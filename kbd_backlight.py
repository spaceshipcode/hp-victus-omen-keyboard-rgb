#!/usr/bin/env python3
"""
HP Keyboard Backlight Control Application
RGB keyboard color and brightness control with a modern popup interface.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, GdkPixbuf
import math
import subprocess
import colorsys
import os
import threading
import configparser

import glob
import sys

# Config file path
CONFIG_PATH = os.path.expanduser("~/.config/kbd_backlight.conf")

def load_settings():
    """Load saved settings."""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    try:
        r = config.getint('color', 'r', fallback=255)
        g = config.getint('color', 'g', fallback=0)
        b = config.getint('color', 'b', fallback=0)
        brightness = config.getfloat('settings', 'brightness', fallback=100.0)
        return r, g, b, brightness
    except Exception:
        return 255, 0, 0, 100.0

def save_settings(r, g, b, brightness):
    """Save current settings to file."""
    config = configparser.ConfigParser()
    config['color'] = {'r': str(r), 'g': str(g), 'b': str(b)}
    config['settings'] = {'brightness': str(brightness)}
    try:
        with open(CONFIG_PATH, 'w') as f:
            config.write(f)
    except Exception as e:
        print(f"Failed to save setting: {e}")

# Test mode control (TEST_MODE=1 python3 kbd_backlight.py)
TEST_MODE = os.environ.get('TEST_MODE', '0') == '1'

# LED file path finding
def find_led_path():
    """Try to find LED hardware path."""
    # Simulate if in test mode
    if TEST_MODE:
        return "/tmp/test_kbd_brightness"
    
    # Possible paths
    patterns = [
        "/sys/class/leds/*::kbd_backlight/multi_intensity",
        "/sys/class/leds/*kbd_backlight/multi_intensity",
        "/sys/class/leds/*::kbd_backlight/brightness",
        "/sys/class/leds/*kbd_backlight/brightness",
        # HP Omen/Pavilion specific
        "/sys/devices/platform/hp-wmi/leds/*/multi_intensity",
        "/sys/devices/platform/hp-wmi/leds/hp::kbd_backlight/multi_intensity",
    ]
    
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
            
    return None

LED_PATH = find_led_path()
HARDWARE_FOUND = LED_PATH is not None or TEST_MODE

# Application directory
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(APP_DIR, "icon.png")

# Helper script path (In the same folder as the Python file)
HELPER_SCRIPT = "/usr/local/bin/kbd_helper.sh"

class ColorWheel(Gtk.Box):
    """Custom color wheel widget - HSV color selection."""
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        self.hue = 0.0  # 0-1 arası
        self.saturation = 1.0  # 0-1 arası
        
        # Renk yuvarlağı için bir image oluştur
        self.size = 200
        self.image = Gtk.Picture()
        self.image.set_size_request(self.size, self.size)
        self.append(self.image)
        
        # Mouse etkileşimi için overlay
        self.overlay = Gtk.Overlay()
        self.remove(self.image)
        self.overlay.set_child(self.image)
        
        # Seçim göstergesi
        self.selector = Gtk.DrawingArea()
        self.selector.set_size_request(self.size, self.size)
        self.selector.set_draw_func(self.draw_selector)
        self.overlay.add_overlay(self.selector)
        
        self.append(self.overlay)
        
        # Mouse etkileşimi
        click = Gtk.GestureClick.new()
        click.connect("pressed", self.on_click)
        self.selector.add_controller(click)
        
        drag = Gtk.GestureDrag.new()
        drag.connect("drag-update", self.on_drag)
        drag.connect("drag-begin", self.on_drag_begin)
        self.selector.add_controller(drag)
        
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Callback fonksiyonu
        self.on_color_changed = None
        
        # Renk yuvarlağını oluştur
        self.create_color_wheel()
        
        # Donanım yoksa devre dışı bırak
        if not HARDWARE_FOUND:
            self.set_opacity(0.5)
            self.set_sensitive(False)
    
    def create_color_wheel(self):
        """Create color wheel pixbuf."""
        size = self.size
        center = size // 2
        radius = center - 5
        
        # RGBA pixel array
        pixels = []
        
        for y in range(size):
            for x in range(size):
                dx = x - center
                dy = y - center
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance <= radius:
                    # Renk hesapla
                    hue = (math.atan2(dy, dx) / (2 * math.pi) + 0.5) % 1.0
                    sat = min(distance / radius, 1.0)
                    r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
                    pixels.extend([int(r*255), int(g*255), int(b*255), 255])
                else:
                    # Şeffaf
                    pixels.extend([0, 0, 0, 0])
        
        # Pixbuf oluştur
        pixel_bytes = GLib.Bytes.new(bytes(pixels))
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            pixel_bytes,
            GdkPixbuf.Colorspace.RGB,
            True,  # has_alpha
            8,     # bits_per_sample
            size,  # width
            size,  # height
            size * 4  # rowstride
        )
        
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        self.image.set_paintable(texture)
    
    def draw_selector(self, area, cr, width, height):
        """Draw selection indicator."""
        center = self.size // 2
        radius = center - 5
        
        # Seçim noktası
        sel_radius = self.saturation * radius
        sel_angle = self.hue * 2 * math.pi - math.pi
        sel_x = center + sel_radius * math.cos(sel_angle)
        sel_y = center + sel_radius * math.sin(sel_angle)
        
        # Beyaz çerçeveli seçim dairesi
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(3)
        cr.arc(sel_x, sel_y, 10, 0, 2 * math.pi)
        cr.stroke()
        
        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(1)
        cr.arc(sel_x, sel_y, 10, 0, 2 * math.pi)
        cr.stroke()
    
    def update_from_point(self, x, y):
        """Update color values from given point."""
        if not HARDWARE_FOUND:
            return
            
        center = self.size // 2
        radius = center - 5
        
        dx = x - center
        dy = y - center
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance <= radius:
            self.saturation = distance / radius
            self.hue = (math.atan2(dy, dx) / (2 * math.pi) + 0.5) % 1.0
            self.selector.queue_draw()
            
            if self.on_color_changed:
                self.on_color_changed()
    
    def on_click(self, gesture, n_press, x, y):
        self.update_from_point(x, y)
    
    def on_drag_begin(self, gesture, x, y):
        self.drag_start_x = x
        self.drag_start_y = y
        self.update_from_point(x, y)
    
    def on_drag(self, gesture, offset_x, offset_y):
        x = self.drag_start_x + offset_x
        y = self.drag_start_y + offset_y
        self.update_from_point(x, y)
    
    def get_rgb(self):
        """Return selected color as RGB (0-255)."""
        rgb = colorsys.hsv_to_rgb(self.hue, self.saturation, 1.0)
        return tuple(int(c * 255) for c in rgb)
    
    def set_rgb(self, r, g, b):
        """Set color from RGB values."""
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        self.hue = h
        self.saturation = s
        self.selector.queue_draw()


class KeyboardBacklightApp(Adw.Application):
    """Main application class."""
    
    def __init__(self):
        super().__init__(application_id="io.github.spaceshipcode.kbd-backlight")
        self.brightness = 1.0
        self.last_rgb = (0, 0, 0)
        # Load saved settings
        self.saved_r, self.saved_g, self.saved_b, self.saved_brightness = load_settings()
        self.connect('activate', self.on_activate)
    
    def on_activate(self, app):
        """Create the main window when the application is activated."""
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_title("Keyboard Backlight")
        self.win.set_default_size(300, 520)
        self.win.set_resizable(False)
        
        # Dark theme
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        
        # Ana container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        
        # Title
        title = Gtk.Label(label="🎨 Keyboard Color")
        title.add_css_class("title-1")
        main_box.append(title)
        
        # Renk yuvarlağı
        wheel_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        wheel_box.set_halign(Gtk.Align.CENTER)
        self.color_wheel = ColorWheel()
        self.color_wheel.on_color_changed = self.on_color_changed
        wheel_box.append(self.color_wheel)
        main_box.append(wheel_box)
        
        # Renk önizleme
        preview_frame = Gtk.Frame()
        preview_frame.set_margin_top(8)
        self.preview_box = Gtk.Box()
        self.preview_box.set_size_request(-1, 40)
        preview_frame.set_child(self.preview_box)
        main_box.append(preview_frame)
        
        # Brightness section
        brightness_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        brightness_box.set_margin_top(8)
        
        brightness_label = Gtk.Label(label="💡 Brightness")
        brightness_label.set_halign(Gtk.Align.START)
        brightness_box.append(brightness_label)
        
        # Parlaklık slider
        self.brightness_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.brightness_scale.set_value(100)
        self.brightness_scale.set_draw_value(True)
        self.brightness_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.brightness_scale.connect("value-changed", self.on_brightness_changed)
        brightness_box.append(self.brightness_scale)
        
        main_box.append(brightness_box)
        
        # RGB değer gösterimi
        self.rgb_label = Gtk.Label(label="RGB: 255, 0, 0")
        self.rgb_label.add_css_class("dim-label")
        self.rgb_label.set_margin_top(8)
        main_box.append(self.rgb_label)
        
        # Turn Off button
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(16)
        
        off_btn = Gtk.Button(label="🌙 Turn Off")
        off_btn.add_css_class("destructive-action")
        off_btn.add_css_class("pill")
        off_btn.set_size_request(160, 44)
        off_btn.connect("clicked", self.on_turn_off)
        button_box.append(off_btn)
        
        main_box.append(button_box)

        # Overlay for close button
        overlay = Gtk.Overlay()
        overlay.set_child(main_box)
        
        # Upper right close button
        self.close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        self.close_btn.set_halign(Gtk.Align.END)
        self.close_btn.set_valign(Gtk.Align.START)
        self.close_btn.set_margin_top(12)
        self.close_btn.set_margin_end(12)
        self.close_btn.add_css_class("close-button")
        self.close_btn.connect("clicked", lambda x: self.win.close())
        overlay.add_overlay(self.close_btn)
        
        # CSS styles
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window {
                background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
            }
            .title-1 {
                font-size: 24px;
                font-weight: bold;
                color: #e94560;
                margin-bottom: 8px;
            }
            frame {
                border-radius: 12px;
                border: 2px solid rgba(255,255,255,0.2);
                background: rgba(0,0,0,0.3);
            }
            button.suggested-action {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                font-weight: bold;
                font-size: 15px;
                border-radius: 22px;
                border: none;
            }
            button.suggested-action:hover {
                background: linear-gradient(135deg, #7b8eef 0%, #8a5cb5 100%);
            }
            button.destructive-action {
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
                font-weight: bold;
                font-size: 15px;
                border-radius: 22px;
                border: none;
            }
            button.destructive-action:hover {
                background: linear-gradient(135deg, #f5a8fc 0%, #f77485 100%);
            }
            scale trough {
                background: rgba(255,255,255,0.1);
                border-radius: 6px;
                min-height: 8px;
            }
            scale highlight {
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                border-radius: 6px;
            }
            scale slider {
                background: white;
                border-radius: 50%;
                min-width: 20px;
                min-height: 20px;
            }
            .dim-label {
                color: rgba(255,255,255,0.6);
                font-size: 13px;
            }
            switch {
                background: rgba(255,255,255,0.1);
            }
            switch:checked {
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            }
            .close-button {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border-radius: 99px;
                padding: 8px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                transition: all 0.3s ease;
            }
            .close-button:hover {
                background: rgba(233, 69, 96, 0.9);
                border-color: #e94560;
                transform: rotate(90deg);
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        if not HARDWARE_FOUND:
            # Hardware not found
            self.win.set_title("❌ Keyboard Color (No Hardware)")
            title.set_label("❌ Keyboard Color")
            off_btn.set_sensitive(False)
            self.brightness_scale.set_sensitive(False)
            
            # More detailed info message
            info_text = (
                "⚠️ RGB Keyboard lighting hardware not found!\n\n"
                "💡 For TEST mode:\n"
                "   TEST_MODE=1 python3 kbd_backlight.py\n\n"
                "📖 For system check:\n"
                "   bash check_system.sh"
            )
            self.rgb_label.set_text(info_text)
            self.rgb_label.set_justify(Gtk.Justification.LEFT)
        elif TEST_MODE:
            # Test mode
            self.win.set_title("🧪 Keyboard Color (TEST MODE)")
            title.set_label("🧪 TEST Mode")
            self.rgb_label.set_text("TEST mode active - Commands are written to console")
        else:
            # Hardware found
            self.win.set_title(f"Keyboard Color - {os.path.basename(LED_PATH)}")

        self.win.set_content(overlay)

        # Apply saved settings to the UI
        self.color_wheel.set_rgb(self.saved_r, self.saved_g, self.saved_b)
        self.brightness_scale.set_value(self.saved_brightness)

        self.update_preview()
        self.win.present()
    
    def get_adjusted_rgb(self):
        """Get brightness-adjusted RGB values."""
        r, g, b = self.color_wheel.get_rgb()
        brightness = self.brightness_scale.get_value() / 100.0
        return (
            int(r * brightness),
            int(g * brightness),
            int(b * brightness)
        )
    
    def update_preview(self):
        """Update color preview."""
        r, g, b = self.get_adjusted_rgb()
        
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            f"box {{ background-color: rgb({r}, {g}, {b}); border-radius: 8px; }}".encode()
        )
        self.preview_box.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        
        self.rgb_label.set_text(f"RGB: {r}, {g}, {b}")
        
        # Update keyboard and save settings if value changed
        if HARDWARE_FOUND and (r, g, b) != self.last_rgb:
            self.last_rgb = (r, g, b)
            self.set_keyboard_color_async(r, g, b)
            save_settings(r, g, b, self.brightness_scale.get_value())
    
    def on_color_changed(self):
        """Renk değiştiğinde çağrılır."""
        self.update_preview()
    
    def on_brightness_changed(self, scale):
        """Called when brightness changes."""
        self.update_preview()
    

    
    def set_keyboard_color_async(self, r, g, b):
        """Set keyboard color asynchronously (no password)."""
        if not HARDWARE_FOUND:
            return

        def run():
            try:
                if TEST_MODE:
                    # Test modunda sadece ekrana yazdır
                    print(f"🎨 TEST: RGB = ({r}, {g}, {b})")
                    # Test dosyasına yaz
                    with open(LED_PATH, 'w') as f:
                        f.write(f"{r} {g} {b}\n")
                else:
                    # Helper script kullan
                    # Parametreler: PATH R G B
                    subprocess.run(
                        ['sudo', HELPER_SCRIPT, LED_PATH, str(r), str(g), str(b)],
                        capture_output=True,
                        timeout=1
                    )
            except Exception as e:
                if TEST_MODE:
                    print(f"⚠️ TEST: Error - {e}")
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    
    def set_keyboard_color(self, r, g, b):
        """Set keyboard color."""
        if not HARDWARE_FOUND:
            return False
            
        try:
            if TEST_MODE:
                # Test modunda sadece ekrana yazdır
                print(f"✨ TEST: Uygula - RGB = ({r}, {g}, {b})")
                with open(LED_PATH, 'w') as f:
                    f.write(f"{r} {g} {b}\n")
                return True
            else:
                subprocess.run(
                    ['sudo', HELPER_SCRIPT, LED_PATH, str(r), str(g), str(b)],
                    capture_output=True,
                    timeout=2
                )
                return True
        except Exception as e:
            print(f"Error: {e}")
            return False
    

    
    def on_turn_off(self, button):
        """When Turn Off button is clicked."""
        self.set_keyboard_color(0, 0, 0)
        self.brightness_scale.set_value(0)
        # Save off state
        save_settings(0, 0, 0, 0.0)


def main():
    app = KeyboardBacklightApp()
    app.run(None)


if __name__ == "__main__":
    main()
