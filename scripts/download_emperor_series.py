#!/usr/bin/env python3
"""
Automated downloader for 'The Emperor's New School' (مدرسة الإمبراطور الجديدة) Arabic Dub.
Fetches episodes from Stardima / Hyperwatching and imports them into Jellyfin.
"""

import sys
import time
import urllib.request
import re
import subprocess
import json
import html
from pathlib import Path

DEST_BASE = Path("/media/dell/Data1/netfelix_data/media/tv/The Emperor's New School")
JELLYFIN_KEY = "4d40f90a8b854cdcbb4faa23134d057b"
JELLYFIN_AUTH = (
    'MediaBrowser Client="Jellyseerr", Device="Jellyseerr", '
    'DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="'
    + JELLYFIN_KEY
    + '"'
)
SEASON_API = "https://stardima-48.cartoon.com.im/series/season/2839?X-Requested-With=XMLHttpRequest"


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


def get_episodes_list():
    req = urllib.request.Request(
        SEASON_API,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    return data.get("episodes", [])


def extract_m3u8(ep_id):
    ep_url = f"https://stardima-48.cartoon.com.im/series/episode/{ep_id}"
    req = urllib.request.Request(
        ep_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        },
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
        raise Exception("Inertia data-page not found")
    props = json.loads(html.unescape(m.group(1)))["props"]
    servers = props["video"]["servers"]
    uqload = next((s for s in servers if s["name"].lower() == "uqload"), None)
    if not uqload:
        raise Exception("Uqload server not found")

    server_api = (
        f"https://v2.hyperwatching.com/embed/{hashid}/server/{uqload['id']}/url"
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
    if res.returncode != 0:
        raise Exception("Failed to unpack JS: " + res.stderr)

    m3u8_links = re.findall(r"https?://[^\s\"\'<>]+\.m3u8[^\s\"\'<>]*", res.stdout)
    if not m3u8_links:
        raise Exception("No m3u8 link found")
    return m3u8_links[0]


def download_episode(ep_num, ep_id):
    # Episodes 1-21 are Season 1, 22-44 are Season 2
    if ep_num <= 21:
        season_num = 1
        season_ep = ep_num
    else:
        season_num = 2
        season_ep = ep_num - 21

    dest_dir = DEST_BASE / f"Season {season_num:02d}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_file = (
        dest_dir / f"The Emperor's New School - S{season_num:02d}E{season_ep:02d}.mp4"
    )

    if target_file.is_file() and target_file.stat().st_size > 50 * 1024 * 1024:
        print(f"[Skip] Episode {ep_num} already exists ({target_file.name}).")
        return True

    print(
        f"\n[Download] Fetching Season {season_num} Ep {season_ep} (Total Ep {ep_num}, ID {ep_id})..."
    )
    for attempt in range(1, 4):
        try:
            m3u8 = extract_m3u8(ep_id)
            cmd = [
                "/home/dell/.local/bin/yt-dlp",
                "-f",
                "1448/best",
                "--add-header",
                "Referer:https://uqload.vc/",
                "-o",
                str(target_file),
                m3u8,
            ]
            res = subprocess.run(cmd)
            if (
                res.returncode == 0
                and target_file.is_file()
                and target_file.stat().st_size > 50 * 1024 * 1024
            ):
                print(
                    f"[Success] Saved {target_file.name} ({target_file.stat().st_size // (1024*1024)} MB)"
                )
                refresh_jellyfin()
                return True
            else:
                print(f"[Retry {attempt}] Download did not finish properly.")
        except Exception as e:
            print(f"[Error] Attempt {attempt} failed: {e}")
        time.sleep(3)

    return False


def main():
    episodes = get_episodes_list()
    print(f"Loaded {len(episodes)} episodes from Stardima catalog.")

    if len(sys.argv) > 1:
        # e.g., '1 5' to download episodes 1 to 5, or 'all'
        arg = sys.argv[1]
        if arg == "all":
            start, end = 1, len(episodes)
        elif "-" in arg:
            s, e = arg.split("-")
            start, end = int(s), int(e)
        else:
            start = end = int(arg)
    else:
        # Default: download first 5 episodes
        start, end = 1, 5

    print(f"Downloading episodes range: {start} to {end}")
    for ep in episodes:
        num = ep.get("episode_number")
        if start <= num <= end:
            download_episode(num, ep.get("id"))
            time.sleep(2)


if __name__ == "__main__":
    main()
