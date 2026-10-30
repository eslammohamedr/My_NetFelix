#!/usr/bin/env python3
"""
NetFelix Sports & Match-Day Scraper
Scrapes today's matches, commentators, channels, and tournament info,
and generates dynamic M3U playlists with beIN Sports, SSC, and live match feeds for Jellyfin and Samsung TV.
"""

import os
import re
import sys
import json
import time
import logging
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
from collections import defaultdict
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
SPORTS_SOURCES_FILE = CONFIG_DIR / "sports_sources.json"
DATA_MEDIA_DIR = Path("/media/dell/Data1/netfelix_data/media")
SPORTS_M3U_FILE = DATA_MEDIA_DIR / "sports_matches.m3u"
NILESAT_M3U_FILE = DATA_MEDIA_DIR / "nilesat_egypt.m3u"
SERVER_IP = "192.168.1.15"
SERVER_PORT = "8092"

CHANNEL_MAP = {
    "bein1": {
        "name": "beIN Sports 1 HD",
        "ar_name": "بي إن سبورتس 1 HD (Match Channel)",
        "logo": "https://i.imgur.com/Vtk2cGI.png",
        "tvg_id": "beINSports1.qa",
        "aliases": ["بي إن سبورت 1", "بي ان سبورت 1", "bein sports 1", "bein 1"]
    },
    "bein2": {
        "name": "beIN Sports 2 HD",
        "ar_name": "بي إن سبورتس 2 HD (Match Channel)",
        "logo": "https://i.imgur.com/vUJZSvs.png",
        "tvg_id": "beINSports2.qa",
        "aliases": ["بي إن سبورت 2", "بي ان سبورت 2", "bein sports 2", "bein 2"]
    },
    "bein3": {
        "name": "beIN Sports 3 HD",
        "ar_name": "بي إن سبورتس 3 HD (Match Channel)",
        "logo": "https://i.imgur.com/UYSMao3.png",
        "tvg_id": "beINSports3.qa",
        "aliases": ["بي إن سبورت 3", "بي ان سبورت 3", "bein sports 3", "bein 3"]
    },
    "bein4": {
        "name": "beIN Sports 4 HD",
        "ar_name": "بي إن سبورتس 4 HD (Match Channel)",
        "logo": "https://i.imgur.com/vwAgJNi.png",
        "tvg_id": "beINSports4.qa",
        "aliases": ["بي إن سبورت 4", "بي ان سبورت 4", "bein sports 4", "bein 4"]
    },
    "bein5": {
        "name": "beIN Sports 5 HD",
        "ar_name": "بي إن سبورتس 5 HD (Match Channel)",
        "logo": "https://i.imgur.com/2Rha5aY.png",
        "tvg_id": "beINSports5.qa",
        "aliases": ["بي إن سبورت 5", "بي ان سبورت 5", "bein sports 5", "bein 5"]
    },
    "bein6": {
        "name": "beIN Sports 6 HD",
        "ar_name": "بي إن سبورتس 6 HD (Match Channel)",
        "logo": "https://i.imgur.com/0wBdLYb.png",
        "tvg_id": "beINSports6.qa",
        "aliases": ["بي إن سبورت 6", "بي ان سبورت 6", "bein sports 6", "bein 6"]
    },
    "bein7": {
        "name": "beIN Sports 7 HD",
        "ar_name": "بي إن سبورتس 7 HD (Match Channel)",
        "logo": "https://i.imgur.com/iODFwZi.png",
        "tvg_id": "beINSports7.qa",
        "aliases": ["بي إن سبورت 7", "بي ان سبورت 7", "bein sports 7", "bein 7"]
    },
    "bein8": {
        "name": "beIN Sports 8 HD",
        "ar_name": "بي إن سبورتس 8 HD (Match Channel)",
        "logo": "https://i.imgur.com/CaFEyVn.png",
        "tvg_id": "beINSports8.qa",
        "aliases": ["بي إن سبورت 8", "بي ان سبورت 8", "bein sports 8", "bein 8"]
    },
    "bein_news": {
        "name": "beIN Sports News HD",
        "ar_name": "بي إن سبورتس الإخبارية HD",
        "logo": "https://i.imgur.com/mE8G4cM.png",
        "tvg_id": "beINSportsNews.qa",
        "aliases": ["بي إن سبورت الإخبارية", "bein sports news", "بي ان سبورتس الاخبارية"],
        "default_stream": "https://shd-amg-fast.edgenextcdn.net/tx001/playlist.m3u8"
    },
    "bein_xtra1": {
        "name": "beIN Sports Xtra 1",
        "ar_name": "بي إن سبورتس إكسترا 1",
        "logo": "https://i.imgur.com/Vtk2cGI.png",
        "tvg_id": "beINXtra1.qa",
        "aliases": ["bein xtra 1", "بي ان اكسترا 1", "بي إن إكسترا 1"]
    },
    "bein_xtra2": {
        "name": "beIN Sports Xtra 2",
        "ar_name": "بي إن سبورتس إكسترا 2",
        "logo": "https://i.imgur.com/Vtk2cGI.png",
        "tvg_id": "beINXtra2.qa",
        "aliases": ["bein xtra 2", "بي ان اكسترا 2", "بي إن إكسترا 2"]
    },
    "alkass1": {
        "name": "Alkass One HD",
        "ar_name": "قناة الكأس 1 HD",
        "logo": "https://i.imgur.com/alkass.png",
        "tvg_id": "AlkassOne.qa",
        "aliases": ["الكأس 1", "قناة الكأس 1", "alkass 1"]
    },
    "ontime1": {
        "name": "On Time Sports 1 HD",
        "ar_name": "أون تايم سبورتس 1 HD",
        "logo": "https://i.imgur.com/ontime.png",
        "tvg_id": "OnTimeSports1.eg",
        "aliases": ["on time sports", "أون تايم سبورت", "on sport plus", "on sport 1"]
    },
    "ssc": {
        "name": "SSC Sports HD",
        "ar_name": "قنوات SSC الرياضية السعودية",
        "logo": "https://i.imgur.com/7123912.png",
        "tvg_id": "SSCSport1.sa",
        "aliases": ["قنوات ثمانية", "ssc", "ssc 1", "ssc sport"]
    }
}

DEFAULT_SOURCES = {
    "bein_news": "https://shd-amg-fast.edgenextcdn.net/tx001/playlist.m3u8",
    "bein1": "",
    "bein2": "",
    "bein3": "",
    "bein4": "",
    "bein5": "",
    "bein6": "",
    "bein7": "",
    "bein8": "",
    "bein_xtra1": "",
    "bein_xtra2": "",
    "alkass1": "",
    "ontime1": "",
    "ssc": ""
}

def load_sources():
    if SPORTS_SOURCES_FILE.exists():
        try:
            with open(SPORTS_SOURCES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading {SPORTS_SOURCES_FILE}: {e}")
    save_sources(DEFAULT_SOURCES)
    return DEFAULT_SOURCES

def save_sources(sources):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SPORTS_SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False)

def resolve_channel_id(ch_str):
    if not ch_str:
        return None
    c_lower = ch_str.strip().lower()
    for ch_id, info in CHANNEL_MAP.items():
        for alias in info["aliases"]:
            if alias.lower() in c_lower or c_lower in alias.lower():
                return ch_id
    return None

def fetch_todays_matches():
    url = "https://yallasaas.com/matches-today/"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    matches = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logging.error(f"Failed to fetch matches from {url}: {e}")
        return matches

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("a", class_=re.compile(r"match-card"))

    for c in cards:
        teams = [t.get_text(strip=True) for t in c.find_all("span", class_="team-name")]
        if len(teams) < 2:
            continue

        # logos
        logos = [img.get("src", "") for img in c.find_all("img") if img.get("src")]
        team1_logo = logos[0] if len(logos) > 0 else ""
        team2_logo = logos[1] if len(logos) > 1 else ""

        ch_el = c.find("span", attrs={"data-live-channel": True})
        ch_raw = ch_el.get_text(strip=True) if ch_el else ""
        ch_id = resolve_channel_id(ch_raw)

        tourn_el = c.find("li", class_="ysmatch-meta-tournament")
        tourn = tourn_el.find_all("span")[-1].get_text(strip=True) if tourn_el and tourn_el.find_all("span") else ""

        comm_el = c.find("span", attrs={"data-live-commentator": True})
        comm = comm_el.get_text(strip=True) if comm_el else ""

        time_el = c.find("b", class_="match-time")
        m_time = time_el.get_text(strip=True) if time_el else ""

        status_el = c.find("small", attrs={"data-live-status": True})
        m_status = status_el.get_text(strip=True) if status_el else ""

        matches.append({
            "team1": teams[0],
            "team2": teams[1],
            "team1_logo": team1_logo,
            "team2_logo": team2_logo,
            "channel_raw": ch_raw,
            "channel_id": ch_id,
            "tournament": tourn,
            "commentator": comm,
            "time": m_time,
            "status": m_status,
            "is_live": "مباشر" in m_status or "جارية" in m_status or (m_status and m_status != "انتهت" and not "تبدأ" in m_status),
            "is_upcoming": "تبدأ" in m_status or ":" in m_time
        })

    logging.info(f"Successfully scraped {len(matches)} matches for today.")
    return matches

def generate_sports_m3u(matches=None):
    if matches is None:
        matches = fetch_todays_matches()

    sources = load_sources()

    # Group matches by channel_id
    matches_by_ch = defaultdict(list)
    for m in matches:
        if m.get("channel_id"):
            matches_by_ch[m["channel_id"]].append(m)

    m3u_lines = [
        "#EXTM3U",
        "# ==============================================================================",
        "# NetFelix Live Sports & Match Center (beIN Sports, SSC, Live Matches)",
        f"# Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        ""
    ]

    # 1. First Section: Live / Upcoming Today Matches Direct Feeds
    m3u_lines.append("# ======================== [⚽ مباريات اليوم المباشرة - Match Day Live] ========================")

    # Sort matches: Live first, then upcoming, then finished
    active_matches = [m for m in matches if not "انتهت" in m.get("status", "")]
    if not active_matches:
        active_matches = matches[:15]

    for idx, m in enumerate(active_matches, 1):
        ch_id = m.get("channel_id") or "bein1"
        ch_info = CHANNEL_MAP.get(ch_id, CHANNEL_MAP["bein1"])

        status_tag = "🔴 [مباشر]" if m.get("is_live") else f"⏰ [{m.get('time', '')}]"
        comm_tag = f" | 🎙️ {m['commentator']}" if m.get("commentator") and m['commentator'] != "—" else ""
        tourn_tag = f" • {m['tournament']}" if m.get("tournament") else ""

        title = f"{status_tag} {m['team1']} × {m['team2']} ({ch_info['name']}{tourn_tag}{comm_tag})"
        logo = m.get("team1_logo") or ch_info["logo"]
        stream_url = f"http://{SERVER_IP}:{SERVER_PORT}/api/sports/stream/{ch_id}"

        m3u_lines.append(f'#EXTINF:-1 tvg-id="{ch_info["tvg_id"]}" tvg-name="{title}" tvg-logo="{logo}" group-title="⚽ مباريات اليوم - Match Day",{title}')
        m3u_lines.append(stream_url)
        m3u_lines.append("")

    # 2. Second Section: Dedicated 24/7 Sports Channels (beIN 1-8, News, SSC, etc.)
    m3u_lines.append("# ======================== [🏆 قنوات بي إن سبورتس وSSC الرياضية] ========================")
    for ch_id, ch_info in CHANNEL_MAP.items():
        # Match info summary for this channel
        ch_matches = matches_by_ch.get(ch_id, [])
        match_summary = ""
        if ch_matches:
            upcoming_for_ch = [f"{m['team1']}×{m['team2']} ({m['time']})" for m in ch_matches if not "انتهت" in m.get("status", "")]
            if upcoming_for_ch:
                match_summary = " [اليوم: " + "، ".join(upcoming_for_ch[:2]) + "]"

        display_name = f"{ch_info['ar_name']}{match_summary}"
        stream_url = f"http://{SERVER_IP}:{SERVER_PORT}/api/sports/stream/{ch_id}"

        m3u_lines.append(f'#EXTINF:-1 tvg-id="{ch_info["tvg_id"]}" tvg-name="{ch_info["name"]}" tvg-logo="{ch_info["logo"]}" group-title="🏆 قنوات بي إن وSSC الرياضية",{display_name}')
        m3u_lines.append(stream_url)
        m3u_lines.append("")

    content = "\n".join(m3u_lines)

    # Save standalone sports m3u
    try:
        DATA_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SPORTS_M3U_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        logging.info(f"Saved sports playlist to {SPORTS_M3U_FILE}")
    except Exception as e:
        logging.error(f"Failed to write {SPORTS_M3U_FILE}: {e}")

    # Also integrate directly into nilesat_egypt.m3u
    merge_into_nilesat(m3u_lines)

    return content

def merge_into_nilesat(sports_lines):
    if not NILESAT_M3U_FILE.exists():
        return
    try:
        with open(NILESAT_M3U_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Filter out old NetFelix sports block if already present
        clean_lines = []
        skip = False
        for line in lines:
            if "NetFelix Live Sports & Match Center" in line or "[⚽ مباريات اليوم المباشرة" in line:
                skip = True
            elif skip and line.startswith("# ========================"):
                # If we encounter next standard category, stop skipping
                if not any(k in line for k in ["مباريات", "بي إن", "beIN", "Sports"]):
                    skip = False
                    clean_lines.append(line)
            elif not skip:
                clean_lines.append(line)

        # Insert sports lines right after #EXTM3U header
        output_lines = []
        inserted = False
        for line in clean_lines:
            output_lines.append(line)
            if line.strip() == "#EXTM3U" and not inserted:
                output_lines.append("\n" + "\n".join(sports_lines[1:]) + "\n")
                inserted = True

        if not inserted:
            output_lines = [sports_lines[0] + "\n" + "\n".join(sports_lines[1:]) + "\n"] + clean_lines

        with open(NILESAT_M3U_FILE, "w", encoding="utf-8") as f:
            f.writelines(output_lines)
        logging.info(f"Merged live sports channels into {NILESAT_M3U_FILE}")
    except Exception as e:
        logging.error(f"Failed to merge sports into {NILESAT_M3U_FILE}: {e}")

if __name__ == "__main__":
    print("Scraping today's matches and generating NetFelix Sports M3U...")
    m = fetch_todays_matches()
    generate_sports_m3u(m)
    print("✓ Sports M3U successfully created and merged!")
