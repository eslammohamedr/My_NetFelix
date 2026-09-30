#!/usr/bin/env python3
"""
Downloader for Disney Classic Movies in Arabic Dub (Egyptian Arabic where available).
- The Little Mermaid (1989) [اريال - ديزني بالمصري]
- The Little Mermaid II: Return to the Sea (2000) [حورية البحر 2 مدبلج مصري]
- Lilo & Stitch (2002) [ليلو وستيتش - ديزني بالمصري]
- Lilo & Stitch 2: Stitch Has a Glitch (2005) [ليلو وستيتش 2 مدبلج]
- Kim Possible: So the Drama (2005) [فيلم دامو ستحيل: رحلة درامية]
"""

import os
import sys
import time
import urllib.request
import urllib.parse
import subprocess
from pathlib import Path

BASE_DIR = Path("/media/dell/Data1/netfelix_data/media/movies")

MOVIES = [
    {
        "id": "mermaid_1",
        "title": "The Little Mermaid (1989)",
        "dest_dir": BASE_DIR / "The Little Mermaid (1989)",
        "filename": "The Little Mermaid (1989).mp4",
        "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8A%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/The%20Little%20Mermaid%20I/The%20Little%20Mermaid%20I.mp4",
        "expected_size": 452308876,
    },
    {
        "id": "mermaid_2",
        "title": "The Little Mermaid II Return to the Sea (2000)",
        "dest_dir": BASE_DIR / "The Little Mermaid II Return to the Sea (2000)",
        "filename": "The Little Mermaid II Return to the Sea (2000).mp4",
        "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8A%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/The%20Little%20Mermaid%20II/The%20Little%20Mermaid%20II.mp4",
        "expected_size": 408012642,
    },
    {
        "id": "lilo_1",
        "title": "Lilo & Stitch (2002)",
        "dest_dir": BASE_DIR / "Lilo & Stitch (2002)",
        "filename": "Lilo & Stitch (2002).mp4",
        "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8A%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Lilo%20And%20Stitch%201/Lilo%20And%20Stitch%201.mp4",
        "expected_size": 470235690,
    },
    {
        "id": "lilo_2",
        "title": "Lilo & Stitch 2 Stitch Has a Glitch (2005)",
        "dest_dir": BASE_DIR / "Lilo & Stitch 2 Stitch Has a Glitch (2005)",
        "filename": "Lilo & Stitch 2 Stitch Has a Glitch (2005).mp4",
        "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8A%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Lilo%20And%20Stitch%202/Lilo%20And%20Stitch%202.mp4",
        "expected_size": 348575027,
    },
    {
        "id": "kim_drama",
        "title": "Kim Possible So the Drama (2005)",
        "dest_dir": BASE_DIR / "Kim Possible So the Drama (2005)",
        "filename": "Kim Possible So the Drama (2005).mp4",
        "url": "https://archive.org/download/KimPossibleSoTheDrama2005ARABHD/%D9%81%D9%8A%D9%84%D9%85%20Kim%20Possible_%20So%20the%20Drama%202005%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20_%20%D8%B9%D8%B1%D8%A8%20%D8%A7%D8%AA%D8%B4%20%D8%AF%D9%8A%20-%20ARAB%20HD.mp4",
        "expected_size": 416568309,
    },
]


def download_file(url, target_path, expected_size=None):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".part")

    downloaded = 0
    if temp_path.exists():
        downloaded = temp_path.stat().st_size

    if target_path.exists():
        cur_sz = target_path.stat().st_size
        if expected_size and cur_sz >= expected_size * 0.98:
            print(f"[SKIP] {target_path.name} already exists ({cur_sz / (1024*1024):.1f} MB).")
            return True
        elif not expected_size and cur_sz > 50 * 1024 * 1024:
            print(f"[SKIP] {target_path.name} exists ({cur_sz / (1024*1024):.1f} MB).")
            return True

    print(f"\n[START] Downloading {target_path.name}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"
        print(f"  Resuming from {downloaded / (1024*1024):.1f} MB")

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(temp_path, "ab" if downloaded > 0 else "wb") as out_f:
            total_sz = resp.headers.get("Content-Length")
            if total_sz:
                total_sz = int(total_sz) + downloaded
            else:
                total_sz = expected_size

            start_t = time.time()
            last_p = start_t
            bytes_since = 0

            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                bytes_since += len(chunk)

                now = time.time()
                if now - last_p >= 3.0:
                    speed = bytes_since / (now - last_p) / (1024 * 1024)
                    pct = (downloaded / total_sz * 100) if total_sz else 0
                    print(f"  Progress: {pct:.1f}% ({downloaded / (1024*1024):.1f} MB) @ {speed:.2f} MB/s", flush=True)
                    last_p = now
                    bytes_since = 0

        # Rename temp to target
        temp_path.rename(target_path)
        print(f"[SUCCESS] Saved to {target_path} ({target_path.stat().st_size / (1024*1024):.1f} MB).")
        return True

    except Exception as e:
        print(f"[ERROR] Download failed for {target_path.name}: {e}")
        return False


def refresh_jellyfin():
    key = "4d40f90a8b854cdcbb4faa23134d057b"
    auth = f'MediaBrowser Client="Jellyseerr", DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="{key}"'
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8096/Library/Refresh",
            data=b"",
            headers={"Authorization": auth},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[Jellyfin] Library scan triggered (Status {resp.status}).")
    except Exception as e:
        print(f"[Jellyfin] Could not trigger scan: {e}")


def main():
    print(f"Starting download of {len(MOVIES)} Disney Arabic dub movies...")
    for m in MOVIES:
        target_file = m["dest_dir"] / m["filename"]
        success = download_file(m["url"], target_file, m.get("expected_size"))
        if success:
            # Quick probe
            try:
                p = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height", "-of", "json", str(target_file)],
                    capture_output=True,
                    text=True,
                )
                print(f"  Probe OK for {m['title']}")
            except Exception as e:
                print(f"  Probe note: {e}")

    refresh_jellyfin()
    print("\nAll movie downloads complete!")


if __name__ == "__main__":
    main()
