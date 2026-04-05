#!/bin/bash
# =============================================================================
#  HP Victus / OMEN RGB Keyboard Backlight Control
#  All-in-one setup script
#  Supports: Ubuntu/Debian, Fedora/RHEL, Arch/Manjaro, openSUSE, Alpine
# =============================================================================

set -e

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}${BLUE}══ $* ${NC}"; }

# ── Resolve script directory ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER_DEST="/usr/local/bin/kbd_helper.sh"
RULES_DEST="/etc/udev/rules.d/99-hp-victus-kbd.rules"
SUDOERS_FILE="/etc/sudoers.d/kbd-backlight"
CURRENT_USER="$(whoami)"
INSTALL_PREFIX="${HOME}/.local/share/kbd-backlight"

# ── Print banner ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ██╗  ██╗██████╗     ██╗  ██╗███████╗██╗   ██╗"
echo "  ██║  ██║██╔══██╗    ██║ ██╔╝██╔════╝╚██╗ ██╔╝"
echo "  ███████║██████╔╝    █████╔╝ █████╗   ╚████╔╝ "
echo "  ██╔══██║██╔═══╝     ██╔═██╗ ██╔══╝    ╚██╔╝  "
echo "  ██║  ██║██║         ██║  ██╗███████╗   ██║   "
echo "  ╚═╝  ╚═╝╚═╝         ╚═╝  ╚═╝╚══════╝   ╚═╝   "
echo ""
echo -e "${BOLD}  RGB Keyboard Backlight Control — Setup Script${NC}"
echo -e "${CYAN}  github.com/your-username/hp-kbd-backlight${NC}"
echo ""
echo -e "${NC}"

# ── Root check ────────────────────────────────────────────────────────────────
if [[ $EUID -eq 0 ]]; then
    error "Do not run this script as root. Run as a normal user — sudo will be used when needed."
fi

# ── Detect package manager ────────────────────────────────────────────────────
step "Detecting Package Manager"

detect_pkg_manager() {
    if   command -v apt    &>/dev/null; then echo "apt"
    elif command -v dnf    &>/dev/null; then echo "dnf"
    elif command -v pacman &>/dev/null; then echo "pacman"
    elif command -v zypper &>/dev/null; then echo "zypper"
    elif command -v apk    &>/dev/null; then echo "apk"
    elif command -v emerge &>/dev/null; then echo "emerge"
    else echo "unknown"
    fi
}

PKG_MGR=$(detect_pkg_manager)

case "$PKG_MGR" in
    apt)    info "Detected: Debian / Ubuntu / Linux Mint" ;;
    dnf)    info "Detected: Fedora / RHEL / CentOS Stream" ;;
    pacman) info "Detected: Arch Linux / Manjaro / EndeavourOS" ;;
    zypper) info "Detected: openSUSE Tumbleweed / Leap" ;;
    apk)    info "Detected: Alpine Linux" ;;
    emerge) info "Detected: Gentoo Linux" ;;
    *)      error "Unsupported package manager. Install dependencies manually and re-run." ;;
esac

# ── Install Python / GTK4 / libadwaita dependencies ───────────────────────────
step "Installing Python & GTK4 Dependencies"

install_gui_deps() {
    case "$PKG_MGR" in
        apt)
            sudo apt update -qq
            sudo apt install -y \
                python3 python3-gi python3-gi-cairo \
                gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 \
                libgtk-4-dev libadwaita-1-dev \
                git build-essential dkms linux-headers-$(uname -r)
            ;;
        dnf)
            sudo dnf install -y \
                python3 python3-gobject python3-cairo \
                gtk4 libadwaita \
                git gcc make dkms "kernel-devel-$(uname -r)" || \
            sudo dnf install -y \
                python3 python3-gobject python3-cairo \
                gtk4 libadwaita \
                git gcc make dkms kernel-devel
            ;;
        pacman)
            sudo pacman -Sy --noconfirm \
                python python-gobject python-cairo \
                gtk4 libadwaita \
                git base-devel dkms linux-headers
            ;;
        zypper)
            sudo zypper install -y \
                python3 python3-gobject python3-cairo \
                gtk4 libadwaita \
                git gcc make dkms "kernel-default-devel=$(uname -r | sed 's/-default//')" || \
            sudo zypper install -y \
                python3 python3-gobject python3-cairo \
                gtk4 libadwaita \
                git gcc make dkms kernel-default-devel
            ;;
        apk)
            sudo apk add \
                python3 py3-gobject3 py3-cairo \
                gtk4.0 libadwaita \
                git gcc make dkms linux-headers
            ;;
        emerge)
            sudo emerge --ask=n \
                dev-python/pygobject x11-libs/gtk+ x11-libs/libadwaita \
                dev-vcs/git sys-kernel/dkms
            ;;
    esac
}

install_gui_deps && success "GUI dependencies installed." || error "Failed to install GUI dependencies."

# Verify GTK4 + Adwaita are importable
if python3 -c "
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
" 2>/dev/null; then
    success "GTK4 + libadwaita verified OK."
else
    warn "GTK4 or libadwaita import failed. The GUI may not start."
fi

# ── Install TUXOV hp-wmi kernel module ───────────────────────────────────────
step "Installing HP WMI Kernel Module (TUXOV)"

TUXOV_REPO="https://github.com/TUXOV/hp-wmi-fan-and-backlight-control.git"
TUXOV_DIR="/tmp/hp-wmi-setup"

install_kernel_module() {
    # Check if already installed
    if dkms status 2>/dev/null | grep -q "hp-wmi-fan"; then
        success "hp-wmi kernel module already installed via DKMS."
        return 0
    fi

    # Check kernel headers exist
    HEADERS_PATH="/lib/modules/$(uname -r)/build"
    if [[ ! -d "$HEADERS_PATH" ]]; then
        warn "Kernel headers not found at $HEADERS_PATH."
        warn "RGB keyboard control may not work. Install kernel headers for your kernel version."
        return 1
    fi

    info "Cloning TUXOV hp-wmi repository..."
    rm -rf "$TUXOV_DIR"
    git clone --depth 1 "$TUXOV_REPO" "$TUXOV_DIR" || {
        warn "Could not clone TUXOV repository. Skipping kernel module installation."
        warn "Install manually: $TUXOV_REPO"
        return 1
    }

    cd "$TUXOV_DIR"
    if [[ -f "install.sh" ]]; then
        info "Running TUXOV install script..."
        sudo bash install.sh
    elif [[ -f "Makefile" ]]; then
        info "Building module with DKMS..."
        MODULE_VERSION=$(grep -r "^VERSION" Makefile 2>/dev/null | head -1 | awk -F= '{print $2}' | tr -d ' ' || echo "0.1")
        sudo cp -r "$TUXOV_DIR" "/usr/src/hp-wmi-fan-${MODULE_VERSION}"
        sudo dkms add -m hp-wmi-fan -v "$MODULE_VERSION"
        sudo dkms build -m hp-wmi-fan -v "$MODULE_VERSION"
        sudo dkms install -m hp-wmi-fan -v "$MODULE_VERSION"
        sudo modprobe hp-wmi 2>/dev/null || true
    fi

    cd "$SCRIPT_DIR"
    rm -rf "$TUXOV_DIR"

    if dkms status 2>/dev/null | grep -q "hp-wmi-fan\|hp_wmi"; then
        success "hp-wmi kernel module installed successfully."
    else
        warn "Module installation may have failed. Check: dkms status"
    fi
}

install_kernel_module || warn "Kernel module step skipped — GUI will still work in TEST_MODE."

# ── Fix and install kbd_helper.sh ─────────────────────────────────────────────
step "Installing Helper Script"

# Write a clean kbd_helper.sh (fixes any shebang issues)
HELPER_CONTENT='#!/bin/bash
# kbd_helper.sh — writes RGB values to the keyboard sysfs node
# Usage: kbd_helper.sh <R> <G> <B>
R="$1"; G="$2"; B="$3"
LED_PATH="/sys/class/leds/hp::kbd_backlight/multi_intensity"
ALT_PATH="/sys/devices/platform/hp-wmi/leds/hp::kbd_backlight/multi_intensity"

if [[ -f "$LED_PATH" ]]; then
    echo "$R $G $B" > "$LED_PATH"
elif [[ -f "$ALT_PATH" ]]; then
    echo "$R $G $B" > "$ALT_PATH"
else
    echo "Error: No keyboard LED sysfs path found." >&2
    exit 1
fi
'

echo "$HELPER_CONTENT" | sudo tee "$HELPER_DEST" > /dev/null
sudo chmod 755 "$HELPER_DEST"
sudo chown root:root "$HELPER_DEST"
success "Helper script installed: $HELPER_DEST"

# ── Install udev rules ────────────────────────────────────────────────────────
step "Installing udev Rules (Passwordless Access)"

sudo cp "${SCRIPT_DIR}/99-hp-victus-kbd.rules" "$RULES_DEST"
sudo chmod 644 "$RULES_DEST"
sudo udevadm control --reload-rules 2>/dev/null && sudo udevadm trigger 2>/dev/null || true
success "udev rules installed: $RULES_DEST"

# ── Configure sudoers ─────────────────────────────────────────────────────────
step "Configuring Passwordless sudo"

# Clean up previous entries
sudo rm -f "$SUDOERS_FILE" "/etc/sudoers.d/kbd_backlight" 2>/dev/null || true

echo "# HP Keyboard Backlight — passwordless helper
$CURRENT_USER ALL=(ALL) NOPASSWD: $HELPER_DEST" | sudo tee "$SUDOERS_FILE" > /dev/null
sudo chmod 440 "$SUDOERS_FILE"
success "sudoers entry created for user: $CURRENT_USER"

# ── Install the Python app ────────────────────────────────────────────────────
step "Installing Application"

mkdir -p "$INSTALL_PREFIX"
cp "${SCRIPT_DIR}/kbd_backlight.py" "$INSTALL_PREFIX/"
cp "${SCRIPT_DIR}/kde_brightness_monitor.py" "$INSTALL_PREFIX/"

# Icon installation for Wayland compatibility
step "Installing Icon into Theme"
ICON_NAME="io.github.spaceshipcode.kbd-backlight"
HICOLOR_DIR="${HOME}/.local/share/icons/hicolor"
mkdir -p "$HICOLOR_DIR/512x512/apps"
mkdir -p "$HICOLOR_DIR/scalable/apps"

# Find source icon (try new ID name first, then fallback to icon.png)
SRC_ICON=""
[[ -f "${SCRIPT_DIR}/${ICON_NAME}.png" ]] && SRC_ICON="${SCRIPT_DIR}/${ICON_NAME}.png"
[[ -z "$SRC_ICON" && -f "${SCRIPT_DIR}/icon.png" ]] && SRC_ICON="${SCRIPT_DIR}/icon.png"

if [[ -n "$SRC_ICON" ]]; then
    # Install to various hicolor folders
    cp "$SRC_ICON" "$HICOLOR_DIR/512x512/apps/${ICON_NAME}.png"
    cp "$SRC_ICON" "$HICOLOR_DIR/scalable/apps/${ICON_NAME}.png"
    # Also keep a local copy
    cp "$SRC_ICON" "$INSTALL_PREFIX/${ICON_NAME}.png"
    success "Icon installed to icon theme: $ICON_NAME"
    
    # Refresh caches
    gtk-update-icon-cache -f "$HICOLOR_DIR" &>/dev/null || true
    if command -v kbuildsycoca5 &>/dev/null; then
        kbuildsycoca5 &>/dev/null || true
    elif command -v kbuildsycoca6 &>/dev/null; then
        kbuildsycoca6 &>/dev/null || true
    fi
fi

# Create a launcher in ~/.local/bin
mkdir -p "${HOME}/.local/bin"
cat > "${HOME}/.local/bin/kbd-backlight" << EOF
#!/bin/bash
cd "$INSTALL_PREFIX"
exec python3 "$INSTALL_PREFIX/kbd_backlight.py" "\$@"
EOF
chmod +x "${HOME}/.local/bin/kbd-backlight"
success "Launcher installed: ~/.local/bin/kbd-backlight"

# ── Create .desktop file ──────────────────────────────────────────────────────
step "Creating Desktop Entry"

DESKTOP_DIR="${HOME}/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
ICON_NAME="io.github.spaceshipcode.kbd-backlight"

cat > "${DESKTOP_DIR}/${ICON_NAME}.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Keyboard Backlight
GenericName=RGB Keyboard Control
Comment=HP Victus / OMEN keyboard RGB backlight control
Exec=${HOME}/.local/bin/kbd-backlight
Icon=${ICON_NAME}
Terminal=false
Categories=Settings;HardwareSettings;
Keywords=keyboard;backlight;rgb;hp;victus;omen;
StartupNotify=true
StartupWMClass=${ICON_NAME}
X-GNOME-UsesNotifications=true
EOF

success "Desktop entry created: ${DESKTOP_DIR}/${ICON_NAME}.desktop"

# ── Optional: KDE brightness monitor service ──────────────────────────────────
step "KDE Brightness Monitor (Optional)"

cat > "/tmp/kde-kbdlight-monitor.service" << EOF
[Unit]
Description=KDE Keyboard Brightness Monitor for HP Victus
After=graphical.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_PREFIX/kde_brightness_monitor.py
Restart=always
RestartSec=3
User=${CURRENT_USER}

[Install]
WantedBy=graphical.target
EOF

echo ""
read -rp "  Install KDE brightness monitor service? (y/N): " -n 1 KDE_REPLY; echo
if [[ "$KDE_REPLY" =~ ^[Yy]$ ]]; then
    sudo cp /tmp/kde-kbdlight-monitor.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable kde-kbdlight-monitor.service
    sudo systemctl start kde-kbdlight-monitor.service
    success "KDE brightness monitor service enabled and started."
else
    info "Skipped. Enable later with:"
    info "  sudo systemctl enable --now kde-kbdlight-monitor.service"
fi
rm -f /tmp/kde-kbdlight-monitor.service

# ── System check ──────────────────────────────────────────────────────────────
step "Running System Check"
bash "${SCRIPT_DIR}/check_system.sh"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  ✅  Installation Complete!${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Run the application:${NC}"
echo -e "    kbd-backlight"
echo ""
echo -e "  ${BOLD}Test mode (no hardware needed):${NC}"
echo -e "    TEST_MODE=1 kbd-backlight"
echo ""
echo -e "  ${BOLD}System diagnostics:${NC}"
echo -e "    bash ${SCRIPT_DIR}/check_system.sh"
echo ""
warn "If PATH doesn't include ~/.local/bin, add this to your ~/.bashrc or ~/.zshrc:"
echo -e "    ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
echo ""
