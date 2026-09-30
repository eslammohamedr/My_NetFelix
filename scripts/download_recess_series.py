#!/usr/bin/env python3
"""
Automated downloader for 'Recess' (الفسحة) Arabic Dub.
Downloads all 3 seasons (65 episodes) from Stardima / Hyperwatching.
Places into Jellyfin directory: /media/dell/Data1/netfelix_data/media/tv/Recess/
"""

import os
import sys
import time
import json
import re
import html
import subprocess
import urllib.request
from pathlib import Path

DEST_BASE = Path("/media/dell/Data1/netfelix_data/media/tv/Recess")
JELLYFIN_KEY = "4d40f90a8b854cdcbb4faa23134d057b"
JELLYFIN_AUTH = (
    'MediaBrowser Client="Jellyseerr", DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="'
    + JELLYFIN_KEY
    + '"'
)

SEASONS = [
    {"num": 1, "id": 1446, "count": 13, "start_ep_id": 33761},
    {"num": 2, "id": 1447, "count": 13, "start_ep_id": 33774},
    {"num": 3, "id": 1448, "count": 39, "start_ep_id": 33787},
]


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
        print(f"[Jellyfin] Scan note: {e}")


def get_m3u8(watch_url):
    hashid = watch_url.split("/")[-1]
    hw_headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        "Referer": "https://stardima-69.cartoon.com.im/",
    }
    req = urllib.request.Request(watch_url, headers=hw_headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        page = resp.read().decode("utf-8", errors="replace")

    m = re.search(r'data-page=[\"\'](.*?)[\"\']', page)
    if not m:
        raise Exception("data-page not found in watch page")

    props = json.loads(html.unescape(m.group(1)))["props"]
    servers = props["video"]["servers"]
    uqload = next((s for s in servers if "uqload" in s["name"].lower()), None)
    if not uqload:
        uqload = servers[0]

    server_api = f"https://v2.hyperwatching.com/embed/{hashid}/server/{uqload['id']}/url"
    req_api = urllib.request.Request(
        server_api,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": watch_url,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req_api, timeout=15) as resp:
        server_data = json.load(resp)
    embed_url = server_data["watch_url"]

    req_embed = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req_embed, timeout=15) as resp:
        embed_html = resp.read().decode("utf-8", errors="replace")

    pos = embed_html.find("eval(function(")
    if pos != -1:
        end = embed_html.find("</script>", pos)
        script_content = embed_html[pos:end].strip()
        if script_content.endswith(";"):
            script_content = script_content[:-1]
        node_script = "console.log(" + script_content[5:-1] + ");"
        res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        m3u8_links = re.findall(r"https?://[^\s\"\'<>]+\.m3u8[^\s\"\'<>]*", res.stdout)
        if m3u8_links:
            return m3u8_links[0]

    m3u8_links = re.findall(r"https?://[^\s\"\'<>]+\.m3u8[^\s\"\'<>]*", embed_html)
    if m3u8_links:
        return m3u8_links[0]
    raise Exception("m3u8 link not found in embed")


def download_episode(season_num, ep_num, ep_id):
    season_dir = DEST_BASE / f"Season {season_num:02d}"
    season_dir.mkdir(parents=True, exist_ok=True)
    target_file = season_dir / f"Recess - S{season_num:02d}E{ep_num:02d}.mp4"

    if target_file.exists() and target_file.stat().st_size > 20 * 1024 * 1024:
        print(f"[SKIP] S{season_num:02d}E{ep_num:02d} exists ({target_file.stat().st_size / (1024*1024):.1f} MB).")
        return True

    print(f"\n[FETCH] Resolving S{season_num:02d}E{ep_num:02d} (ID: {ep_id})...")
    ep_url = f"https://stardima-69.cartoon.com.im/series/episode/{ep_id}"
    req = urllib.request.Request(
        ep_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        ep_data = json.load(resp)
    watch_url = ep_data["episode"]["watch_url"]

    m3u8_url = get_m3u8(watch_url)
    print(f"[DOWNLOAD] Downloading S{season_num:02d}E{ep_num:02d}...")

    temp_file = target_file.with_suffix(".temp.mp4")
    cmd = [
        "yt-dlp",
        "--no-warning",
        "-q",
        "--progress",
        "-o",
        str(temp_file),
        m3u8_url,
    ]
    p = subprocess.run(cmd)
    if p.returncode == 0 and temp_file.exists() and temp_file.stat().st_size > 5 * 1024 * 1024:
        temp_file.rename(target_file)
        print(f"[SUCCESS] S{season_num:02d}E{ep_num:02d} saved ({target_file.stat().st_size / (1024*1024):.1f} MB).")
        return True
    else:
        print(f"[FAIL] Download failed for S{season_num:02d}E{ep_num:02d}.")
        if temp_file.exists():
            temp_file.unlink()
        return False


def main():
    print("=" * 60)
    print("Starting Recess (الفسحة) Arabic Dub Downloader")
    print("=" * 60)

    total_downloaded = 0
    for s in SEASONS:
        season_num = s["num"]
        count = s["count"]
        start_id = s["start_ep_id"]
        print(f"\n>>> Processing Season {season_num} ({count} episodes) <<<")
        for i in range(count):
            ep_num = i + 1
            ep_id = start_id + i
            try:
                ok = download_episode(season_num, ep_num, ep_id)
                if ok:
                    total_downloaded += 1
                if total_downloaded > 0 and total_downloaded % 5 == 0:
                    refresh_jellyfin()
                time.sleep(1)
            except Exception as e:
                print(f"[ERROR] Failed S{season_num:02d}E{ep_num:02d}: {e}")
                time.sleep(3)

    refresh_jellyfin()
    print(f"\nAll downloads finished! Total episodes ready: {total_downloaded}")


if __name__ == "__main__":
    main()
