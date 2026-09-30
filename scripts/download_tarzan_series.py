#!/usr/bin/env python3
"""
The Legend of Tarzan (أسطورة طرزان) - Complete Arabic Dub Downloader
Downloads all 35 episodes in 720p HD with official Egyptian Arabic Disney dub.
Saves to /media/dell/Data1/netfelix_data/media/tv/The Legend of Tarzan/Season 01/
Triggers Jellyfin library refresh periodically.
"""

import sys
import time
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

DEST_DIR = Path("/media/dell/Data1/netfelix_data/media/tv/The Legend of Tarzan/Season 01")
DEST_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = (
    "https://archive.org/download/www.arabp-2p.net-walt-disney-tarazan-serie-1-35-hd/"
    "Walt%20Disney%20-%20Tarazan%20Serie%201-35%20By%20MyGamesTop%20and%20GeniusBoy%20%5BHD%5D"
)

JELLYFIN_AUTH = (
    'MediaBrowser Client="Jellyseerr", Device="Jellyseerr", '
    'DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", '
    'Token="4d40f90a8b854cdcbb4faa23134d057b"'
)

# Exact expected byte sizes from Archive.org metadata
EXPECTED_SIZES = {
    1: 433858335,
    2: 428030981,
    3: 436072229,
    4: 435554446,
    5: 436288973,
    6: 421828350,
    7: 435589510,
    8: 436161177,
    9: 436397296,
    10: 435869993,
    11: 436752301,
    12: 436525491,
    13: 436041089,
    14: 436216125,
    15: 402278133,
    16: 436003976,
    17: 436668318,
    18: 435958173,
    19: 436635075,
    20: 435873737,
    21: 436362718,
    22: 436004781,
    23: 431361782,
    24: 434184767,
    25: 435800533,
    26: 436117349,
    27: 435794025,
    28: 435453929,
    29: 434228092,
    30: 422269216,
    31: 430976046,
    32: 435939210,
    33: 434106524,
    34: 435369687,
    35: 434703657,
}


def refresh_jellyfin():
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8096/Library/Refresh",
            data=b"",
            headers={"Authorization": JELLYFIN_AUTH},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[Jellyfin] Library scan triggered (Status {resp.status}).")
    except Exception as e:
        print(f"[Jellyfin] Could not trigger scan: {e}")


def main():
    print("=" * 60)
    print("STARTING 'THE LEGEND OF TARZAN' (أسطورة طرزان) DOWNLOADER")
    print("Target: 35 Episodes (720p HD Egyptian Arabic Dub)")
    print(f"Destination: {DEST_DIR}")
    print("=" * 60)

    total_episodes = 35
    start_time = time.time()

    for ep in range(1, total_episodes + 1):
        target = DEST_DIR / f"The Legend of Tarzan - S01E{ep:02d}.mp4"
        expected = EXPECTED_SIZES.get(ep, 400 * 1024 * 1024)

        # Check if already fully downloaded
        if target.is_file() and target.stat().st_size >= expected:
            print(f"[{ep:02d}/{total_episodes}] Already fully downloaded: {target.name} ({target.stat().st_size // (1024*1024)} MB)")
            continue

        filename_encoded = urllib.parse.quote(
            f"{ep:02d}-Walt Disney - Tarazan Serie By MyGamesTop and GeniusBoy [HD].mp4"
        )
        url = f"{BASE_URL}/{filename_encoded}"

        curr_size = target.stat().st_size if target.is_file() else 0
        if curr_size > 0:
            print(f"\n[{ep:02d}/{total_episodes}] Resuming {target.name} ({curr_size // (1024*1024)} MB / {expected // (1024*1024)} MB)...")
        else:
            print(f"\n[{ep:02d}/{total_episodes}] Downloading {target.name} ({expected // (1024*1024)} MB)...")

        cmd = ["curl", "-L", "-C", "-", "--progress-bar", "-o", str(target), url]
        res = subprocess.run(cmd)

        if res.returncode == 0 and target.is_file() and target.stat().st_size >= expected:
            print(f"[{ep:02d}/{total_episodes}] Successfully saved {target.name} ({target.stat().st_size // (1024*1024)} MB)")
            if ep % 3 == 0 or ep == total_episodes:
                refresh_jellyfin()
        else:
            print(f"[ERROR] Incomplete or failed download for Episode {ep:02d} (Current: {target.stat().st_size if target.is_file() else 0} bytes, Expected: {expected}).")

    refresh_jellyfin()
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"THE LEGEND OF TARZAN DOWNLOAD COMPLETE in {elapsed / 60:.1f} minutes!")
    print("=" * 60)


if __name__ == "__main__":
    main()
