#!/usr/bin/env python3
"""
KDE Brightness Monitor - Keyboard RGB Controller
Monitors /sys/class/leds/hp::kbd_backlight/brightness changes
and updates RGB values accordingly (software brightness emulation)
"""

import time
import os

BRIGHTNESS_FILE = "/sys/class/leds/hp::kbd_backlight/brightness"
RGB_FILE = "/sys/class/leds/hp::kbd_backlight/multi_intensity"

# Stored base color (at 100% brightness)
base_color = [255, 255, 255]  # White by default
last_brightness = 255

def read_file(path):
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except:
        return None

def write_rgb(r, g, b):
    try:
        with open(RGB_FILE, 'w') as f:
            f.write(f"{r} {g} {b}")
        return True
    except:
        return False

def monitor_brightness():
    global last_brightness, base_color
    
    print("🔍 KDE Brightness Monitor başlatıldı...")
    print(f"📁 Izlenen dosya: {BRIGHTNESS_FILE}")
    
    while True:
        # Read current brightness (0-255)
        brightness_str = read_file(BRIGHTNESS_FILE)
        if brightness_str is None:
            time.sleep(0.5)
            continue
            
        try:
            brightness = int(brightness_str)
        except:
            time.sleep(0.5)
            continue
        
        # Brightness changed?
        if brightness != last_brightness:
            print(f"💡 Brightness değişti: {last_brightness} → {brightness}")
            
            # Read current RGB to update base color if it changed externally
            rgb_str = read_file(RGB_FILE)
            if rgb_str:
                try:
                    parts = rgb_str.split()
                    if len(parts) == 3:
                        # If brightness was at max, this is new base color
                        if last_brightness == 255:
                            base_color = [int(p) for p in parts]
                            print(f"🎨 Yeni baz renk: {base_color}")
                except:
                    pass
            
            # Calculate scaled RGB
            scale = brightness / 255.0
            scaled_r = int(base_color[0] * scale)
            scaled_g = int(base_color[1] * scale)
            scaled_b = int(base_color[2] * scale)
            
            # Write scaled values
            if write_rgb(scaled_r, scaled_g, scaled_b):
                print(f"✅ RGB güncellendi: {scaled_r} {scaled_g} {scaled_b}")
            
            last_brightness = brightness
        
        time.sleep(0.2)  # Poll every 200ms

if __name__ == "__main__":
    try:
        monitor_brightness()
    except KeyboardInterrupt:
        print("\n👋 Monitor durduruldu")
