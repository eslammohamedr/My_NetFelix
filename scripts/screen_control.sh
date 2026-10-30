#!/usr/bin/env bash
# NetFelix Laptop Physical Screen Power Saver
# Controls physical display (:0) without affecting remote RDP/RustDesk sessions (:10)

ACTION="${1:-toggle}"

is_screen_on() {
    # Check if eDP-1 is active with a resolution on physical display :0
    if xrandr -d :0 2>/dev/null | grep -E "eDP-1 connected [0-9]+x[0-9]+" >/dev/null; then
        return 0
    else
        return 1
    fi
}

turn_off() {
    echo ">> Turning OFF physical laptop screen (:0)..."
    xrandr -d :0 --output eDP-1 --off 2>/dev/null || true
    DISPLAY=:0 xset +dpms 2>/dev/null || true
    DISPLAY=:0 xset dpms force off 2>/dev/null || true
    echo "✅ Physical screen is now OFF (Power saving mode active)."
    which notify-send >/dev/null 2>&1 && notify-send -i display "Laptop Screen" "Physical display turned OFF to save power" 2>/dev/null || true
}

turn_on() {
    echo ">> Turning ON physical laptop screen (:0)..."
    xrandr -d :0 --output eDP-1 --auto 2>/dev/null || true
    DISPLAY=:0 xset dpms force on 2>/dev/null || true
    echo "✅ Physical screen is now ON."
    which notify-send >/dev/null 2>&1 && notify-send -i display "Laptop Screen" "Physical display turned ON" 2>/dev/null || true
}

case "$ACTION" in
    off)
        turn_off
        ;;
    on)
        turn_on
        ;;
    status)
        if is_screen_on; then
            echo "ON"
        else
            echo "OFF"
        fi
        ;;
    toggle|*)
        if is_screen_on; then
            turn_off
        else
            turn_on
        fi
        ;;
esac
