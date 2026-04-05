#!/bin/bash#!/bin/bash
R=$1
G=$2
B=$3
echo "$R $G $B" > /sys/devices/platform/hp-wmi/leds/hp::kbd_backlight/multi_intensity
