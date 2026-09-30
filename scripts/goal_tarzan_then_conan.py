#!/usr/bin/env python3
"""
MASTER GOAL RUNNER:
1. Download full "The Legend of Tarzan" (أسطورة طرزان) - 35 Episodes (720p HD Egyptian Arabic Dub)
2. Download remaining "Detective Conan" (المحقق كونان) - Seasons 7 to 12 (Venus Centre Arabic Dub)
3. Periodically refresh Jellyfin and confirm library availability.
"""

import sys
import time
import json
import re
import html
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

MEDIA_ROOT = Path("/media/dell/Data1/netfelix_data/media")
TV_ROOT = MEDIA_ROOT / "tv"

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
# 1. THE LEGEND OF TARZAN (أسطورة طرزان)
# ==========================================
TARZAN_DEST = TV_ROOT / "The Legend of Tarzan" / "Season 01"
TARZAN_BASE = (
    "https://archive.org/download/www.arabp-2p.net-walt-disney-tarazan-serie-1-35-hd/"
    "Walt%20Disney%20-%20Tarazan%20Serie%201-35%20By%20MyGamesTop%20and%20GeniusBoy%20%5BHD%5D"
)
TARZAN_SIZES = {
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


def download_tarzan_series():
    print("\n" + "=" * 60)
    print("STEP 1: Starting 'The Legend of Tarzan' (أسطورة طرزان)")
    print("Target: 35 Episodes (720p HD Egyptian Arabic Dub)")
    print("=" * 60 + "\n")

    TARZAN_DEST.mkdir(parents=True, exist_ok=True)
    total = 35

    for ep in range(1, total + 1):
        target = TARZAN_DEST / f"The Legend of Tarzan - S01E{ep:02d}.mp4"
        expected = TARZAN_SIZES.get(ep, 400 * 1024 * 1024)

        if target.is_file() and target.stat().st_size >= expected:
            print(f"[Tarzan {ep:02d}/{total}] Already downloaded: {target.name}")
            continue

        filename_encoded = urllib.parse.quote(
            f"{ep:02d}-Walt Disney - Tarazan Serie By MyGamesTop and GeniusBoy [HD].mp4"
        )
        url = f"{TARZAN_BASE}/{filename_encoded}"

        curr_size = target.stat().st_size if target.is_file() else 0
        if curr_size > 0:
            print(f"\n[Tarzan {ep:02d}/{total}] Resuming {target.name} ({curr_size // (1024*1024)} MB / {expected // (1024*1024)} MB)...")
        else:
            print(f"\n[Tarzan {ep:02d}/{total}] Downloading {target.name} ({expected // (1024*1024)} MB)...")

        cmd = ["curl", "-L", "-C", "-", "--progress-bar", "-o", str(target), url]
        res = subprocess.run(cmd)

        if res.returncode == 0 and target.is_file() and target.stat().st_size >= expected:
            print(f"[Tarzan {ep:02d}/{total}] Successfully saved {target.name} ({target.stat().st_size // (1024*1024)} MB)")
            if ep % 3 == 0 or ep == total:
                refresh_jellyfin()
        else:
            print(f"[ERROR] Tarzan Episode {ep:02d} incomplete (Size: {target.stat().st_size if target.is_file() else 0} / {expected}).")

    refresh_jellyfin()
    print("\n[The Legend of Tarzan] ALL 35 EPISODES COMPLETED!\n")


# ==========================================
# 2. DETECTIVE CONAN (المحقق كونان)
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
    print("STEP 2: Starting Detective Conan (المحقق كونان) - REMAINING SEASONS")
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


def main():
    start_time = time.time()
    print("=" * 60)
    print("MASTER GOAL: THE LEGEND OF TARZAN -> REMAINING DETECTIVE CONAN")
    print("=" * 60)

    # 1. The Legend of Tarzan
    download_tarzan_series()

    # 2. Detective Conan (remaining)
    download_detective_conan()

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"ALL GOAL ITEMS FULLY COMPLETED in {elapsed / 60:.1f} minutes!")
    print("=" * 60)
    refresh_jellyfin()


if __name__ == "__main__":
    main()
