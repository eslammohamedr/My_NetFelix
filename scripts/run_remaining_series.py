#!/usr/bin/env python3
"""
MASTER CONTINUATION RUNNER (OPTIMIZED):
Downloads all remaining episodes of:
1. Recess (الفسحة)
2. Lilo & Stitch: The Series (مسلسل ليلو وستيتش)
3. Kim Possible (مسلسل دامو ستحيل)

Fast skip on 404 dead links, resilient on network drops.
"""

import os
import sys
import time
import json
import re
import html
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

BASE_MEDIA = Path("/media/dell/Data1/netfelix_data/media/tv")
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
        print(f"[Jellyfin] Scan note: {e}")


def safe_urlopen(req, timeout=10, max_retries=3):
    for attempt in range(max_retries):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as he:
            # 404 or 403 or 410 is permanent, do not retry!
            if he.code in (404, 403, 410):
                raise he
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise he
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise e


def get_m3u8(watch_url):
    hashid = watch_url.split("/")[-1]
    hw_headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        "Referer": "https://stardima-69.cartoon.com.im/",
    }
    req = urllib.request.Request(watch_url, headers=hw_headers)
    with safe_urlopen(req, timeout=10) as resp:
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
    with safe_urlopen(req_api, timeout=10) as resp:
        server_data = json.load(resp)
    embed_url = server_data["watch_url"]

    req_embed = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
    with safe_urlopen(req_embed, timeout=10) as resp:
        embed_html = resp.read().decode("utf-8", errors="replace")

    if "File was locked" in embed_html or "File Not Found" in embed_html or "File was deleted" in embed_html:
        raise Exception("File is locked/deleted on host")

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


def download_single_ep(dest_dir, filename, ep_id):
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_file = dest_dir / filename

    if target_file.exists() and target_file.stat().st_size > 20 * 1024 * 1024:
        return "EXISTS"

    print(f"\n[FETCH] Resolving {filename} (ID: {ep_id})...")
    ep_url = f"https://stardima-69.cartoon.com.im/series/episode/{ep_id}"
    req = urllib.request.Request(
        ep_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with safe_urlopen(req, timeout=10) as resp:
        ep_data = json.load(resp)
    watch_url = ep_data["episode"]["watch_url"]

    m3u8_url = get_m3u8(watch_url)
    print(f"[DOWNLOAD] Downloading {filename}...")

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
        print(f"[SUCCESS] {filename} saved ({target_file.stat().st_size / (1024*1024):.1f} MB).")
        return "SUCCESS"
    else:
        print(f"[FAIL] Download failed for {filename}.")
        if temp_file.exists():
            temp_file.unlink()
        return "FAILED"


def run_recess():
    print("\n" + "=" * 60)
    print("CHECKING & COMPLETING RECESS (الفسحة)")
    print("=" * 60)
    dest_base = BASE_MEDIA / "Recess"
    seasons = [
        {"num": 1, "count": 13, "start_ep_id": 33761},
        {"num": 2, "count": 13, "start_ep_id": 33774},
        {"num": 3, "count": 39, "start_ep_id": 33787},
    ]

    for s in seasons:
        s_num = s["num"]
        s_dir = dest_base / f"Season {s_num:02d}"
        for i in range(s["count"]):
            ep_num = i + 1
            ep_id = s["start_ep_id"] + i
            fn = f"Recess - S{s_num:02d}E{ep_num:02d}.mp4"
            try:
                res = download_single_ep(s_dir, fn, ep_id)
                if res == "SUCCESS":
                    time.sleep(1)
            except Exception as e:
                print(f"[SKIP/DEAD] Recess S{s_num:02d}E{ep_num:02d}: {e}")


def run_lilo():
    print("\n" + "=" * 60)
    print("DOWNLOADING LILO & STITCH: THE SERIES (مسلسل ليلو وستيتش)")
    print("=" * 60)
    dest_base = BASE_MEDIA / "Lilo & Stitch: The Series"
    seasons = [
        {"num": 1, "count": 39, "start_ep_id": 35112},
        {"num": 2, "count": 26, "start_ep_id": 35151},
    ]

    downloaded = 0
    for s in seasons:
        s_num = s["num"]
        s_dir = dest_base / f"Season {s_num:02d}"
        for i in range(s["count"]):
            ep_num = i + 1
            ep_id = s["start_ep_id"] + i
            fn = f"Lilo & Stitch - S{s_num:02d}E{ep_num:02d}.mp4"
            try:
                res = download_single_ep(s_dir, fn, ep_id)
                if res == "SUCCESS":
                    downloaded += 1
                    if downloaded % 5 == 0:
                        refresh_jellyfin()
                    time.sleep(1)
            except Exception as e:
                print(f"[SKIP/DEAD] Lilo S{s_num:02d}E{ep_num:02d}: {e}")


def run_kim_possible():
    print("\n" + "=" * 60)
    print("DOWNLOADING KIM POSSIBLE (دامو ستحيل)")
    print("=" * 60)
    dest_base = BASE_MEDIA / "Kim Possible"

    url = "https://stardima-69.cartoon.com.im/series/season/3769"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with safe_urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    episodes = data.get("episodes", [])

    downloaded = 0
    for idx, ep in enumerate(episodes):
        ep_num = idx + 1
        ep_id = ep["id"]
        if ep_num <= 21:
            s_num = 1
            s_ep = ep_num
        elif ep_num <= 51:
            s_num = 2
            s_ep = ep_num - 21
        else:
            s_num = 3
            s_ep = ep_num - 51

        s_dir = dest_base / f"Season {s_num:02d}"
        fn = f"Kim Possible - S{s_num:02d}E{s_ep:02d}.mp4"
        try:
            res = download_single_ep(s_dir, fn, ep_id)
            if res == "SUCCESS":
                downloaded += 1
                if downloaded % 5 == 0:
                    refresh_jellyfin()
                time.sleep(1)
        except Exception as e:
            print(f"[SKIP/DEAD] Kim Possible ep {ep_num} (ID {ep_id}): {e}")


def main():
    print("Starting master continuation runner (Fast & Resilient)...")
    run_recess()
    refresh_jellyfin()

    run_lilo()
    refresh_jellyfin()

    run_kim_possible()
    refresh_jellyfin()

    print("\n" + "=" * 60)
    print("ALL SERIES DOWNLOADS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
