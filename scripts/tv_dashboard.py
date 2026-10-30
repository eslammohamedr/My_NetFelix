#!/usr/bin/env python3
"""
NetFelix TVMorph & TVM-IPTV Master GUI for Samsung Smart TV (Tizen OS)
Customized for Eslam & Family:
- Custom 4K Landscape Photo Wallpaper & Frosted Glass Refraction
- Custom App Icon (Eslam & Wife Portrait with Cyan Glowing Bezel)
- Interactive Home Screen Live Matches Row (FilGoal Real-time Scores & beIN Streams)
- Dynamic Ambient Glow (Ambilight Aura shift on card focus)
- Apple TV 4K Screensaver Mode (Idle fade into personal memories with clock & prayer widget)
- 24/7 Quran Radio (إذاعة القرآن الكريم) Embedded Audio Player
- Dedicated Full-Screen Prayer Times Hub with Cairo Survey Authority & Dhikr
- Soft Adhan Alert when prayer time arrives
- Instant AI Media Search & Content Downloader Dialog
- Ultra-Smooth 2D Spatial Navigation with Cone Scoring & Row Overlap Priority
- WebAudio Tactile Navigation Clicks
"""

import os
from local_env import load_local_env
load_local_env()
import os
import sys
import time
import json
import re
import urllib.request
import urllib.parse
import datetime
import zoneinfo
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TVMorphHub")

BASE_DIR = Path("/home/dell/Desktop/My_NetFelix")
CONFIG_DIR = BASE_DIR / "config"
MEDIA_DIR = Path("/media/dell/Data1/netfelix_data/media")
M3U_FILE = MEDIA_DIR / "nilesat_egypt.m3u"

JELLYFIN_URL = "http://127.0.0.1:8096"
JELLYFIN_TOKEN = os.getenv("JELLYFIN_API_KEY", "")
JELLYFIN_USER = "1585758e77204dae9d782cca1d4e5f5a"

# In-memory caches for snappy responsiveness
_WEATHER_CACHE = {"ts": 0, "data": None}
_PRAYER_CACHE = {"ts": 0, "data": None}
_MATCHES_CACHE = {"ts": 0, "data": None}
_JELLYFIN_CACHE = {"ts": 0, "resume": [], "latest": []}


def get_weather():
    """Fetches Cairo weather with a 15-minute cache."""
    now = time.time()
    if _WEATHER_CACHE["data"] and (now - _WEATHER_CACHE["ts"]) < 900:
        return _WEATHER_CACHE["data"]

    try:
        req = urllib.request.Request(
            "https://wttr.in/Cairo?format=j1",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
            current = data.get("current_condition", [{}])[0]
            temp_c = current.get("temp_C", "28")
            desc = current.get("weatherDesc", [{}])[0].get("value", "Clear night").strip()
            humidity = current.get("humidity", "38")
            result = {
                "temp": f"{temp_c}°",
                "desc": desc,
                "humidity": f"{humidity}%",
                "city": "Cairo"
            }
            _WEATHER_CACHE["ts"] = now
            _WEATHER_CACHE["data"] = result
            return result
    except Exception:
        if _WEATHER_CACHE["data"]:
            return _WEATHER_CACHE["data"]
        return {"temp": "28°", "desc": "Clear night", "humidity": "38%", "city": "Cairo"}


def get_cairo_prayer_times():
    """Fetches accurate prayer times for Cairo according to Egyptian Survey Authority."""
    now = time.time()
    if _PRAYER_CACHE["data"] and (now - _PRAYER_CACHE["ts"]) < 43200:  # 12 hours
        return _PRAYER_CACHE["data"]

    try:
        url = "http://api.aladhan.com/v1/timingsByCity?city=Cairo&country=Egypt&method=5"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            timings = json.loads(r.read().decode("utf-8"))["data"]["timings"]
            result = {
                "fajr": timings.get("Fajr", "05:36"),
                "sunrise": timings.get("Sunrise", "07:04"),
                "dhuhr": timings.get("Dhuhr", "12:39"),
                "asr": timings.get("Asr", "15:51"),
                "maghrib": timings.get("Maghrib", "18:14"),
                "isha": timings.get("Isha", "19:32"),
                "city": "Cairo"
            }
            _PRAYER_CACHE["ts"] = now
            _PRAYER_CACHE["data"] = result
            return result
    except Exception:
        if _PRAYER_CACHE["data"]:
            return _PRAYER_CACHE["data"]
        return {
            "fajr": "05:36", "sunrise": "07:04", "dhuhr": "12:39",
            "asr": "15:51", "maghrib": "18:14", "isha": "19:32", "city": "Cairo"
        }


def calculate_next_prayer(timings):
    """Calculates upcoming prayer, remaining seconds and formatted string."""
    cairo_tz = zoneinfo.ZoneInfo("Africa/Cairo")
    now = datetime.datetime.now(cairo_tz)
    now_secs = now.hour * 3600 + now.minute * 60 + now.second

    prayers = [
        ("Fajr", "الفجر", timings.get("fajr", "05:36")),
        ("Sunrise", "الشروق", timings.get("sunrise", "07:04")),
        ("Dhuhr", "الظهر", timings.get("dhuhr", "12:39")),
        ("Asr", "العصر", timings.get("asr", "15:51")),
        ("Maghrib", "المغرب", timings.get("maghrib", "18:14")),
        ("Isha", "العشاء", timings.get("isha", "19:32")),
    ]

    for name_en, name_ar, t_str in prayers:
        try:
            h, m = map(int, t_str.split(":"))
            p_secs = h * 3600 + m * 60
            if p_secs > now_secs:
                diff_secs = p_secs - now_secs
                hours = diff_secs // 3600
                mins = (diff_secs % 3600) // 60
                secs = diff_secs % 60
                countdown_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
                return {
                    "name_en": name_en,
                    "name_ar": name_ar,
                    "time": t_str,
                    "target_secs": p_secs,
                    "countdown": countdown_str,
                    "diff_secs": diff_secs
                }
        except Exception:
            continue

    # Past Isha: next is tomorrow's Fajr
    try:
        h, m = map(int, timings.get("fajr", "05:36").split(":"))
        diff_secs = (86400 - now_secs) + (h * 3600 + m * 60)
        hours = diff_secs // 3600
        mins = (diff_secs % 3600) // 60
        secs = diff_secs % 60
        return {
            "name_en": "Fajr",
            "name_ar": "الفجر",
            "time": timings.get("fajr", "05:36"),
            "target_secs": h * 3600 + m * 60,
            "countdown": f"{hours:02d}:{mins:02d}:{secs:02d}",
            "diff_secs": diff_secs
        }
    except Exception:
        return {
            "name_en": "Fajr", "name_ar": "الفجر", "time": "05:36",
            "target_secs": 20160, "countdown": "03:15:00", "diff_secs": 11700
        }


def get_sports_matches():
    """Scrapes today's matches with team crests and scores from FilGoal."""
    now = time.time()
    if _MATCHES_CACHE["data"] and (now - _MATCHES_CACHE["ts"]) < 300:  # 5 minutes
        return _MATCHES_CACHE["data"]

    matches = []
    try:
        import bs4
        cairo_tz = zoneinfo.ZoneInfo("Africa/Cairo")
        today_str = datetime.datetime.now(cairo_tz).strftime("%Y-%m-%d")
        url = f"https://www.filgoal.com/matches/?date={today_str}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with urllib.request.urlopen(req, timeout=5) as r:
            soup = bs4.BeautifulSoup(r.read().decode("utf-8", errors="ignore"), "html.parser")
            for h in soup.find_all("li", class_="match-header-holder")[:16]:
                tourn = h.find("h6").get_text(strip=True) if h.find("h6") else ""
                teams = [s.get_text(strip=True) for s in h.find_all("span") if s.get_text(strip=True) and not s.get("class")]
                scores = [b.get_text(strip=True) for b in h.find_all("b")]
                status_el = h.find("span", class_=lambda c: c and "status" in c)
                status = status_el.get_text(strip=True) if status_el else ""
                time_el = h.find("span", class_="time")
                m_time = time_el.get_text(strip=True) if time_el else ""
                imgs = [img.get("data-src") or img.get("src") for img in h.find_all("img")]

                if len(teams) >= 2:
                    t1_logo = imgs[0] if imgs else ""
                    t2_logo = imgs[1] if len(imgs) > 1 else ""
                    if t1_logo.startswith("//"): t1_logo = "https:" + t1_logo
                    if t2_logo.startswith("//"): t2_logo = "https:" + t2_logo

                    is_live = "مباشر" in status or "جارية" in status or "'" in status
                    matches.append({
                        "tournament": tourn,
                        "team1": teams[0],
                        "team2": teams[1],
                        "score1": scores[0] if len(scores) > 0 else "",
                        "score2": scores[1] if len(scores) > 1 else "",
                        "status": status or m_time,
                        "time": m_time,
                        "is_live": is_live,
                        "team1_logo": t1_logo,
                        "team2_logo": t2_logo
                    })
        _MATCHES_CACHE["ts"] = now
        _MATCHES_CACHE["data"] = matches
        return matches
    except Exception as e:
        logger.error(f"Error fetching matches: {e}")
        if _MATCHES_CACHE["data"]:
            return _MATCHES_CACHE["data"]
        return []


def get_jellyfin_items():
    """Fetches Resume and Latest items from Jellyfin."""
    now = time.time()
    if _JELLYFIN_CACHE["resume"] and (now - _JELLYFIN_CACHE["ts"]) < 30:
        return _JELLYFIN_CACHE["resume"], _JELLYFIN_CACHE["latest"]

    headers = {"Authorization": f'MediaBrowser Token="{JELLYFIN_TOKEN}"'}
    resume_items = []
    latest_items = []

    try:
        url = f"{JELLYFIN_URL}/Users/{JELLYFIN_USER}/Items/Resume?Limit=6&Fields=Overview,PrimaryImageAspectRatio"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as r:
            items = json.loads(r.read()).get("Items", [])
            for it in items:
                item_id = it.get("Id")
                name = it.get("Name", "")
                series_name = it.get("SeriesName", "")
                full_title = f"{series_name}: {name}" if series_name else name
                pct = round(it.get("UserData", {}).get("PlayedPercentage", 0))
                resume_items.append({
                    "id": item_id,
                    "title": full_title,
                    "series": series_name,
                    "type": it.get("Type"),
                    "pct": pct,
                    "backdrop": f"/api/jellyfin/image/{item_id}/Backdrop" if it.get("BackdropImageTags") else f"/api/jellyfin/image/{item_id}/Primary",
                    "poster": f"/api/jellyfin/image/{item_id}/Primary"
                })
    except Exception:
        pass

    try:
        url = f"{JELLYFIN_URL}/Users/{JELLYFIN_USER}/Items/Latest?Limit=8&Fields=Overview,PrimaryImageAspectRatio"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as r:
            items = json.loads(r.read())
            for it in items:
                item_id = it.get("Id")
                name = it.get("Name", "")
                series_name = it.get("SeriesName", "")
                full_title = f"{series_name}: {name}" if series_name else name
                latest_items.append({
                    "id": item_id,
                    "title": full_title,
                    "series": series_name,
                    "type": it.get("Type"),
                    "poster": f"/api/jellyfin/image/{item_id}/Primary",
                    "backdrop": f"/api/jellyfin/image/{item_id}/Backdrop" if it.get("BackdropImageTags") else f"/api/jellyfin/image/{item_id}/Primary"
                })
    except Exception:
        pass

    _JELLYFIN_CACHE["ts"] = now
    _JELLYFIN_CACHE["resume"] = resume_items
    _JELLYFIN_CACHE["latest"] = latest_items
    return resume_items, latest_items


def get_dashboard_data():
    """Aggregates all TV Hub data into a unified payload."""
    resume, latest = get_jellyfin_items()
    weather = get_weather()
    prayer_timings = get_cairo_prayer_times()
    next_prayer = calculate_next_prayer(prayer_timings)
    matches = get_sports_matches()

    cairo_tz = zoneinfo.ZoneInfo("Africa/Cairo")
    now_cairo = datetime.datetime.now(cairo_tz)
    clock_str = now_cairo.strftime("%I:%M %p").lstrip("0")
    date_str = now_cairo.strftime("%a, %b %d")

    return {
        "status": "online",
        "clock": clock_str,
        "date": date_str,
        "weather": weather,
        "prayer": {
            "timings": prayer_timings,
            "next": next_prayer
        },
        "matches": matches,
        "resume": resume,
        "latest": latest
    }


# ==============================================================================
# MASTER HTML TEMPLATE (Custom Wallpaper + Interactive Home Matches + Screensaver)
# ==============================================================================

TV_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>NetFelix Hub • Eslam & Family 4K Edition</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=Cairo:wght@600;700;800;900&display=swap" rel="stylesheet">
    <script src="/api/hls.min.js"></script>
    <style>
        :root {
            --bg-deep: #020617;
            --bg-card: rgba(12, 20, 42, 0.82);
            --bg-card-hover: rgba(30, 41, 59, 0.92);
            --border-glass: rgba(255, 255, 255, 0.09);
            --border-highlight: rgba(255, 255, 255, 0.32);
            --cyan-accent: #00e5ff;
            --cyan-glow: 0 0 30px rgba(0, 229, 255, 0.9), 0 0 8px #00e5ff, 0 0 60px rgba(0, 229, 255, 0.3);
            --blue-accent: #38bdf8;
            --purple-accent: #a78bfa;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --ambilight: rgba(0, 229, 255, 0.18);
            --card-radius: 24px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            -webkit-user-select: none;
        }

        body {
            background-color: var(--bg-deep);
            background-image:
                linear-gradient(180deg, rgba(2, 6, 23, 0.55) 0%, rgba(2, 6, 23, 0.92) 100%),
                url('/api/wallpaper?v=1');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', 'Cairo', -apple-system, BlinkMacSystemFont, sans-serif;
            min-height: 100vh;
            overflow-x: hidden;
            overflow-y: auto;
            padding: 22px 36px 50px 36px;
            scroll-behavior: smooth;
        }

        /* Animated floating orb particles behind content */
        #particle-canvas {
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
        }

        /* Dynamic Ambilight Room Backdrop Aura */
        #ambilight-halo {
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            background: radial-gradient(ellipse at 55% 35%, var(--ambilight) 0%, transparent 70%);
            transition: background 0.8s cubic-bezier(0.22, 1, 0.36, 1);
            mix-blend-mode: screen;
        }

        .page-content-wrapper {
            position: relative;
            z-index: 1;
        }

        /* ────────── TV REMOTE SPATIAL FOCUS (Animated Gradient Ring + Lift) ────────── */
        .focusable {
            outline: none !important;
            transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1),
                        box-shadow 0.22s cubic-bezier(0.22, 1, 0.36, 1),
                        border-color 0.22s ease,
                        background-color 0.22s ease,
                        filter 0.22s ease;
            will-change: transform, box-shadow;
        }

        .focusable:focus,
        .focusable.focused {
            transform: translateY(-6px) scale(1.06) !important;
            border-color: var(--cyan-accent) !important;
            box-shadow:
                0 0 0 2.5px var(--cyan-accent),
                0 0 18px rgba(0, 229, 255, 0.85),
                0 14px 40px rgba(0, 229, 255, 0.45),
                0 22px 50px rgba(0, 0, 0, 0.85),
                inset 0 1px 0 rgba(255, 255, 255, 0.18) !important;
            z-index: 100 !important;
            position: relative;
            filter: brightness(1.08);
        }

        .dock-app-card.focusable:focus,
        .dock-app-card.focusable.focused {
            transform: translateY(-14px) scale(1.18) !important;
            border-color: var(--cyan-accent) !important;
            box-shadow:
                0 0 0 3px var(--cyan-accent),
                0 0 22px rgba(0, 229, 255, 0.9),
                0 18px 45px rgba(0, 229, 255, 0.55),
                0 28px 55px rgba(0, 0, 0, 0.9),
                inset 0 1px 0 rgba(255, 255, 255, 0.22) !important;
            filter: brightness(1.12);
        }

        .tvm-hero-card.focusable:focus,
        .tvm-hero-card.focusable.focused {
            transform: scale(1.018) !important;
            border-color: var(--cyan-accent) !important;
            box-shadow:
                0 0 0 3px var(--cyan-accent),
                0 0 25px rgba(0, 229, 255, 0.75),
                0 20px 50px rgba(0, 229, 255, 0.35),
                0 32px 70px rgba(0, 0, 0, 0.9) !important;
        }

        /* ────────── Top Bar Navigation ────────── */
        .tvm-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 22px;
            gap: 16px;
        }

        .tvm-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .tvm-logo-badge {
            display: flex;
            align-items: center;
            gap: 10px;
            background: rgba(10, 18, 38, 0.88);
            backdrop-filter: blur(30px) saturate(160%);
            border: 1px solid var(--border-glass);
            border-top: 1px solid var(--border-highlight);
            padding: 5px 18px 5px 7px;
            border-radius: 9999px;
            font-size: 17px;
            font-weight: 900;
            letter-spacing: 0.5px;
            cursor: pointer;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
        }

        .tvm-brand-avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            object-fit: cover;
            border: 2.5px solid var(--cyan-accent);
            box-shadow: 0 0 14px rgba(0, 229, 255, 0.7);
        }

        .tvm-search-pill {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(10, 18, 38, 0.78);
            backdrop-filter: blur(30px) saturate(160%);
            border: 1px solid var(--border-glass);
            border-top: 1px solid var(--border-highlight);
            padding: 9px 20px;
            border-radius: 9999px;
            font-size: 13px;
            color: var(--text-muted);
            cursor: pointer;
            box-shadow: 0 6px 18px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06);
        }

        .tvm-nav-tabs {
            display: flex;
            align-items: center;
            gap: 5px;
            background: rgba(10, 18, 38, 0.84);
            backdrop-filter: blur(35px) saturate(170%);
            border: 1px solid var(--border-glass);
            border-top: 1px solid var(--border-highlight);
            padding: 5px 8px;
            border-radius: 9999px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
        }

        .nav-tab {
            padding: 7px 16px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 700;
            color: var(--text-muted);
            cursor: pointer;
            white-space: nowrap;
            border: 1px solid transparent;
            transition: all 0.2s ease;
        }

        .nav-tab.active {
            background: linear-gradient(135deg, #2563eb, #3b82f6);
            color: #fff;
            box-shadow: 0 0 22px rgba(37, 99, 235, 0.8), inset 0 1px 0 rgba(255,255,255,0.2);
        }

        .tvm-status-pills {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .meta-pill {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(10, 18, 38, 0.8);
            backdrop-filter: blur(30px) saturate(160%);
            border: 1px solid var(--border-glass);
            border-top: 1px solid var(--border-highlight);
            padding: 7px 16px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 6px 16px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06);
        }

        .clock-val {
            font-size: 16px;
            font-weight: 900;
            letter-spacing: 0.5px;
            color: #fff;
        }

        /* ────────── Main Grid Layout ────────── */
        .tvm-layout {
            display: grid;
            grid-template-columns: 86px 1fr;
            gap: 22px;
        }

        .left-vertical-dock {
            display: flex;
            flex-direction: column;
            gap: 12px;
            align-items: center;
            padding-top: 4px;
        }

        .sidebar-btn {
            width: 78px;
            height: 78px;
            background: var(--bg-card);
            backdrop-filter: blur(30px) saturate(160%);
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            border-radius: var(--card-radius);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 6px;
            cursor: pointer;
            box-shadow: 0 10px 24px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.06);
        }

        .sidebar-btn .s-icon {
            font-size: 26px;
            line-height: 1;
        }

        .sidebar-btn .s-label {
            font-size: 10px;
            font-weight: 800;
            color: var(--text-muted);
            text-align: center;
            line-height: 1.1;
        }

        /* Main Content Column */
        .main-content {
            display: flex;
            flex-direction: column;
            gap: 26px;
        }

        /* ────────── Hero Banner ────────── */
        .tvm-hero-card {
            position: relative;
            height: 380px;
            border-radius: 28px;
            overflow: hidden;
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            background: linear-gradient(135deg, rgba(7, 14, 36, 0.88) 0%, rgba(2, 6, 23, 0.96) 100%);
            backdrop-filter: blur(25px) saturate(160%);
            display: flex;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.75), inset 0 1px 0 rgba(255,255,255,0.06);
            cursor: pointer;
        }

        .hero-left-content {
            flex: 1.2;
            padding: 42px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 14px;
            z-index: 2;
        }

        .hero-tagline {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-weight: 800;
            color: var(--cyan-accent);
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }

        .hero-tagline-dot {
            width: 8px;
            height: 8px;
            background: var(--cyan-accent);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--cyan-accent);
        }

        .hero-headline {
            font-size: 42px;
            font-weight: 900;
            line-height: 1.15;
            color: #ffffff;
            letter-spacing: -0.5px;
        }

        .hero-desc {
            font-size: 16px;
            color: #94a3b8;
            max-width: 490px;
            line-height: 1.5;
        }

        .hero-btn-row {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-top: 8px;
        }

        .hero-cta-btn {
            background: linear-gradient(135deg, #ffffff 0%, #e2e8f0 100%);
            color: #030712;
            border: none;
            padding: 13px 30px;
            border-radius: 9999px;
            font-size: 15px;
            font-weight: 900;
            font-family: inherit;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 8px 30px rgba(255,255,255,0.35), inset 0 -2px 0 rgba(0,0,0,0.08);
            letter-spacing: 0.3px;
        }

        .hero-secondary-btn {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            border: 1.5px solid rgba(255, 255, 255, 0.25);
            padding: 12px 26px;
            border-radius: 9999px;
            font-size: 14px;
            font-weight: 800;
            font-family: inherit;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            backdrop-filter: blur(15px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.12);
        }

        .hero-right-visual {
            flex: 1.25;
            position: relative;
            background-size: cover;
            background-position: center 30%;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            align-items: flex-end;
            padding: 32px;
        }

        .hero-right-visual::before {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, rgba(7, 14, 36, 0.95) 0%, rgba(7, 14, 36, 0.4) 40%, transparent 100%),
                        linear-gradient(0deg, rgba(2, 6, 23, 0.85) 0%, transparent 50%);
        }

        /* Floating Prayer Countdown inside Hero */
        .hero-prayer-widget {
            position: relative;
            z-index: 5;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(30px);
            border: 1.5px solid rgba(0, 229, 255, 0.45);
            border-top: 1.5px solid rgba(255, 255, 255, 0.35);
            border-radius: 22px;
            padding: 18px 26px;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 4px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.6), 0 0 20px rgba(0, 229, 255, 0.25);
            cursor: pointer;
        }

        .prayer-label-sub {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 800;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .prayer-pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--cyan-accent);
            animation: pulse-glow 2s infinite;
        }

        @keyframes pulse-glow {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 229, 255, 0.7); }
            70% { transform: scale(1.1); box-shadow: 0 0 0 8px rgba(0, 229, 255, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 229, 255, 0); }
        }

        .prayer-target-name {
            font-size: 22px;
            font-weight: 900;
            color: #ffffff;
        }

        .prayer-live-timer {
            font-size: 30px;
            font-weight: 900;
            color: var(--cyan-accent);
            letter-spacing: 1px;
            font-variant-numeric: tabular-nums;
            text-shadow: 0 0 15px rgba(0, 229, 255, 0.6);
        }

        /* Section Titles */
        .section-row-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 6px;
        }

        .sec-title {
            font-size: 21px;
            font-weight: 900;
            letter-spacing: 0.2px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .sec-more-link {
            font-size: 14px;
            font-weight: 700;
            color: var(--cyan-accent);
            cursor: pointer;
        }

        /* ────────── Home Screen Live Matches Row ────────── */
        .home-matches-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 18px;
        }

        .home-match-card {
            background: var(--bg-card);
            backdrop-filter: blur(30px) saturate(160%);
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            border-radius: var(--card-radius);
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            cursor: pointer;
            box-shadow: 0 12px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
        }

        .hm-tourn-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            font-weight: 800;
            color: var(--cyan-accent);
            text-transform: uppercase;
        }

        .hm-teams-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .hm-team-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            width: 38%;
            text-align: center;
        }

        .hm-team-logo {
            width: 38px;
            height: 38px;
            object-fit: contain;
        }

        .hm-team-name {
            font-size: 13px;
            font-weight: 800;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            width: 100%;
        }

        .hm-score-center {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 3px;
        }

        .hm-score-val {
            font-size: 20px;
            font-weight: 900;
            color: #fff;
            letter-spacing: 1px;
        }

        .hm-status-tag {
            font-size: 10px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 9999px;
            background: rgba(255, 255, 255, 0.12);
            color: var(--text-muted);
        }

        .hm-status-tag.live {
            background: #ef4444;
            color: #fff;
            animation: pulse-glow 2s infinite;
        }

        .hm-action-hint {
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted);
            text-align: center;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding-top: 8px;
        }

        /* ────────── "Recently used" Row ────────── */
        .recent-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 16px;
        }

        .recent-card {
            background: var(--bg-card);
            backdrop-filter: blur(30px) saturate(160%);
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            border-radius: 22px;
            padding: 16px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            box-shadow: 0 10px 28px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.06);
        }

        .recent-icon-wrap {
            width: 46px;
            height: 46px;
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 23px;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.04));
            border: 1px solid rgba(255, 255, 255, 0.12);
            flex-shrink: 0;
            overflow: hidden;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.1);
        }

        .recent-icon-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .recent-texts {
            display: flex;
            flex-direction: column;
            overflow: hidden;
            gap: 2px;
        }

        .recent-name {
            font-size: 14px;
            font-weight: 800;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .recent-sub {
            font-size: 11px;
            color: var(--text-muted);
            white-space: nowrap;
        }

        /* ────────── "Continue watching" Row ────────── */
        .continue-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }

        .continue-card {
            position: relative;
            height: 185px;
            border-radius: var(--card-radius);
            overflow: hidden;
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            background-size: cover;
            background-position: center;
            padding: 20px 22px;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            cursor: pointer;
            box-shadow: 0 16px 40px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.05);
        }

        .continue-card::before {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, rgba(2, 6, 23, 0.15) 0%, rgba(2, 6, 23, 0.96) 100%);
            z-index: 1;
        }

        .continue-card-content {
            position: relative;
            z-index: 2;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .cont-top-badge {
            align-self: flex-start;
            background: rgba(0, 229, 255, 0.15);
            border: 1px solid var(--cyan-accent);
            color: var(--cyan-accent);
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            padding: 3px 10px;
            border-radius: 9999px;
        }

        .cont-title {
            font-size: 18px;
            font-weight: 900;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .progress-track {
            width: 100%;
            height: 5px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 9999px;
            overflow: hidden;
            margin-top: 4px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00e5ff, #38bdf8);
            border-radius: 9999px;
            box-shadow: 0 0 10px rgba(0, 229, 255, 0.8);
        }

        .cont-footer-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted);
            margin-top: 2px;
        }

        /* ────────── Bottom App Dock with Glossy Mirror Reflection ────────── */
        .tvm-bottom-dock {
            display: flex;
            justify-content: center;
            gap: 24px;
            padding: 14px 0 40px 0;
            -webkit-box-reflect: below 8px linear-gradient(transparent 45%, rgba(255, 255, 255, 0.30));
        }

        .dock-app-card {
            width: 96px;
            height: 96px;
            border-radius: 28px;
            background: var(--bg-card);
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 6px;
            cursor: pointer;
            box-shadow: 0 14px 35px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.08);
            position: relative;
        }

        .dock-avatar-img {
            width: 54px;
            height: 54px;
            border-radius: 18px;
            object-fit: cover;
            border: 2px solid var(--cyan-accent);
            box-shadow: 0 0 12px rgba(0, 229, 255, 0.5);
        }

        .dock-icon {
            font-size: 40px;
            line-height: 1;
            filter: drop-shadow(0 2px 6px rgba(0,0,0,0.4));
        }

        .dock-app-name {
            position: absolute;
            bottom: -26px;
            font-size: 12px;
            font-weight: 900;
            color: #fff;
            white-space: nowrap;
            opacity: 0;
            transition: opacity 0.2s ease, transform 0.2s ease;
            text-shadow: 0 2px 10px rgba(0,0,0,0.9);
            transform: translateY(4px);
        }

        .dock-app-card.focused .dock-app-name,
        .dock-app-card:focus .dock-app-name {
            opacity: 1;
            transform: translateY(0);
        }

        /* Fullscreen Prayer Times Hub Modal (Photo 3 exact clone) */
        #prayer-hub-modal {
            display: none;
            position: fixed;
            inset: 0;
            background: #020617;
            background-image:
                radial-gradient(circle at 50% 25%, rgba(14, 116, 144, 0.35) 0%, transparent 60%),
                linear-gradient(180deg, rgba(2, 6, 23, 0.88) 0%, #020617 100%),
                url('/api/wallpaper?v=1');
            background-size: cover;
            background-position: center;
            z-index: 9999;
            flex-direction: column;
            padding: 40px 60px;
            overflow-y: auto;
        }

        .ph-top-bar {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 30px;
        }

        .ph-title-group h1 {
            font-size: 30px;
            font-weight: 900;
        }

        .ph-title-group p {
            color: #94a3b8;
            font-size: 14px;
            margin-top: 4px;
        }

        .ph-action-btns {
            display: flex;
            gap: 12px;
        }

        .ph-pill-btn {
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(25px);
            border: 1px solid var(--border-glass);
            border-top: 1px solid var(--border-highlight);
            color: #fff;
            padding: 8px 22px;
            border-radius: 9999px;
            font-size: 14px;
            font-weight: 700;
            font-family: inherit;
            cursor: pointer;
        }

        .ph-row-1 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }

        .ph-weather-card,
        .ph-clock-card {
            background: rgba(15, 23, 42, 0.72);
            backdrop-filter: blur(30px);
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            border-radius: 24px;
            padding: 26px 32px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.5);
        }

        .ph-big-clock {
            font-size: 46px;
            font-weight: 900;
            letter-spacing: 1px;
            color: #fff;
        }

        .ph-prayers-row {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 16px;
            margin-bottom: 30px;
        }

        .ph-prayer-box {
            background: rgba(15, 23, 42, 0.72);
            backdrop-filter: blur(30px);
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            border-radius: 22px;
            padding: 22px 16px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        }

        .ph-prayer-box.active-prayer {
            border: 2px solid var(--cyan-accent);
            box-shadow: var(--cyan-glow);
            background: rgba(14, 116, 144, 0.45);
        }

        .ph-p-name {
            font-size: 15px;
            font-weight: 800;
            color: #94a3b8;
        }

        .ph-p-time {
            font-size: 24px;
            font-weight: 900;
            color: #fff;
        }

        .ph-supplication-box {
            text-align: center;
            margin-top: auto;
            padding-top: 20px;
        }

        .ph-arabic-dhikr {
            font-family: 'Cairo', sans-serif;
            font-size: 24px;
            font-weight: 900;
            color: #ffffff;
            margin-bottom: 6px;
            letter-spacing: 0.5px;
        }

        .ph-dhikr-trans {
            font-size: 15px;
            color: #94a3b8;
        }

        /* APPLE TV SCREENSAVER OVERLAY */
        #screensaver-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: #000;
            z-index: 999999;
            overflow: hidden;
            opacity: 0;
            transition: opacity 0.8s ease;
        }

        #screensaver-overlay.active {
            opacity: 1;
        }

        .ss-bg-image {
            position: absolute;
            inset: -5%;
            width: 110%;
            height: 110%;
            object-fit: cover;
            animation: ken-burns 30s ease-in-out infinite alternate;
        }

        @keyframes ken-burns {
            0% { transform: scale(1) translate(0, 0); }
            100% { transform: scale(1.08) translate(-2%, -2%); }
        }

        .ss-hud-bottom {
            position: absolute;
            bottom: 40px;
            left: 50px;
            right: 50px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            z-index: 10;
        }

        .ss-glass-card {
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(35px);
            border: 1.5px solid rgba(255, 255, 255, 0.15);
            border-top: 1.5px solid rgba(255, 255, 255, 0.3);
            border-radius: 24px;
            padding: 20px 32px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7);
        }

        .ss-clock {
            font-size: 48px;
            font-weight: 900;
            color: #fff;
            letter-spacing: 1px;
        }

        /* AI Media Search & Downloader Modal */
        #search-downloader-modal {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(2, 6, 23, 0.94);
            backdrop-filter: blur(40px);
            z-index: 99999;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px;
        }

        .sd-box {
            width: 700px;
            background: var(--bg-card);
            border: 1.5px solid var(--border-glass);
            border-top: 1.5px solid var(--border-highlight);
            border-radius: 28px;
            padding: 36px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            box-shadow: 0 25px 60px rgba(0,0,0,0.8);
        }

        .sd-input-row {
            display: flex;
            gap: 12px;
        }

        .sd-input {
            flex: 1;
            background: rgba(255, 255, 255, 0.08);
            border: 1.5px solid var(--border-glass);
            border-radius: 16px;
            padding: 14px 20px;
            font-size: 18px;
            font-weight: 700;
            color: #fff;
            font-family: inherit;
            outline: none;
        }

        .sd-tags-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .sd-tag-pill {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid var(--border-glass);
            color: #fff;
            padding: 8px 18px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 800;
            cursor: pointer;
        }

        /* Live Video Player Modal */
        #player-modal {
            display: none;
            position: fixed;
            inset: 0;
            background: #000;
            z-index: 999999;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }

        .player-bar {
            position: absolute;
            top: 28px;
            right: 40px;
            z-index: 10;
            display: flex;
            align-items: center;
            gap: 16px;
            background: rgba(15, 23, 42, 0.88);
            backdrop-filter: blur(30px);
            padding: 8px 24px;
            border-radius: 9999px;
            border: 1px solid rgba(255,255,255,0.18);
        }

        /* Audio Player Bar (Radio Quran) */
        #audio-bar {
            display: none;
            position: fixed;
            bottom: 25px;
            right: 35px;
            background: rgba(15, 23, 42, 0.9);
            backdrop-filter: blur(30px);
            border: 1.5px solid var(--cyan-accent);
            border-radius: 9999px;
            padding: 10px 24px;
            z-index: 9999;
            align-items: center;
            gap: 16px;
            box-shadow: var(--cyan-glow);
        }

        /* TV Toast Notification */
        .tvm-toast {
            position: fixed;
            top: 35px;
            left: 50%;
            transform: translateX(-50%) translateY(-120px);
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(40px);
            border: 1.5px solid var(--cyan-accent);
            box-shadow: var(--cyan-glow);
            padding: 12px 28px;
            border-radius: 9999px;
            font-size: 16px;
            font-weight: 800;
            color: #fff;
            z-index: 999999;
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .tvm-toast.show {
            transform: translateX(-50%) translateY(0);
        }

        footer {
            margin-top: 45px;
            font-size: 12px;
            color: #64748b;
            text-align: center;
            letter-spacing: 0.5px;
        }

        /* Living-room layout: generous safe area and readable controls. */
        body { padding: 3vh 3.5vw 64px; }
        .tvm-topbar { flex-wrap: wrap; gap: 20px; margin-bottom: 32px; }
        .tvm-brand { flex: 1; }
        .tvm-nav-tabs { order: 3; width: 100%; justify-content: center; border-radius: 18px; padding: 10px; gap: 12px; }
        .nav-tab { font-size: 18px; padding: 12px 22px; }
        .tvm-search-pill, .meta-pill { font-size: 17px; min-height: 48px; }
        .clock-val { font-size: 22px; }
        .main-content { min-width: 0; }
        .tvm-layout { grid-template-columns: 96px minmax(0, 1fr); gap: 30px; }
        .sidebar-btn { width: 88px; height: 88px; border-radius: 20px; }
        .sidebar-btn .s-label { font-size: 14px; color: #dbe5f4; }
        .hero-desc { font-size: 20px; line-height: 1.65; max-width: 620px; }
        .hero-tagline { font-size: 15px; }
        .hero-cta-btn, .hero-secondary-btn { min-height: 54px; font-size: 18px; }
        .sec-title { font-size: 24px; }
        .sec-more-link { font-size: 17px; padding: 10px; border-radius: 10px; }
        .recent-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .recent-card { min-height: 104px; }
        .focusable { scroll-margin: 80px; will-change: auto; }
        .focusable:focus, .focusable.focused,
        .dock-app-card.focusable:focus, .dock-app-card.focusable.focused,
        .tvm-hero-card.focusable:focus, .tvm-hero-card.focusable.focused {
            transform: translateY(-2px) !important;
            outline: 3px solid #e7fcff !important;
            outline-offset: 4px;
            box-shadow: 0 0 0 6px rgba(0, 229, 255, .24), 0 12px 28px rgba(0, 0, 0, .45) !important;
        }
        .remote-guide { display: flex; justify-content: center; gap: 28px; color: #c4cfdf; font-size: 16px; margin: 30px 0 8px; }
        .remote-guide kbd { color: #fff; border: 1px solid #738198; border-radius: 6px; padding: 3px 8px; font: inherit; }
        .sd-input { user-select: text; -webkit-user-select: text; }
        @media (max-width: 1400px) {
            .nav-tab { padding: 10px 14px; font-size: 16px; }
            .tvm-nav-tabs { gap: 4px; }
            .home-matches-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .hero-left-content { padding: 28px; }
            .hero-headline { font-size: 42px; }
        }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
        }
    </style>
    <link rel="stylesheet" href="/tv-ui/appearance.css">
    <link rel="stylesheet" href="/tv-ui/icons.css">
</head>
<body>

    <!-- Dynamic Room Ambilight Backdrop -->
    <div id="ambilight-halo"></div>

    <!-- Floating particle orbs (CSS only, no canvas overhead) -->
    <style>
        .orb {
            position: fixed;
            border-radius: 50%;
            pointer-events: none;
            z-index: 0;
            mix-blend-mode: screen;
            animation: orb-drift linear infinite;
        }
        @keyframes orb-drift {
            0%   { transform: translate(0, 0) scale(1); opacity: 0.35; }
            25%  { transform: translate(60px, -120px) scale(1.1); opacity: 0.22; }
            50%  { transform: translate(-40px, -240px) scale(0.95); opacity: 0.30; }
            75%  { transform: translate(80px, -360px) scale(1.05); opacity: 0.18; }
            100% { transform: translate(0, -480px) scale(1); opacity: 0.35; }
        }
    </style>
    <div class="orb" style="width:240px;height:240px;left:8%;bottom:-5%;background:radial-gradient(circle,rgba(0,229,255,0.15),transparent 70%);animation-duration:22s;"></div>
    <div class="orb" style="width:180px;height:180px;right:12%;bottom:10%;background:radial-gradient(circle,rgba(99,102,241,0.12),transparent 70%);animation-duration:28s;animation-delay:-6s;"></div>
    <div class="orb" style="width:300px;height:300px;left:55%;bottom:20%;background:radial-gradient(circle,rgba(56,189,248,0.1),transparent 70%);animation-duration:35s;animation-delay:-12s;"></div>

    <div class="page-content-wrapper">

        <!-- TVM Top Bar -->
        <header class="tvm-topbar">
            <div class="tvm-brand">
                <div class="tvm-logo-badge focusable" tabindex="0" onclick="window.location.reload()" data-color="cyan">
                    <img src="/api/app-icon" class="tvm-brand-avatar" alt="NetFelix">
                    <span>NetFelix Hub</span>
                </div>
                <div class="tvm-search-pill focusable" tabindex="0" onclick="openSearchModal()" data-color="blue">
                    <span>🔍</span>
                    <span>Search / Download...</span>
                </div>
            </div>

            <nav class="tvm-nav-tabs">
                <div class="nav-tab active focusable" tabindex="0" onclick="window.scrollTo({top:0, behavior:'smooth'})" data-color="cyan">🏠 Home</div>
                <div class="nav-tab focusable" tabindex="0" onclick="openLiveTV()" data-color="green">📡 Live TV</div>
                <div class="nav-tab focusable" tabindex="0" onclick="launchApp('jellyfin')" data-color="sky">🍿 Movies</div>
                <div class="nav-tab focusable" tabindex="0" onclick="launchApp('jellyfin')" data-color="sky">📺 Series</div>
                <div class="nav-tab focusable" tabindex="0" onclick="scrollToMatches()" data-color="green">⚽ Matches</div>
                <div class="nav-tab focusable" tabindex="0" onclick="openPrayerHub()" data-color="teal">🕌 Prayer Hub</div>
                <div class="nav-tab focusable" tabindex="0" onclick="toggleQuranRadio()" data-color="teal">📻 Quran Radio</div>
            </nav>

            <div class="tvm-status-pills">
                <div class="meta-pill focusable" tabindex="0" onclick="openPrayerHub()" data-color="teal">
                    <span>🌙</span>
                    <span>{WEATHER_TEMP} Cairo</span>
                </div>
                <div class="meta-pill focusable" tabindex="0" onclick="openPrayerHub()" data-color="teal">
                    <span class="clock-val" id="live-clock-time">{CLOCK_TIME}</span>
                    <span style="color:var(--text-muted); font-size:11px;">{DATE_STR}</span>
                </div>
            </div>
        </header>

        <div class="remote-guide"><span><kbd>↑ ↓ ← →</kbd> Navigate</span><span><kbd>OK</kbd> Select</span><span><kbd>Back</kbd> Close / Return</span></div>

        <!-- TVM Main Layout: Left Dock + Main Area -->
        <div class="tvm-layout">

            <!-- Left Vertical Dock (Image 2) -->
            <aside class="left-vertical-dock">
                <div class="sidebar-btn focusable" tabindex="0" onclick="openPrayerHub()" data-color="teal">
                    <span class="s-icon">🌙</span>
                    <span class="s-label">Prayer</span>
                </div>
                <div class="sidebar-btn focusable" tabindex="0" onclick="launchApp('jellyfin')" data-color="sky">
                    <span class="s-icon">🍿</span>
                    <span class="s-label">NetFelix</span>
                </div>
                <div class="sidebar-btn focusable" tabindex="0" onclick="openLiveTV()" data-color="green">
                    <span class="s-icon">📡</span>
                    <span class="s-label">Live TV</span>
                </div>
                <div class="sidebar-btn focusable" tabindex="0" onclick="scrollToMatches()" data-color="green">
                    <span class="s-icon">⚽</span>
                    <span class="s-label">Matches</span>
                </div>
                <div class="sidebar-btn focusable" tabindex="0" onclick="launchApp('youtube')" data-color="red">
                    <span class="s-icon">▶️</span>
                    <span class="s-label">YouTube</span>
                </div>
                <div class="sidebar-btn focusable" tabindex="0" onclick="toggleQuranRadio()" data-color="teal">
                    <span class="s-icon">📻</span>
                    <span class="s-label">Quran</span>
                </div>
            </aside>

            <!-- Main Content Area -->
            <main class="main-content">

                <!-- Hero Banner: "Your TV. Your world." -->
                <div class="tvm-hero-card">
                    <div class="hero-left-content">
                        <div class="hero-tagline">
                            <div class="hero-tagline-dot"></div>
                            <span>ESLAM & FAMILY • 4K ULTRA HD</span>
                        </div>
                        <h1 class="hero-headline">Your TV. Your world.</h1>
                        <p class="hero-desc">Stream live Egyptian & European matches, cinema hits in 4K HDR, and stay synchronized with Cairo Adhan timings.</p>
                        <div class="hero-btn-row">
                            <button class="hero-cta-btn focusable" tabindex="0" onclick="launchApp('jellyfin'); event.stopPropagation();">
                                <span>▶</span> Watch now
                            </button>
                            <button class="hero-secondary-btn focusable" tabindex="0" onclick="scrollToMatches(); event.stopPropagation();">
                                <span>⚽</span> Today's Matches
                            </button>
                        </div>
                    </div>
                    <div class="hero-right-visual" style="background-image: url('https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1200&auto=format&fit=crop');">
                        <!-- Live Ticking Prayer Countdown Widget -->
                        <div class="hero-prayer-widget focusable" tabindex="0" onclick="openPrayerHub(); event.stopPropagation();" data-color="teal">
                            <div class="prayer-label-sub">
                                <div class="prayer-pulse-dot"></div>
                                <span>Next prayer</span>
                            </div>
                            <span class="prayer-target-name" id="hero-prayer-name">{PRAYER_TARGET_NAME}</span>
                            <span class="prayer-live-timer" id="hero-prayer-timer">{PRAYER_COUNTDOWN}</span>
                        </div>
                    </div>
                </div>

                <!-- INTERACTIVE HOME SCREEN LIVE MATCHES ROW -->
                <div class="section-row-header" id="matches-section-anchor">
                    <h3 class="sec-title">⚽ Live Matches & Today's Games (FilGoal)</h3>
                    <span class="sec-more-link focusable" tabindex="0" role="button" onclick="openLiveTV()">All Live Channels →</span>
                </div>
                <div class="home-matches-grid">
                    {HOME_MATCHES_CARDS}
                </div>

                <!-- "Recently used" Row -->
                <div class="section-row-header">
                    <h3 class="sec-title">✨ Recently used</h3>
                    <span class="sec-more-link focusable" tabindex="0" role="button" onclick="launchApp('jellyfin')">All apps →</span>
                </div>
                <div class="recent-grid">
                    <div class="recent-card focusable" tabindex="0" onclick="openLiveTV()" data-color="green">
                        <div class="recent-icon-wrap" style="color:var(--cyan-accent);">📡</div>
                        <div class="recent-texts">
                            <span class="recent-name">Live TV (IPTV)</span>
                            <span class="recent-sub">TOD & Channels</span>
                        </div>
                    </div>
                    <div class="recent-card focusable" tabindex="0" onclick="launchApp('jellyfin')" data-color="cyan">
                        <div class="recent-icon-wrap">
                            <img src="/api/app-icon" class="recent-icon-img" alt="NetFelix">
                        </div>
                        <div class="recent-texts">
                            <span class="recent-name">NetFelix</span>
                            <span class="recent-sub">Opened recently</span>
                        </div>
                    </div>
                    <div class="recent-card focusable" tabindex="0" onclick="openPrayerHub()" data-color="teal">
                        <div class="recent-icon-wrap" style="color:#34d399;">🌙</div>
                        <div class="recent-texts">
                            <span class="recent-name">Prayer times</span>
                            <span class="recent-sub">Opened recently</span>
                        </div>
                    </div>
                    <div class="recent-card focusable" tabindex="0" onclick="launchApp('tod')" data-color="green">
                        <div class="recent-icon-wrap" style="color:#00b2a9;">⚽</div>
                        <div class="recent-texts">
                            <span class="recent-name">TOD Sports</span>
                            <span class="recent-sub">Opened recently</span>
                        </div>
                    </div>
                    <div class="recent-card focusable" tabindex="0" onclick="launchApp('netflix')" data-color="red">
                        <div class="recent-icon-wrap" style="color:#ef4444;">🎬</div>
                        <div class="recent-texts">
                            <span class="recent-name">Netflix</span>
                            <span class="recent-sub">Opened recently</span>
                        </div>
                    </div>
                    <div class="recent-card focusable" tabindex="0" onclick="showToast('HDMI 1: PlayStation 5', '🎮')" data-color="gold">
                        <div class="recent-icon-wrap" style="color:#f59e0b;">🎮</div>
                        <div class="recent-texts">
                            <span class="recent-name">HDMI 1</span>
                            <span class="recent-sub">PlayStation 5</span>
                        </div>
                    </div>
                </div>

                <!-- "Continue watching" Section -->
                <div class="section-row-header">
                    <h3 class="sec-title">▶ Continue watching</h3>
                    <span class="sec-more-link focusable" tabindex="0" role="button" onclick="launchApp('jellyfin')">Watch history →</span>
                </div>
                <div class="continue-grid">
                    {CONTINUE_WATCHING_CARDS}
                </div>

                <!-- Signature Bottom App Dock with Glossy Reflection -->
                <div class="tvm-bottom-dock">
                    <div class="dock-app-card focusable" tabindex="0" onclick="openLiveTV()" data-color="blue" style="background: linear-gradient(135deg, rgba(30, 64, 175, 0.75), rgba(15, 23, 42, 0.85));">
                        <span class="dock-icon">📺</span>
                        <span class="dock-app-name">Live TV</span>
                    </div>
                    <div class="dock-app-card focusable" tabindex="0" onclick="toggleQuranRadio()" data-color="teal" style="background: linear-gradient(135deg, rgba(6, 95, 70, 0.75), rgba(15, 23, 42, 0.85));">
                        <span class="dock-icon">📻</span>
                        <span class="dock-app-name">Quran Radio</span>
                    </div>
                    <div class="dock-app-card focusable" tabindex="0" onclick="launchApp('tod')" data-color="green" style="background: linear-gradient(135deg, rgba(4, 120, 87, 0.75), rgba(15, 23, 42, 0.85));">
                        <span class="dock-icon">⚽</span>
                        <span class="dock-app-name">TOD Sports</span>
                    </div>
                    <div class="dock-app-card focusable" tabindex="0" onclick="launchApp('netflix')" data-color="red" style="background: linear-gradient(135deg, rgba(153, 27, 27, 0.75), rgba(15, 23, 42, 0.85));">
                        <span class="dock-icon" style="color:#e50914; font-weight:900; font-size:42px; text-shadow:0 0 15px rgba(229,9,20,0.7);">N</span>
                        <span class="dock-app-name">Netflix</span>
                    </div>
                    <div class="dock-app-card focusable" tabindex="0" onclick="launchApp('jellyfin')" data-color="cyan" style="background: linear-gradient(135deg, rgba(14, 116, 144, 0.75), rgba(15, 23, 42, 0.85));">
                        <img src="/api/app-icon" class="dock-avatar-img" alt="NetFelix">
                        <span class="dock-app-name">NetFelix</span>
                    </div>
                    <div class="dock-app-card focusable" tabindex="0" onclick="launchApp('youtube')" data-color="red" style="background: linear-gradient(135deg, rgba(185, 28, 28, 0.75), rgba(15, 23, 42, 0.85));">
                        <span class="dock-icon" style="color:#ff0000; text-shadow:0 0 15px rgba(255,0,0,0.7);">▶</span>
                        <span class="dock-app-name">YouTube</span>
                    </div>
                    <div class="dock-app-card focusable" tabindex="0" onclick="openPrayerHub()" data-color="teal" style="background: linear-gradient(135deg, rgba(15, 118, 110, 0.75), rgba(15, 23, 42, 0.85));">
                        <span class="dock-icon" style="text-shadow:0 0 15px rgba(0,229,255,0.6);">🌙</span>
                        <span class="dock-app-name">Prayer Hub</span>
                    </div>
                    <div class="dock-app-card focusable" tabindex="0" onclick="openSearchModal()" data-color="blue" style="background: linear-gradient(135deg, rgba(107, 33, 168, 0.75), rgba(15, 23, 42, 0.85));">
                        <span class="dock-icon" style="color:#c084fc; text-shadow:0 0 15px rgba(192,132,252,0.6);">🔍</span>
                        <span class="dock-app-name">Download 4K</span>
                    </div>
                </div>

            </main>
        </div>

    </div>

    <!-- Fullscreen Prayer Times Hub Modal -->
    <div id="prayer-hub-modal">
        <div class="ph-top-bar">
            <div class="ph-title-group">
                <span style="font-size:12px; color:var(--cyan-accent); font-weight:800; letter-spacing:1.5px;">NETFELIX ISLAMIC HUB</span>
                <h1>Prayer times</h1>
                <p>Cairo · Egypt · Egyptian General Authority of Survey</p>
            </div>
            <div class="ph-action-btns">
                <button class="ph-pill-btn focusable" tabindex="0" onclick="toggleQuranRadio()">📻 Quran Radio</button>
                <button class="ph-pill-btn focusable" tabindex="0" onclick="window.location.reload()">Refresh times</button>
                <button class="ph-pill-btn focusable" tabindex="0" style="background:#e11d48;" onclick="closePrayerHub()">Back ↰</button>
            </div>
        </div>

        <div class="ph-row-1">
            <div class="ph-weather-card">
                <span style="font-size:48px;">🌙</span>
                <span style="font-size:38px; font-weight:900;">{WEATHER_TEMP}</span>
                <span style="color:#94a3b8; font-weight:700;">Cairo • Clear night</span>
            </div>
            <div class="ph-clock-card">
                <span style="font-size:26px;">🌙</span>
                <span class="ph-big-clock" id="ph-live-clock">{CLOCK_TIME}</span>
                <span style="color:#94a3b8; font-weight:700;">{DATE_STR} • 14 Jumādā al-ūlā 1448</span>
                <div style="background:rgba(0,229,255,0.15); border:1px solid var(--cyan-accent); padding:6px 16px; border-radius:9999px; margin-top:8px;">
                    <span style="color:var(--cyan-accent); font-weight:800;">Next prayer · {PRAYER_TARGET_NAME} {PRAYER_COUNTDOWN}</span>
                </div>
            </div>
        </div>

        <div class="ph-prayers-row">
            {PRAYER_BOXES_HTML}
        </div>

        <div class="ph-supplication-box">
            <p style="font-size:12px; color:#94a3b8; font-weight:800; text-transform:uppercase; margin-bottom:4px;">Daily supplication</p>
            <h2 class="ph-arabic-dhikr">سُبْحَانَ اللَّهِ وَبِحَمْدِهِ ، سُبْحَانَ اللَّهِ الْعَظِيمِ</h2>
            <p class="ph-dhikr-trans">Glory and praise belong to Allah, Glory be to Allah the Almighty.</p>
        </div>

        <footer style="margin-top:20px; font-size:11px; color:#64748b;">
            Adhan timings by Egyptian General Authority of Survey • Built for Eslam
        </footer>
    </div>

    <!-- AI Search & Downloader Modal -->
    <div id="search-downloader-modal">
        <div class="sd-box">
            <h2 style="font-size:24px; font-weight:900; color:#fff;">🔍 AI Media Search & Downloader</h2>
            <p style="color:#94a3b8; font-size:14px;">Request any movie, series, or live match. The AI downloader will fetch it automatically in 4K HDR.</p>
            <div class="sd-input-row">
                <input type="text" id="sd-query-input" class="sd-input focusable" aria-label="Movie or series title" placeholder="Enter movie or series title...">
                <button class="hero-cta-btn focusable" tabindex="0" onclick="submitDownloadRequest()">Download 4K</button>
            </div>
            <p style="font-size:12px; color:#94a3b8; font-weight:800; text-transform:uppercase;">Quick Trending Requests:</p>
            <div class="sd-tags-row">
                <div class="sd-tag-pill focusable" tabindex="0" onclick="quickRequest('Dune: Part Two')">Dune: Part Two</div>
                <div class="sd-tag-pill focusable" tabindex="0" onclick="quickRequest('Oppenheimer')">Oppenheimer</div>
                <div class="sd-tag-pill focusable" tabindex="0" onclick="quickRequest('Spider-Man: Across the Spider-Verse')">Spider-Man</div>
                <div class="sd-tag-pill focusable" tabindex="0" onclick="quickRequest('Deadpool & Wolverine')">Deadpool & Wolverine</div>
                <div class="sd-tag-pill focusable" tabindex="0" onclick="quickRequest('House of the Dragon')">House of the Dragon</div>
            </div>
            <button class="ph-pill-btn focusable" tabindex="0" style="align-self:flex-start; margin-top:10px; background:#e11d48;" onclick="closeSearchModal()">Close ↰</button>
        </div>
    </div>

    <!-- Apple TV Screensaver Mode Overlay -->
    <div id="screensaver-overlay">
        <img src="/api/wallpaper" class="ss-bg-image" alt="Eslam Memories">
        <div class="ss-hud-bottom">
            <div class="ss-glass-card">
                <span class="ss-clock" id="ss-live-clock">{CLOCK_TIME}</span>
                <p style="color:#94a3b8; font-size:14px; font-weight:700; margin-top:4px;">{DATE_STR} • Cairo, Egypt</p>
            </div>
            <div class="ss-glass-card">
                <span style="font-size:12px; color:var(--cyan-accent); font-weight:800; letter-spacing:1px;">NEXT PRAYER</span>
                <p style="font-size:24px; font-weight:900; color:#fff;" id="ss-prayer-timer">{PRAYER_TARGET_NAME} {PRAYER_COUNTDOWN}</p>
            </div>
        </div>
    </div>

    <!-- Live TV Fullscreen Stream Player Modal -->
    <div id="player-modal">
        <div class="player-bar">
            <span id="player-title" style="color:#fff; font-weight:800; font-size:17px;">Live Channel</span>
            <div style="display:flex; gap:10px; align-items:center;">
                <button class="focusable" onclick="openLiveTV()" style="background:#0284c7; border:none; color:#fff; padding:6px 18px; border-radius:9999px; font-family:inherit; font-size:14px; font-weight:800; cursor:pointer;">
                    📺 Open in TV App
                </button>
                <button class="focusable" onclick="closePlayer()" style="background:#e11d48; border:none; color:#fff; padding:6px 18px; border-radius:9999px; font-family:inherit; font-size:14px; font-weight:800; cursor:pointer;">
                    ✕ Close (Back)
                </button>
            </div>
        </div>
        <video id="tv-video-player" style="width:100%; height:100%; object-fit:contain;" controls autoplay playsinline></video>
    </div>

    <!-- Audio Player Bar (Quran Radio) -->
    <div id="audio-bar">
        <span>📻 إذاعة القرآن الكريم</span>
        <button class="focusable" onclick="toggleQuranRadio()" style="background:#e11d48; border:none; color:#fff; padding:4px 14px; border-radius:9999px; font-weight:800; cursor:pointer;">إيقاف ✕</button>
        <audio id="quran-audio-player" src="https://qurango.net/radio/tarateel" preload="none"></audio>
    </div>

    <!-- TV Toast Notification -->
    <div id="toast" class="tvm-toast">
        <span id="toast-icon">🚀</span>
        <span id="toast-text">Launching...</span>
    </div>

    <footer>
        Developed by Karim Aboushousha & Hassan Shehata • NetFelix TVMorph 4K Edition
    </footer>

    <script>
        let focusableElements = [];
        let currentFocusIndex = 0;
        let returnFocus = null;
        let nextPrayerSeconds = {PRAYER_REMAINING_SECS};
        let lastKeyTime = 0;
        const KEY_THROTTLE_MS = 90;

        // Screensaver Timer (Apple TV Mode)
        let screensaverTimer = null;
        const IDLE_TIMEOUT_MS = 90000; // 90 seconds

        function resetScreensaverTimer() {
            const ss = document.getElementById('screensaver-overlay');
            if (ss && ss.style.display === 'block') {
                ss.classList.remove('active');
                setTimeout(() => { ss.style.display = 'none'; }, 400);
            }
            clearTimeout(screensaverTimer);
            screensaverTimer = setTimeout(triggerScreensaver, IDLE_TIMEOUT_MS);
        }

        function triggerScreensaver() {
            // Don't trigger if video is playing
            const vModal = document.getElementById('player-modal');
            if (vModal && vModal.style.display === 'flex') return;

            const ss = document.getElementById('screensaver-overlay');
            if (ss) {
                ss.style.display = 'block';
                setTimeout(() => ss.classList.add('active'), 20);
            }
        }

        // WebAudio Tactile Navigation Synthesizer
        let audioCtx = null;
        function playNavSound(type = 'move') {
            try {
                if (!audioCtx) {
                    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                }
                if (audioCtx.state === 'suspended') {
                    audioCtx.resume();
                }
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain);
                gain.connect(audioCtx.destination);

                if (type === 'move') {
                    osc.frequency.setValueAtTime(440, audioCtx.currentTime);
                    osc.frequency.exponentialRampToValueAtTime(750, audioCtx.currentTime + 0.035);
                    gain.gain.setValueAtTime(0.06, audioCtx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.035);
                    osc.start();
                    osc.stop(audioCtx.currentTime + 0.035);
                } else if (type === 'enter') {
                    osc.frequency.setValueAtTime(550, audioCtx.currentTime);
                    osc.frequency.exponentialRampToValueAtTime(1100, audioCtx.currentTime + 0.06);
                    gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.06);
                    osc.start();
                    osc.stop(audioCtx.currentTime + 0.06);
                }
            } catch(e) {}
        }

        // Dynamic Ambilight Aura Shifts
        const AMBILIGHT_COLORS = {
            cyan: 'rgba(0, 229, 255, 0.22)',
            green: 'rgba(16, 185, 129, 0.25)',
            red: 'rgba(239, 68, 68, 0.25)',
            sky: 'rgba(56, 189, 248, 0.22)',
            teal: 'rgba(13, 148, 136, 0.25)',
            blue: 'rgba(37, 99, 235, 0.25)',
            gold: 'rgba(245, 158, 11, 0.25)'
        };

        function updateAmbilight(targetEl) {
            if (!targetEl) return;
            const colKey = targetEl.getAttribute('data-color') || 'cyan';
            const col = AMBILIGHT_COLORS[colKey] || AMBILIGHT_COLORS.cyan;
            const halo = document.getElementById('ambilight-halo');
            if (halo) {
                halo.style.background = `radial-gradient(circle at 60% 40%, ${col} 0%, transparent 65%)`;
            }
        }

        let toastTimer = null;
        function showToast(text, icon = '🚀') {
            const toast = document.getElementById('toast');
            document.getElementById('toast-icon').textContent = icon;
            document.getElementById('toast-text').textContent = text;
            toast.classList.add('show');
            clearTimeout(toastTimer);
            toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
        }

        let hlsInstance = null;

        function playChannel(url, title) {
            returnFocus = document.activeElement;
            playNavSound('enter');
            const modal = document.getElementById('player-modal');
            const video = document.getElementById('tv-video-player');
            const titleEl = document.getElementById('player-title');
            if (titleEl) titleEl.textContent = title || 'Live Channel';
            if (modal) modal.style.display = 'flex';
            refreshFocusables();
            const closeBtn = modal.querySelector('button');
            if (closeBtn) {
                const idx = focusableElements.indexOf(closeBtn);
                if (idx !== -1) setFocus(idx);
            }

            if (video) {
                if (hlsInstance) {
                    try { hlsInstance.destroy(); } catch(e) {}
                    hlsInstance = null;
                }

                if (window.Hls && Hls.isSupported()) {
                    hlsInstance = new Hls({
                        enableWorker: true,
                        lowLatencyMode: true,
                        backBufferLength: 60
                    });
                    hlsInstance.loadSource(url);
                    hlsInstance.attachMedia(video);
                    hlsInstance.on(Hls.Events.MANIFEST_PARSED, function() {
                        video.play().catch(e => console.log('Autoplay handled:', e));
                    });
                    hlsInstance.on(Hls.Events.ERROR, function(event, data) {
                        console.warn('HLS stream notice:', data);
                        if (data.fatal) {
                            switch(data.type) {
                                case Hls.ErrorTypes.NETWORK_ERROR:
                                    hlsInstance.startLoad();
                                    break;
                                case Hls.ErrorTypes.MEDIA_ERROR:
                                    hlsInstance.recoverMediaError();
                                    break;
                                default:
                                    try { hlsInstance.destroy(); } catch(e) {}
                                    video.src = url;
                                    video.play().catch(e => console.log(e));
                                    break;
                            }
                        }
                    });
                } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                    video.src = url;
                    video.play().catch(e => console.log('Playback error:', e));
                } else {
                    video.src = url;
                    video.play().catch(e => console.log('Playback error:', e));
                }
            }
        }

        function closePlayer() {
            playNavSound('move');
            const modal = document.getElementById('player-modal');
            const video = document.getElementById('tv-video-player');
            if (hlsInstance) {
                try { hlsInstance.destroy(); } catch(e) {}
                hlsInstance = null;
            }
            if (video) {
                video.pause();
                video.removeAttribute('src');
                video.load();
            }
            if (modal) modal.style.display = 'none';
            refreshFocusables();
            setFocus(Math.max(0, focusableElements.indexOf(returnFocus)));
        }

        function openLiveTV() {
            playNavSound('enter');
            showToast('Opening Live TV & Channels app...', '📡');
            launchApp('iptv');
        }

        function toggleQuranRadio() {
            playNavSound('enter');
            const audio = document.getElementById('quran-audio-player');
            const bar = document.getElementById('audio-bar');
            if (audio.paused) {
                audio.play().then(() => {
                    bar.style.display = 'flex';
                    showToast('إذاعة القرآن الكريم قيد التشغيل 🌙', '📻');
                }).catch(e => showToast('خطأ في تشغيل الإذاعة', '⚠️'));
            } else {
                audio.pause();
                bar.style.display = 'none';
                showToast('تم إيقاف إذاعة القرآن الكريم', '⏹️');
            }
        }

        function openPrayerHub() {
            returnFocus = document.activeElement;
            playNavSound('enter');
            document.getElementById('prayer-hub-modal').style.display = 'flex';
            refreshFocusables();
            const firstPrayerBox = document.querySelector('.ph-prayer-box.active-prayer') || document.querySelector('.ph-pill-btn');
            if (firstPrayerBox) {
                const idx = focusableElements.indexOf(firstPrayerBox);
                if (idx !== -1) setFocus(idx);
            }
        }

        function closePrayerHub() {
            playNavSound('move');
            document.getElementById('prayer-hub-modal').style.display = 'none';
            refreshFocusables();
            setFocus(Math.max(0, focusableElements.indexOf(returnFocus)));
        }

        function openSearchModal() {
            returnFocus = document.activeElement;
            playNavSound('enter');
            document.getElementById('search-downloader-modal').style.display = 'flex';
            refreshFocusables();
            const input = document.getElementById('sd-query-input');
            if (input) input.focus();
        }

        function closeSearchModal() {
            playNavSound('move');
            document.getElementById('search-downloader-modal').style.display = 'none';
            refreshFocusables();
            setFocus(Math.max(0, focusableElements.indexOf(returnFocus)));
        }

        async function quickRequest(title) {
            showToast(`جارٍ طلب ${title}...`, '📥');
            try {
                const response = await fetch('/api/request', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: title})
                });
                const result = await response.json();
                if (!response.ok || result.success === false) {
                    showToast(result.error || 'Could not submit your request. Please retry.', '⚠️');
                    return;
                }
                showToast('Request sent. You can follow it in NetFelix Studio.', '📥');
                setTimeout(closeSearchModal, 1500);
            } catch (error) {
                showToast('Could not reach NetFelix. Your request was not confirmed.', '⚠️');
            }
        }

        function submitDownloadRequest() {
            const input = document.getElementById('sd-query-input');
            if (input && input.value.trim()) {
                quickRequest(input.value.trim());
            }
        }

        function scrollToMatches() {
            const el = document.getElementById('matches-section-anchor');
            if (el) {
                el.scrollIntoView({behavior: 'smooth', block: 'start'});
                const firstMatch = document.querySelector('.home-match-card');
                if (firstMatch) {
                    const idx = focusableElements.indexOf(firstMatch);
                    if (idx !== -1) setFocus(idx);
                }
            }
        }

        async function launchApp(appId) {
            playNavSound('enter');
            showToast(`Opening ${appId}...`, '🚀');
            try {
                const response = await fetch('/api/tv/launch_app', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({app: appId})
                });
                const result = await response.json();
                if (!response.ok || !result.success) {
                    showToast(result.error || `Could not open ${appId}.`, '⚠️');
                    return;
                }
                showToast(`Launch command sent: ${appId}`, '▶');
            } catch (error) {
                showToast('Could not reach the TV controls. Please retry.', '⚠️');
            }
        }

        // Live Clocks & Prayer Countdown Ticker
        function updateTimers() {
            const now = new Date();
            let hours = now.getHours();
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12 || 12;
            const timeStr = window.NetFelixAppearance && window.NetFelixAppearance.clock24 ? `${String(now.getHours()).padStart(2, '0')}:${minutes}` : `${hours}:${minutes} ${ampm}`;

            const topClock = document.getElementById('live-clock-time');
            if (topClock) topClock.textContent = timeStr;
            const phClock = document.getElementById('ph-live-clock');
            if (phClock) phClock.textContent = timeStr;
            const ssClock = document.getElementById('ss-live-clock');
            if (ssClock) ssClock.textContent = timeStr;

            if (nextPrayerSeconds > 0) {
                nextPrayerSeconds--;
                const h = Math.floor(nextPrayerSeconds / 3600);
                const m = Math.floor((nextPrayerSeconds % 3600) / 60);
                const s = nextPrayerSeconds % 60;
                const fmt = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
                const heroTimer = document.getElementById('hero-prayer-timer');
                if (heroTimer) heroTimer.textContent = fmt;
                const ssTimer = document.getElementById('ss-prayer-timer');
                if (ssTimer) ssTimer.textContent = fmt;

                if (nextPrayerSeconds === 0) {
                    showToast('حان الآن موعد الأذان المبارك 🕌', '🌙');
                }
            }
        }

        // Spatial Navigation Engine
        function refreshFocusables() {
            if (window.NetFelixPreviewMode) return;
            const all = Array.from(document.querySelectorAll('.focusable'));
            focusableElements = all.filter(el => {
                if (el.offsetParent === null) return false;
                const modal = el.closest('#prayer-hub-modal, #search-downloader-modal, #player-modal, #screensaver-overlay');
                if (modal && modal.style.display !== 'flex' && modal.style.display !== 'block') return false;
                const activeModal = document.querySelector('#prayer-hub-modal[style*="display: flex"], #search-downloader-modal[style*="display: flex"], #player-modal[style*="display: flex"]');
                if (activeModal && !modal) return false;
                return true;
            });

            focusableElements.forEach((el, idx) => {
                el.tabIndex = 0;
                el.onmouseenter = () => setFocus(idx);
                el.onfocus = () => {
                    currentFocusIndex = idx;
                    document.querySelectorAll('.focused').forEach(item => item.classList.remove('focused'));
                    el.classList.add('focused');
                    updateAmbilight(el);
                };
            });

            if (focusableElements.length > 0 && !document.querySelector('.focusable.focused')) {
                setFocus(0);
            }
        }

        function setFocus(index) {
            if (index < 0 || index >= focusableElements.length) return;
            document.querySelectorAll('.focused').forEach(el => el.classList.remove('focused'));
            currentFocusIndex = index;
            const target = focusableElements[currentFocusIndex];
            target.classList.add('focused');
            target.focus({preventScroll: true});

            updateAmbilight(target);

            // Smart non-jarring scroll
            const r = target.getBoundingClientRect();
            const vh = window.innerHeight;
            const margin = 80;
            if (r.top < margin) {
                window.scrollBy({ top: r.top - margin, behavior: 'smooth' });
            } else if (r.bottom > vh - margin) {
                window.scrollBy({ top: r.bottom - (vh - margin), behavior: 'smooth' });
            }
        }

        // 2D Spatial Navigation
        function moveFocus(direction) {
            refreshFocusables();
            if (!focusableElements.length) return;
            const current = focusableElements[currentFocusIndex];
            if (!current) { setFocus(0); return; }
            const curRect = current.getBoundingClientRect();
            const curCenter = { x: curRect.left + curRect.width / 2, y: curRect.top + curRect.height / 2 };

            let bestCandidate = null;
            let bestScore = Infinity;

            focusableElements.forEach(candidate => {
                if (candidate === current) return;
                const targetRect = candidate.getBoundingClientRect();
                const targetCenter = { x: targetRect.left + targetRect.width / 2, y: targetRect.top + targetRect.height / 2 };

                let isEligible = false;
                let primaryDiff = 0;
                let secondaryDiff = 0;
                let overlap = 0;

                if (direction === 'right') {
                    if (targetRect.left >= curRect.left + 5) {
                        isEligible = true;
                        primaryDiff = targetRect.left - curRect.right;
                        secondaryDiff = Math.abs(targetCenter.y - curCenter.y);
                        overlap = Math.max(0, Math.min(curRect.bottom, targetRect.bottom) - Math.max(curRect.top, targetRect.top));
                    }
                } else if (direction === 'left') {
                    if (targetRect.right <= curRect.right - 5) {
                        isEligible = true;
                        primaryDiff = curRect.left - targetRect.right;
                        secondaryDiff = Math.abs(targetCenter.y - curCenter.y);
                        overlap = Math.max(0, Math.min(curRect.bottom, targetRect.bottom) - Math.max(curRect.top, targetRect.top));
                    }
                } else if (direction === 'down') {
                    if (targetRect.top >= curRect.top + 5) {
                        isEligible = true;
                        primaryDiff = targetRect.top - curRect.bottom;
                        secondaryDiff = Math.abs(targetCenter.x - curCenter.x);
                        overlap = Math.max(0, Math.min(curRect.right, targetRect.right) - Math.max(curRect.left, targetRect.left));
                    }
                } else if (direction === 'up') {
                    if (targetRect.bottom <= curRect.bottom - 5) {
                        isEligible = true;
                        primaryDiff = curRect.top - targetRect.bottom;
                        secondaryDiff = Math.abs(targetCenter.x - curCenter.x);
                        overlap = Math.max(0, Math.min(curRect.right, targetRect.right) - Math.max(curRect.left, targetRect.left));
                    }
                }

                if (isEligible) {
                    const pDist = Math.max(0, primaryDiff);
                    const score = pDist + (secondaryDiff * 4) - (overlap * 3);
                    if (score < bestScore) {
                        bestScore = score;
                        bestCandidate = candidate;
                    }
                }
            });

            // Section Fallbacks
            if (!bestCandidate) {
                const inDock = current.closest('.left-vertical-dock');
                const inTopNav = current.closest('.tvm-nav-tabs') || current.closest('.tvm-topbar');
                const inMain = current.closest('.main-content');

                const rightMenu = document.body.getAttribute('data-nf-menu') === 'right';
                if (direction === (rightMenu ? 'right' : 'left') && inMain) {
                    const dockItems = focusableElements.filter(el => el.closest('.left-vertical-dock'));
                    let closestDock = null, minD = Infinity;
                    dockItems.forEach(d => {
                        const r = d.getBoundingClientRect();
                        const diff = Math.abs((r.top + r.height/2) - curCenter.y);
                        if (diff < minD) { minD = diff; closestDock = d; }
                    });
                    if (closestDock) bestCandidate = closestDock;
                } else if (direction === (rightMenu ? 'left' : 'right') && inDock) {
                    const mainItems = focusableElements.filter(el => el.closest('.main-content'));
                    let closestMain = null, minD = Infinity;
                    mainItems.forEach(m => {
                        const r = m.getBoundingClientRect();
                        const diff = Math.abs((r.top + r.height/2) - curCenter.y);
                        if (diff < minD) { minD = diff; closestMain = m; }
                    });
                    if (closestMain) bestCandidate = closestMain;
                } else if (direction === 'up' && (inMain || inDock)) {
                    const navTabs = Array.from(document.querySelectorAll('.tvm-nav-tabs .focusable'));
                    if (navTabs.length) bestCandidate = navTabs[0];
                } else if (direction === 'down' && inTopNav) {
                    const hero = document.querySelector('.tvm-hero-card');
                    if (hero) bestCandidate = hero;
                }
            }

            if (bestCandidate) {
                const newIndex = focusableElements.indexOf(bestCandidate);
                if (newIndex !== -1) {
                    setFocus(newIndex);
                    playNavSound('move');
                }
            }
        }

        // Remote Keydown Listeners (Samsung Tizen Remote & Keyboard)
        window.addEventListener('keydown', (e) => {
            resetScreensaverTimer();

            const editing = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA';
            if (editing && ![27, 10009, 38, 40].includes(e.keyCode)) {
                if (e.keyCode === 13) { submitDownloadRequest(); e.preventDefault(); }
                return;
            }
            if (document.getElementById('player-modal').style.display === 'flex' &&
                ![27, 10009].includes(e.keyCode) && e.target.tagName === 'VIDEO') return;

            const now = Date.now();
            if (now - lastKeyTime < KEY_THROTTLE_MS && [37, 38, 39, 40].includes(e.keyCode)) {
                e.preventDefault();
                return;
            }
            lastKeyTime = now;

            const key = e.keyCode;
            switch(key) {
                case 37: // Left
                    moveFocus('left');
                    e.preventDefault();
                    break;
                case 38: // Up
                    moveFocus('up');
                    e.preventDefault();
                    break;
                case 39: // Right
                    moveFocus('right');
                    e.preventDefault();
                    break;
                case 40: // Down
                    moveFocus('down');
                    e.preventDefault();
                    break;
                case 13: // Enter / OK
                    if (focusableElements[currentFocusIndex]) {
                        playNavSound('enter');
                        focusableElements[currentFocusIndex].click();
                    }
                    e.preventDefault();
                    break;
                case 10009: // Tizen Return / Back
                case 27: // Escape
                    const vModal = document.getElementById('player-modal');
                    if (vModal && getComputedStyle(vModal).display !== 'none') {
                        closePlayer();
                        e.preventDefault();
                        return;
                    }
                    const sModal = document.getElementById('search-downloader-modal');
                    if (sModal && getComputedStyle(sModal).display !== 'none') {
                        closeSearchModal();
                        e.preventDefault();
                        return;
                    }
                    const pHModal = document.getElementById('prayer-hub-modal');
                    if (pHModal && getComputedStyle(pHModal).display !== 'none') {
                        closePrayerHub();
                        e.preventDefault();
                        return;
                    }
                    try {
                        if (window.tizen && window.tizen.application) {
                            window.tizen.application.getCurrentApplication().exit();
                        }
                    } catch(err) {}
                    break;
            }
        });

        // Initialize timers & screensaver
        setInterval(updateTimers, 1000);
        updateTimers();
        refreshFocusables();
        resetScreensaverTimer();
    </script>
    <script src="/tv-ui/visuals.js"></script>
    <script src="/tv-ui/appearance.js"></script>
    <script src="/tv-ui/remote.js"></script>
</body>
</html>
"""


def render_home_matches_cards(matches):
    """Renders the top 4-8 matches directly onto the Home Screen."""
    if not matches:
        return "<p style='color:#94a3b8; font-size:15px; padding:15px;'>No matches scheduled for today.</p>"

    cards = []
    for m in matches[:4]:
        is_live = m.get("is_live", False)
        status_cls = "live" if is_live else ""
        t1 = m.get("team1", "Team 1")
        t2 = m.get("team2", "Team 2")
        s1 = m.get("score1", "")
        s2 = m.get("score2", "")
        score_display = f"{s1} - {s2}" if (s1 and s2) else "VS"
        logo1 = m.get("team1_logo", "") or "https://ssl.gstatic.com/onebox/media/sports/logos/9oN7kS9xJqG0kC9n.png"
        logo2 = m.get("team2_logo", "") or "https://ssl.gstatic.com/onebox/media/sports/logos/9oN7kS9xJqG0kC9n.png"
        tourn = m.get("tournament", "Championship")
        status = m.get("status", "Today")

        cards.append(f'''
            <div class="home-match-card focusable" tabindex="0"
                 onclick="playChannel('http://192.168.1.15:8092/api/sports/stream/bein1', '{t1} vs {t2}')"
                 data-color="green"
                 style="background: linear-gradient(145deg, rgba(12, 20, 42, 0.88) 0%, rgba(6, 78, 59, 0.28) 100%);">
                <div class="hm-tourn-bar">
                    <span>🏆 {tourn}</span>
                    <span class="hm-status-tag {status_cls}">{status}</span>
                </div>
                <div class="hm-teams-row">
                    <div class="hm-team-box">
                        <img src="{logo1}" class="hm-team-logo" alt="{t1}" onerror="this.onerror=null; this.style.display='none';">
                        <span class="hm-team-name">{t1}</span>
                    </div>
                    <div class="hm-score-center">
                        <span class="hm-score-val">{score_display}</span>
                    </div>
                    <div class="hm-team-box">
                        <img src="{logo2}" class="hm-team-logo" alt="{t2}" onerror="this.onerror=null; this.style.display='none';">
                        <span class="hm-team-name">{t2}</span>
                    </div>
                </div>
                <div class="hm-action-hint">
                    <span style="color:var(--cyan-accent); font-weight:800;">⚡ beIN Sports 1 HD</span> · <span>▶ تشغيل البث المباشر</span>
                </div>
            </div>
        ''')
    return "\n".join(cards)


def render_continue_watching(resume_items):
    """Renders the 3 widescreen Continue Watching cards with real artwork and progress."""
    cards = []

    # Card 1: Last Live Channel (beIN Sports 1 HD)
    cards.append('''
        <div class="continue-card focusable" tabindex="0" onclick="playChannel('http://192.168.1.15:8092/api/sports/stream/bein1', 'beIN Sports 1 HD')"
             style="background-image: url('https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=900&auto=format&fit=crop');"
             data-color="green">
            <div class="continue-card-content">
                <span class="cont-top-badge">📡 Channel • Live HD</span>
                <h4 class="cont-title">beIN Sports 1 HD [1080p]</h4>
                <div class="progress-track">
                    <div class="progress-fill" style="width: 100%;"></div>
                </div>
                <div class="cont-footer-info">
                    <span>NileSat & Sports Network</span>
                    <span>▶ Watch Live</span>
                </div>
            </div>
        </div>
    ''')

    # Card 2: Last Movie / Resume item 1
    if resume_items and len(resume_items) > 0:
        item = resume_items[0]
        title = item.get("title", "MobLand: Blank Curtain")
        pct = item.get("pct", 17)
        img_url = item.get("backdrop", "")
    else:
        title = "MobLand: Blank Curtain"
        pct = 17
        img_url = "https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?q=80&w=900&auto=format&fit=crop"

    cards.append(f'''
        <div class="continue-card focusable" tabindex="0" onclick="launchApp('jellyfin')"
             style="background-image: url('{img_url}');"
             data-color="cyan">
            <div class="continue-card-content">
                <span class="cont-top-badge">🍿 Movie • 4K HDR</span>
                <h4 class="cont-title">{title}</h4>
                <div class="progress-track">
                    <div class="progress-fill" style="width: {pct}%;"></div>
                </div>
                <div class="cont-footer-info">
                    <span>▶ {pct}% watched</span>
                    <span>Resume</span>
                </div>
            </div>
        </div>
    ''')

    # Card 3: Last Series / Resume item 2
    if resume_items and len(resume_items) > 1:
        item = resume_items[1]
        title = item.get("title", "See: The Lowlands")
        pct = item.get("pct", 18)
        img_url = item.get("backdrop", "")
    else:
        title = "See: The Lowlands"
        pct = 18
        img_url = "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=900&auto=format&fit=crop"

    cards.append(f'''
        <div class="continue-card focusable" tabindex="0" onclick="launchApp('jellyfin')"
             style="background-image: url('{img_url}');"
             data-color="sky">
            <div class="continue-card-content">
                <span class="cont-top-badge">📺 Series • S1 : E4</span>
                <h4 class="cont-title">{title}</h4>
                <div class="progress-track">
                    <div class="progress-fill" style="width: {pct}%;"></div>
                </div>
                <div class="cont-footer-info">
                    <span>▶ {pct}% watched</span>
                    <span>Resume</span>
                </div>
            </div>
        </div>
    ''')

    return "\n".join(cards)


def render_prayer_boxes(prayer_data):
    """Renders the 6 prayer time boxes from Photo 3."""
    if not prayer_data or not prayer_data.get("timings"):
        return ""
    timings = prayer_data["timings"]
    next_p = prayer_data.get("next", {})
    prayers = [
        ("Fajr", timings.get("fajr", "05:36")),
        ("Sunrise", timings.get("sunrise", "07:04")),
        ("Dhuhr", timings.get("dhuhr", "12:39")),
        ("Asr", timings.get("asr", "15:51")),
        ("Maghrib", timings.get("maghrib", "18:14")),
        ("Isha", timings.get("isha", "19:32")),
    ]
    boxes = []
    for name, t_str in prayers:
        is_active = next_p and next_p.get("name_en") == name
        active_cls = "active-prayer" if is_active else ""
        boxes.append(f'''
            <div class="ph-prayer-box focusable {active_cls}" tabindex="0" data-color="teal">
                <span class="ph-p-name">{name}</span>
                <span class="ph-p-time">{t_str}</span>
            </div>
        ''')
    return "\n".join(boxes)


def get_rendered_html() -> str:
    """Pre-renders TVMorph HTML with 100% completed markup and zero loading placeholders."""
    try:
        data = get_dashboard_data()

        weather_temp = data.get("weather", {}).get("temp", "28°")
        clock_time = data.get("clock", "08:15 PM")
        date_str = data.get("date", "Sun, Oct 25")

        next_p = data.get("prayer", {}).get("next", {})
        prayer_target = next_p.get("name_en", "Fajr")
        prayer_countdown = next_p.get("countdown", "03:15:00")
        prayer_rem_secs = next_p.get("diff_secs", 11700)

        resume_items = data.get("resume", [])
        matches = data.get("matches", [])

        continue_watching_html = render_continue_watching(resume_items)
        prayer_boxes_html = render_prayer_boxes(data.get("prayer"))
        home_matches_html = render_home_matches_cards(matches)

        rendered = TV_DASHBOARD_TEMPLATE
        rendered = rendered.replace("{WEATHER_TEMP}", weather_temp)
        rendered = rendered.replace("{CLOCK_TIME}", clock_time)
        rendered = rendered.replace("{DATE_STR}", date_str)
        rendered = rendered.replace("{PRAYER_TARGET_NAME}", prayer_target)
        rendered = rendered.replace("{PRAYER_COUNTDOWN}", prayer_countdown)
        rendered = rendered.replace("{PRAYER_REMAINING_SECS}", str(prayer_rem_secs))
        rendered = rendered.replace("{CONTINUE_WATCHING_CARDS}", continue_watching_html)
        rendered = rendered.replace("{PRAYER_BOXES_HTML}", prayer_boxes_html)
        rendered = rendered.replace("{HOME_MATCHES_CARDS}", home_matches_html)

        return rendered

    except Exception as e:
        logger.error(f"Error rendering TVMorph HTML: {e}")
        return TV_DASHBOARD_TEMPLATE


if __name__ == "__main__":
    print(get_rendered_html()[:400])
