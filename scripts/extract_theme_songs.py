#!/usr/bin/env python3
"""
NetFelix Ambient Theme Songs Generator
Automatically extracts opening theme songs (theme.mp3) for TV shows
using timestamps detected by Intro Skipper and saves them into show folders.
"""

import os
import sqlite3
import subprocess
from pathlib import Path

DB_PATH = Path("/home/dell/Desktop/My_NetFelix/config/jellyfin/data/jellyfin.db")
MEDIA_TV_DIR = Path("/media/dell/Data1/netfelix_data/media/tv")
FFMPEG = "/home/dell/.local/bin/ffmpeg"


def extract_themes():
    if not DB_PATH.exists() or not MEDIA_TV_DIR.exists():
        print("Database or TV directory not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT b.SeriesName, b.Path, s.StartTicks/10000000.0, s.EndTicks/10000000.0
        FROM MediaSegments s
        JOIN BaseItems b ON s.ItemId = b.Id
        WHERE s.Type = 5 AND b.SeriesName IS NOT NULL
    """)
    rows = cur.fetchall()

    extracted = set()
    for series_name, container_path, start, end in rows:
        if series_name in extracted:
            continue

        host_path = container_path.replace("/data/media", "/media/dell/Data1/netfelix_data/media")
        if not os.path.exists(host_path):
            continue

        series_dir = MEDIA_TV_DIR / series_name
        if not series_dir.exists():
            continue

        theme_file = series_dir / "theme.mp3"
        duration = end - start

        if 10 < duration < 180 and not theme_file.exists():
            print(f"Extracting theme for '{series_name}' ({start:.1f}s to {end:.1f}s)...")
            cmd = [
                FFMPEG, "-y", "-ss", str(start), "-to", str(end),
                "-i", host_path, "-vn", "-c:a", "libmp3lame", "-b:a", "192k",
                str(theme_file)
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                print(f"  -> Successfully created {theme_file}")
                extracted.add(series_name)


if __name__ == "__main__":
    extract_themes()
