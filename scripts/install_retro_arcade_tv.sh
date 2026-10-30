#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo ">> Checking Samsung TV status at 192.168.1.3..."
if ! ping -c 1 -W 1 192.168.1.3 >/dev/null 2>&1; then
    echo "❌ TV is unreachable. Please turn on your Samsung TV and ensure it is connected to Wi-Fi."
    exit 1
fi

echo ">> Installing Retro Arcade (RetroArcade.wgt) onto Samsung TV..."
docker run --rm -v "$SCRIPT_DIR/tizen_apps:/workspace" -w /workspace --entrypoint sh georift/install-jellyfin-tizen -c "
    sdb connect 192.168.1.3
    tizen install -n RetroArcade.wgt -t UA50AU7000UXEG
"

echo "✅ Retro Arcade installed successfully on Samsung TV!"
