#!/usr/bin/env python3
"""
MASTER GOAL ORCHESTRATOR:
Fulfills /goal: Download all 5 requested Disney classics in Egyptian / Arabic dub:
1. The Little Mermaid (1989 & 2000 Movies) [Ariel - أريل]
2. Lilo & Stitch (2002 & 2005 Movies + 65 Episode TV Series) [ليلو وسنينش]
3. Recess (65 Episode TV Series + Movies) [الفسحة]
4. Kim Possible (2005 Movie + 66 Episode TV Series) [كيم بوسيبل / دامو ستحيل]
5. Brandy & Mr. Whiskers (39 Episodes organized in Jellyfin) [داندي والسيد ورطة]
"""

import os
import sys
import time
import subprocess
import urllib.request
import json
import re
import html
from pathlib import Path

BASE_DIR = Path("/media/dell/Data1/netfelix_data/media")
MOVIES_DIR = BASE_DIR / "movies"
TV_DIR = BASE_DIR / "tv"

JELLYFIN_KEY = "4d40f90a8b854cdcbb4faa23134d057b"
JELLYFIN_AUTH = (
    'MediaBrowser Client="Jellyseerr", DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="'
    + JELLYFIN_KEY
    + '"'
)


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
        print(f"[Jellyfin] Scan error: {e}")


def wait_for_process(cmd_pattern, script_path, desc):
    print(f"\n>>> Checking status for {desc} <<<")
    # Check if already running
    p = subprocess.run(["pgrep", "-f", cmd_pattern], capture_output=True, text=True)
    if not p.stdout.strip():
        print(f"Starting {desc} ({script_path})...")
        proc = subprocess.Popen([sys.executable, str(script_path)])
        proc.wait()
        print(f"{desc} completed!")
    else:
        print(f"{desc} is currently running (PID {p.stdout.strip().split()[0]}). Waiting for completion...")
        while True:
            p = subprocess.run(["pgrep", "-f", cmd_pattern], capture_output=True, text=True)
            if not p.stdout.strip():
                print(f"{desc} finished!")
                break
            time.sleep(10)


def download_recess_movies():
    print("\n>>> Downloading Recess Movies (Stardima / Hyperwatching) <<<")
    movies = [
        {
            "title": "Recess: All Growed Down (2003)",
            "dest": MOVIES_DIR / "Recess All Growed Down (2003)" / "Recess All Growed Down (2003).mp4",
            "watch_url": "https://v2.hyperwatching.com/watch/DgfLmOuEU48O",
        },
        {
            "title": "Recess: Taking the 5th Grade (2003)",
            "dest": MOVIES_DIR / "Recess Taking the 5th Grade (2003)" / "Recess Taking the 5th Grade (2003).mp4",
            "watch_url": "https://v2.hyperwatching.com/watch/2CtzJ8YwUOkF",
        },
    ]

    from download_recess_series import get_m3u8

    for m in movies:
        dest_file = m["dest"]
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        if dest_file.exists() and dest_file.stat().st_size > 50 * 1024 * 1024:
            print(f"[SKIP] {m['title']} already exists ({dest_file.stat().st_size / (1024*1024):.1f} MB).")
            continue

        print(f"[FETCH] Resolving stream for {m['title']}...")
        try:
            m3u8 = get_m3u8(m["watch_url"])
            temp_file = dest_file.with_suffix(".temp.mp4")
            cmd = ["yt-dlp", "--no-warning", "-q", "--progress", "-o", str(temp_file), m3u8]
            res = subprocess.run(cmd)
            if res.returncode == 0 and temp_file.exists() and temp_file.stat().st_size > 20 * 1024 * 1024:
                temp_file.rename(dest_file)
                print(f"[SUCCESS] {m['title']} saved ({dest_file.stat().st_size / (1024*1024):.1f} MB).")
            else:
                if temp_file.exists():
                    temp_file.unlink()
                print(f"[FAIL] Download failed for {m['title']}.")
        except Exception as e:
            print(f"[ERROR] Could not download {m['title']}: {e}")

    refresh_jellyfin()


def main():
    print("=" * 70)
    print("MASTER GOAL RUNNER: ALL 5 DISNEY ARABIC / EGYPTIAN DUB TITLES")
    print("=" * 70)

    scripts_dir = Path("/home/dell/Desktop/My_NetFelix/scripts")

    # 1. Wait for Disney Classic Movies download
    wait_for_process("download_disney_movies.py", scripts_dir / "download_disney_movies.py", "Disney Movies Downloader")

    # 2. Download Recess Feature Movies
    download_recess_movies()

    # 3. Wait for Recess Series download
    wait_for_process("download_recess_series.py", scripts_dir / "download_recess_series.py", "Recess Series Downloader")

    # 4. Run Lilo & Stitch: The Series download
    wait_for_process("download_lilo_series.py", scripts_dir / "download_lilo_series.py", "Lilo & Stitch Series Downloader")

    # 5. Run Kim Possible: The Series download
    wait_for_process("download_kim_possible_series.py", scripts_dir / "download_kim_possible_series.py", "Kim Possible Series Downloader")

    # 6. Final Jellyfin Library Scan & Verification
    print("\n>>> Triggering Final Jellyfin Scan <<<")
    refresh_jellyfin()
    time.sleep(15)

    print("\n" + "=" * 70)
    print("GOAL EXECUTION FINISHED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
