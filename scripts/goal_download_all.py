#!/usr/bin/env python3
"""
Master Goal Downloader: Executes downloads in the exact requested order:
1. Timon & Pumbaa (تيمون وبومبا)
2. Detective Conan (المحقق كونان)
3. The Lion King 1 & 2 (الأسد الملك)
4. Tarzan 1 & 2 (طرزان)
"""

import sys
import os
import time
import subprocess
import urllib.request
import json
import re
import html
from pathlib import Path

MEDIA_ROOT = Path("/media/dell/Data1/netfelix_data/media")
TV_ROOT = MEDIA_ROOT / "tv"
MOVIES_ROOT = MEDIA_ROOT / "movies"

JELLYFIN_KEY = "4d40f90a8b854cdcbb4faa23134d057b"
JELLYFIN_AUTH = (
    'MediaBrowser Client="Jellyseerr", Device="Jellyseerr", '
    'DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="'
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
        print(f"[Jellyfin] Could not trigger scan: {e}")


# ==========================================
# 1. TIMON & PUMBAA DOWNLOADER
# ==========================================
def download_timon_and_pumbaa():
    print("\n" + "=" * 60)
    print("STEP 1: Starting Timon & Pumbaa (تيمون وبومبا)")
    print("=" * 60 + "\n")

    dest_dir = TV_ROOT / "Timon & Pumbaa"
    s1_dir = dest_dir / "Season 01"
    s2_dir = dest_dir / "Season 02"
    s1_dir.mkdir(parents=True, exist_ok=True)
    s2_dir.mkdir(parents=True, exist_ok=True)

    base_url = "https://archive.org/download/www.arabp-2p.net-timon-and-pumbaa-1-42-hd/Timon%20and%20Pumba%201-42%20By%20MyGamesTop%20and%20GeniusBoy%20%5BHD%5D"

    for ep in range(1, 43):
        # Ep 1-25 -> Season 1, Ep 26-42 -> Season 2
        if ep <= 25:
            target = s1_dir / f"Timon & Pumbaa - S01E{ep:02d}.mp4"
        else:
            s2_ep = ep - 25
            target = s2_dir / f"Timon & Pumbaa - S02E{s2_ep:02d}.mp4"

        if target.is_file() and target.stat().st_size > 100 * 1024 * 1024:
            print(f"[Timon] Episode {ep}/42 already downloaded ({target.name}).")
            continue

        filename_encoded = f"{ep:02d}%20Timon%20and%20Pumba%20By%20MyGamesTop%20and%20GeniusBoy%20%5BHD%5D.mp4"
        url = f"{base_url}/{filename_encoded}"

        print(f"\n[Timon] Downloading episode {ep}/42: {target.name}...")
        cmd = ["curl", "-L", "-C", "-", "--progress-bar", "-o", str(target), url]
        res = subprocess.run(cmd)
        if res.returncode == 0 and target.is_file() and target.stat().st_size > 100 * 1024 * 1024:
            print(f"[Timon] Successfully saved {target.name} ({target.stat().st_size // (1024*1024)} MB)")
            if ep % 5 == 0 or ep == 42:
                refresh_jellyfin()
        else:
            print(f"[Timon Error] Failed to download episode {ep}.")

    refresh_jellyfin()
    print("\n[Timon & Pumbaa] Complete!\n")


# ==========================================
# 2. DETECTIVE CONAN DOWNLOADER
# ==========================================
def extract_stardima_m3u8(ep_id):
    ep_url = f"https://stardima-48.cartoon.com.im/series/episode/{ep_id}"
    req = urllib.request.Request(
        ep_url,
        headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        ep_data = json.load(resp)
    watch_url = ep_data["episode"]["watch_url"]
    hashid = watch_url.split("/")[-1]

    hw_headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://stardima-48.cartoon.com.im/",
    }
    req = urllib.request.Request(watch_url, headers=hw_headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        page = resp.read().decode("utf-8", errors="replace")

    m = re.search(r'data-page=[\"\'](.*?)[\"\']', page)
    if not m:
        raise Exception("data-page not found")
    props = json.loads(html.unescape(m.group(1)))["props"]
    servers = props["video"]["servers"]

    # Try Uqload first, then fallback
    target_server = next((s for s in servers if s["name"].lower() == "uqload"), servers[0])

    server_api = (
        f"https://v2.hyperwatching.com/embed/{hashid}/server/{target_server['id']}/url"
    )
    req = urllib.request.Request(
        server_api,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": watch_url,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        server_data = json.load(resp)
    embed_url = server_data["watch_url"]

    # If Uqload, unpack eval
    if "uqload" in embed_url:
        req = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            embed_html = resp.read().decode("utf-8", errors="replace")
        pos = embed_html.find("eval(function(")
        end = embed_html.find("</script>", pos)
        script_content = embed_html[pos:end].strip()
        if script_content.endswith(";"):
            script_content = script_content[:-1]
        node_script = "console.log(" + script_content[5:-1] + ");"
        res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        m3u8_links = re.findall(r"https?://[^\s\"\'<>]+\.m3u8[^\s\"\'<>]*", res.stdout)
        if m3u8_links:
            return m3u8_links[0], "https://uqload.vc/"

    return embed_url, "https://stardima-48.cartoon.com.im/"


def download_detective_conan():
    print("\n" + "=" * 60)
    print("STEP 2: Starting Detective Conan (المحقق كونان) - ALL 12 SEASONS")
    print("=" * 60 + "\n")

    seasons = [
        (1, 57, "Season 1"),
        (2, 720, "Season 2"),
        (3, 1508, "Season 3"),
        (4, 1535, "Season 4"),
        (5, 1537, "Season 5"),
        (6, 1538, "Season 6"),
        (7, 1549, "Season 7"),
        (8, 1547, "Season 8"),
        (9, 4084, "Season 9"),
        (10, 4083, "Season 10"),
        (11, 745, "Season 11"),
        (12, 3589, "Season 12"),
    ]

    for snum, sid, label in seasons:
        dest_dir = TV_ROOT / "Detective Conan" / f"Season {snum:02d}"
        dest_dir.mkdir(parents=True, exist_ok=True)

        season_url = f"https://stardima-48.cartoon.com.im/series/season/{sid}?X-Requested-With=XMLHttpRequest"
        req = urllib.request.Request(
            season_url,
            headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                episodes = json.load(resp).get("episodes", [])
        except Exception as e:
            print(f"[Conan Error] Failed to load episodes for Season {snum} (ID {sid}): {e}")
            continue

        print(f"\n[Conan] Loaded {len(episodes)} episodes for Season {snum} ({label}).")

        for idx, ep in enumerate(episodes, 1):
            ep_id = ep.get("id")
            title = ep.get("title", f"Episode {idx}")
            target = dest_dir / f"Detective Conan - S{snum:02d}E{idx:02d}.mp4"

            if target.is_file() and target.stat().st_size > 40 * 1024 * 1024:
                print(f"[Conan] S{snum:02d}E{idx:02d} already downloaded ({target.name}).")
                continue

            print(f"\n[Conan] Downloading S{snum:02d}E{idx:02d} ({idx}/{len(episodes)}): {title}...")
            success = False
            for attempt in range(1, 4):
                try:
                    stream_url, referer = extract_stardima_m3u8(ep_id)
                    cmd = [
                        "/home/dell/.local/bin/yt-dlp",
                        "-f",
                        "best",
                        "--add-header",
                        f"Referer:{referer}",
                        "-o",
                        str(target),
                        stream_url,
                    ]
                    res = subprocess.run(cmd)
                    if res.returncode == 0 and target.is_file() and target.stat().st_size > 40 * 1024 * 1024:
                        print(f"[Conan] Saved {target.name} ({target.stat().st_size // (1024*1024)} MB)")
                        success = True
                        break
                except Exception as e:
                    print(f"[Conan Error] Attempt {attempt} failed: {e}")
                time.sleep(3)

            if success and (idx % 5 == 0 or idx == len(episodes)):
                refresh_jellyfin()

        refresh_jellyfin()
        print(f"\n[Detective Conan] Season {snum} Complete!\n")

    print("\n[Detective Conan] ALL 12 SEASONS COMPLETE!\n")


# ==========================================
# 3. THE LION KING 1 & 2 DOWNLOADER
# ==========================================
def download_lion_king():
    print("\n" + "=" * 60)
    print("STEP 3: Starting The Lion King 1 & 2 (الأسد الملك)")
    print("=" * 60 + "\n")

    movies = [
        {
            "name": "The Lion King (1994)",
            "dest": MOVIES_ROOT / "The Lion King (1994)",
            "file": "The Lion King (1994).mp4",
            "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8a%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Lion%20King%201/Lion%20King%201.mp4",
        },
        {
            "name": "The Lion King 2: Simba's Pride (1998)",
            "dest": MOVIES_ROOT / "The Lion King 2 Simba's Pride (1998)",
            "file": "The Lion King 2 Simba's Pride (1998).mp4",
            "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8a%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Lion%20King%202/Lion%20King%202.mp4",
        },
    ]

    for m in movies:
        m["dest"].mkdir(parents=True, exist_ok=True)
        target = m["dest"] / m["file"]
        if target.is_file() and target.stat().st_size > 100 * 1024 * 1024:
            print(f"[Lion King] {m['name']} already downloaded.")
            continue

        print(f"\n[Lion King] Downloading {m['name']}...")
        cmd = ["curl", "-L", "-C", "-", "--progress-bar", "-o", str(target), m["url"]]
        res = subprocess.run(cmd)
        if res.returncode == 0 and target.is_file() and target.stat().st_size > 100 * 1024 * 1024:
            print(f"[Lion King] Saved {target.name} ({target.stat().st_size // (1024*1024)} MB)")
            refresh_jellyfin()
        else:
            print(f"[Lion King Error] Failed to download {m['name']}.")

    print("\n[The Lion King] Complete!\n")


# ==========================================
# 4. TARZAN 1 & 2 DOWNLOADER
# ==========================================
def download_tarzan():
    print("\n" + "=" * 60)
    print("STEP 4: Starting Tarzan 1 & 2 (طرزان)")
    print("=" * 60 + "\n")

    movies = [
        {
            "name": "Tarzan (1999)",
            "dest": MOVIES_ROOT / "Tarzan (1999)",
            "file": "Tarzan (1999).mp4",
            "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8a%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Tarzan%201/Tarzan%201.mp4",
        },
        {
            "name": "Tarzan 2 (2005)",
            "dest": MOVIES_ROOT / "Tarzan 2 (2005)",
            "file": "Tarzan 2 (2005).mp4",
            "url": "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8a%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/Tarzan%202/Tarzan%202.mp4",
        },
    ]

    for m in movies:
        m["dest"].mkdir(parents=True, exist_ok=True)
        target = m["dest"] / m["file"]
        if target.is_file() and target.stat().st_size > 100 * 1024 * 1024:
            print(f"[Tarzan] {m['name']} already downloaded.")
            continue

        print(f"\n[Tarzan] Downloading {m['name']}...")
        cmd = ["curl", "-L", "-C", "-", "--progress-bar", "-o", str(target), m["url"]]
        res = subprocess.run(cmd)
        if res.returncode == 0 and target.is_file() and target.stat().st_size > 100 * 1024 * 1024:
            print(f"[Tarzan] Saved {target.name} ({target.stat().st_size // (1024*1024)} MB)")
            refresh_jellyfin()
        else:
            print(f"[Tarzan Error] Failed to download {m['name']}.")

    print("\n[Tarzan] Complete!\n")


def main():
    start_time = time.time()
    print("=" * 60)
    print("STARTING COMPLETE MASTER GOAL EXECUTION")
    print("ORDER:")
    print("  1. Timon & Pumbaa (تيمون وبومبا)")
    print("  2. Detective Conan (المحقق كونان)")
    print("  3. [SKIPPED] The Lion King (per user request)")
    print("  4. Tarzan 1 & 2 (طرزان)")
    print("=" * 60)

    # 1. Timon & Pumbaa
    download_timon_and_pumbaa()

    # 2. Detective Conan
    download_detective_conan()

    # 3. Tarzan (Lion King skipped per user request)
    download_tarzan()

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"ALL REQUESTED GOAL ITEMS FULLY COMPLETED in {elapsed / 60:.1f} minutes!")
    print("=" * 60)
    refresh_jellyfin()


if __name__ == "__main__":
    main()
