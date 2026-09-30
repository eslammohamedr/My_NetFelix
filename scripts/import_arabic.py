#!/usr/bin/env python3
"""
Direct Importer for Classic Arabic-Dubbed Movies and Series.
Downloads directly from verified unthrottled archives and triggers Jellyfin library refresh.
"""

import os
import sys
import subprocess
import urllib.request
import json
from pathlib import Path

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/media/dell/Data1/netfelix_data/media"))
MOVIES_DIR = MEDIA_ROOT / "movies"
TV_DIR = MEDIA_ROOT / "tv"
JELLYFIN_KEY = "4d40f90a8b854cdcbb4faa23134d057b"
JELLYFIN_AUTH = (
    'MediaBrowser Client="Jellyseerr", Device="Jellyseerr", '
    'DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="'
    + JELLYFIN_KEY
    + '"'
)

# Catalog of verified direct Arabic dub downloads
CATALOG = {
    "emperor-movie": {
        "title": "The Emperor's New Groove (2000) [Arabic Dub - كوزكو مدبلج مصري]",
        "type": "movie",
        "dest": MOVIES_DIR / "The Emperor's New Groove (2000)",
        "filename": "The Emperor's New Groove (2000).mp4",
        "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8a%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/The%20Emperor%20New%20Groove/The%20Emperor%20New%20Groove.mp4",
    },
    "lion-king-1": {
        "title": "The Lion King (1994) [Arabic Dub - الأسد الملك مدبلج مصري]",
        "type": "movie",
        "dest": MOVIES_DIR / "The Lion King (1994)",
        "filename": "The Lion King (1994).mp4",
        "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8a%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Lion%20King%201/Lion%20King%201.mp4",
    },
    "lion-king-2": {
        "title": "The Lion King 2: Simba's Pride (1998) [Arabic Dub - سيمبا 2 مدبلج مصري]",
        "type": "movie",
        "dest": MOVIES_DIR / "The Lion King 2 Simba's Pride (1998)",
        "filename": "The Lion King 2 Simba's Pride (1998).mp4",
        "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8a%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Lion%20King%202/Lion%20King%202.mp4",
    },
    "tarzan-1": {
        "title": "Tarzan (1999) [Arabic Dub - طرزان مدبلج مصري]",
        "type": "movie",
        "dest": MOVIES_DIR / "Tarzan (1999)",
        "filename": "Tarzan (1999).mp4",
        "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8a%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Tarzan%201/Tarzan%201.mp4",
    },
    "timon-s1": {
        "title": "Timon & Pumbaa - Season 1 [Arabic Dub - تيمون وبومبا الموسم الأول كامل]",
        "type": "tv",
        "dest": TV_DIR / "Timon & Pumbaa" / "Season 01",
        "filename": "Timon & Pumbaa - S01E01-E20.mp4",
        "url": "https://archive.org/download/Temon.W.Bomba.full.season/Temon.W.Bomba.S01.mp4",
    },
    "timon-s2": {
        "title": "Timon & Pumbaa - Season 2 [Arabic Dub - تيمون وبومبا الموسم الثاني كامل]",
        "type": "tv",
        "dest": TV_DIR / "Timon & Pumbaa" / "Season 02",
        "filename": "Timon & Pumbaa - S02E01-E21.mp4",
        "url": "https://archive.org/download/Temon.W.Bomba.full.season/Temon.W.Bomba.S02.mp4",
    },
    "timon-s3": {
        "title": "Timon & Pumbaa - Season 3 [Arabic Dub - تيمون وبومبا الموسم الثالث كامل]",
        "type": "tv",
        "dest": TV_DIR / "Timon & Pumbaa" / "Season 03",
        "filename": "Timon & Pumbaa - S03E01-E25.mp4",
        "url": "https://archive.org/download/Temon.W.Bomba.full.season/Temon.W.Bomba.S03.mp4",
    },
}


def refresh_jellyfin():
    """Trigger library refresh in Jellyfin."""
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


def download_item(key: str):
    """Download an item by catalog key."""
    if key not in CATALOG:
        print(f"Unknown item key '{key}'. Available keys:")
        for k, v in CATALOG.items():
            print(f"  - {k}: {v['title']}")
        return False

    item = CATALOG[key]
    dest_dir = item["dest"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_file = dest_dir / item["filename"]

    print(f"\n==========================================")
    print(f"Starting download: {item['title']}")
    print(f"Destination: {target_file}")
    print(f"==========================================\n")

    cmd = [
        "curl",
        "-L",
        "-C",
        "-",
        "--progress-bar",
        "-o",
        str(target_file),
        item["url"],
    ]

    res = subprocess.run(cmd)
    if res.returncode == 0 and target_file.is_file() and target_file.stat().st_size > 1000000:
        print(f"\n[Success] Downloaded {item['filename']} ({target_file.stat().st_size // (1024*1024)} MB).")
        refresh_jellyfin()
        return True
    else:
        print(f"\n[Error] Download failed or file is incomplete (code {res.returncode}).")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 import_arabic.py <item-key> [or 'list']")
        print("\nAvailable titles:")
        for k, v in CATALOG.items():
            print(f"  {k:15} -> {v['title']}")
        sys.exit(0)

    arg = sys.argv[1]
    if arg == "list":
        for k, v in CATALOG.items():
            print(f"  {k:15} -> {v['title']}")
    else:
        download_item(arg)
