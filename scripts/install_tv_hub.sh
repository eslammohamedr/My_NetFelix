#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

TV_IP="192.168.1.2"
TV_TARGET="UA50AU7000UXEG"

echo ">> Checking Samsung TV status at $TV_IP..."
if ! ping -c 1 -W 1 "$TV_IP" >/dev/null 2>&1; then
    echo "❌ TV is unreachable. Please turn on your Samsung TV and ensure it is connected to Wi-Fi."
    exit 1
fi

echo ">> Installing NetFelix Hub (NetFelixHub.wgt) onto Samsung TV..."
docker run --rm -v "$SCRIPT_DIR/tizen_apps:/workspace" -w /workspace --entrypoint sh georift/install-jellyfin-tizen -c "
    sdb connect $TV_IP
    tizen install -n NetFelixHub.wgt -t $TV_TARGET
"

echo "✅ NetFelix Hub installed successfully on Samsung TV!"
