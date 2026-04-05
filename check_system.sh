#!/bin/bash
echo "==================================="
echo "  🔍 Keyboard Backlight System Check"
echo "==================================="
echo ""

# 1. LED Devices
echo "📌 LED Devices:"
if [ -d "/sys/class/leds" ]; then
    kbd_found=false
    for led in /sys/class/leds/*; do
        if [[ "$led" == *"kbd"* ]] || [[ "$led" == *"backlight"* ]]; then
            echo "  ✅ $(basename "$led")"
            kbd_found=true
        fi
    done
    if [ "$kbd_found" = false ]; then
        echo "  ❌ Keyboard LED not found"
    fi
else
    echo "  ❌ /sys/class/leds directory not found"
fi
echo ""

# 2. HP WMI Support
echo "📌 HP WMI Support:"
if lsmod | grep -q "hp_wmi"; then
    echo "  ✅ hp_wmi module loaded"
    
    if [ -d "/sys/devices/platform/hp-wmi" ]; then
        echo "  ✅ HP WMI platform exists"
        
        if [ -d "/sys/devices/platform/hp-wmi/leds" ]; then
            echo "  ✅ LED interface found:"
            ls -1 /sys/devices/platform/hp-wmi/leds/ | sed 's/^/    /'
        else
            echo "  ❌ No LED interface (this laptop might not support RGB keyboard)"
        fi
    else
        echo "  ❌ HP WMI platform directory not found"
    fi
else
    echo "  ❌ hp_wmi module not loaded"
fi
echo ""

# 3. Screen Brightness (Fallback)
echo "📌 Screen Brightness (Fallback):"
backlight_found=false
for bl in /sys/class/backlight/*; do
    if [ -d "$bl" ]; then
        echo "  ✅ $(basename "$bl")"
        if [ -f "$bl/brightness" ]; then
            max=$(cat "$bl/max_brightness" 2>/dev/null)
            cur=$(cat "$bl/brightness" 2>/dev/null)
            echo "    Current: $cur / Maximum: $max"
        fi
        backlight_found=true
    fi
done
if [ "$backlight_found" = false ]; then
    echo "  ❌ Screen brightness control not found"
fi
echo ""

# 4. Python Dependencies
echo "📌 Python Dependencies:"
if python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); print('  ✅ GTK4 and Adwaita ready')" 2>/dev/null; then
    :
else
    echo "  ❌ GTK4 or Adwaita missing"
fi
echo ""

# 5. Solutions / Suggestions
echo "==================================="
echo "  💡 Solutions / Suggestions"
echo "==================================="
echo ""

if [ ! -d "/sys/devices/platform/hp-wmi/leds" ]; then
    echo "⚠️  This laptop does not support RGB keyboard backlight."
    echo ""
    echo "Options:"
    echo "  1. Run application in TEST mode (simulation)"
    echo "  2. Control screen brightness (alternative)"
    echo "  3. Try on a different HP laptop model"
    echo ""
fi

echo "Laptop Model:"
sudo dmidecode -t system | grep -i "product\|manufacturer" 2>/dev/null | sed 's/^/  /'
