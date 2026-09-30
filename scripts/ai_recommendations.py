#!/usr/bin/env python3
"""
NetFelix AI Personalized Recommendation Engine ("سهرة اليوم")
Picks a top trending or classic recommendation not yet in library,
with movie details, rating, poster, and 1-click download command.
"""

import os
import sys
import json
import random
import logging
import urllib.request
import urllib.parse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Recommendations] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Recommendations")

JELLYSEERR_URL = "http://127.0.0.1:5055"
JELLYSEERR_KEY = os.getenv("JELLYSEERR_API_KEY", "MTc5MDAxMjMyMzcwOTUxY2M5MjhmLWNiNzEtNGQwYi04YjY4LTQ0YTVhZDhlZGQ3YQ==")
JELLYFIN_URL = "http://127.0.0.1:8096"
JELLYFIN_KEY = os.getenv("JELLYFIN_API_KEY", "4d40f90a8b854cdcbb4faa23134d057b")
OUTPUT_FILE = Path("/home/dell/Desktop/My_NetFelix/config/daily_recommendation.json")


def get_existing_titles():
    """Fetches titles already existing in Jellyfin library."""
    try:
        url = f"{JELLYFIN_URL}/Items?IncludeItemTypes=Movie,Series&Recursive=true"
        req = urllib.request.Request(url, headers={"Authorization": f'MediaBrowser Token="{JELLYFIN_KEY}"'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            return {item.get("Name", "").lower() for item in data.get("Items", [])}
    except Exception as e:
        logger.warning(f"Could not fetch Jellyfin items: {e}")
        return set()


def pick_recommendation():
    existing = get_existing_titles()

    # Discover popular movies from Jellyseerr
    url = f"{JELLYSEERR_URL}/api/v1/discover/movies?sortBy=popularity.desc&page=1"
    req = urllib.request.Request(url, headers={"X-Api-Key": JELLYSEERR_KEY})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            results = data.get("results", [])
    except Exception as e:
        logger.error(f"Error fetching recommendations: {e}")
        return None

    # Filter out already owned movies
    candidates = [
        m for m in results
        if m.get("title", "").lower() not in existing
        and (m.get("mediaInfo", {}).get("status") or 1) == 1  # UNKNOWN status in Jellyseerr
    ]

    if not candidates:
        candidates = results

    if not candidates:
        return None

    pick = random.choice(candidates[:8])

    # Fetch Arabic details for the pick
    ar_overview = pick.get("overview", "")
    try:
        ar_url = f"{JELLYSEERR_URL}/api/v1/movie/{pick['id']}?language=ar"
        ar_req = urllib.request.Request(ar_url, headers={"X-Api-Key": JELLYSEERR_KEY})
        with urllib.request.urlopen(ar_req, timeout=5) as resp:
            ar_data = json.load(resp)
            if ar_data.get("overview"):
                ar_overview = ar_data["overview"]
    except Exception:
        pass

    rec = {
        "tmdbId": pick.get("id"),
        "title": pick.get("title"),
        "releaseDate": pick.get("releaseDate", "")[:4],
        "rating": round(pick.get("voteAverage", 0), 1),
        "overview": ar_overview or pick.get("overview", ""),
        "posterPath": f"https://image.tmdb.org/t/p/w500{pick.get('posterPath')}" if pick.get("posterPath") else "",
        "downloadApi": f"http://192.168.1.15:8092/api/request"
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)

    logger.info(f"Tonight's Pick generated: {rec['title']} ({rec['releaseDate']}) - Rating: {rec['rating']}")
    return rec


if __name__ == "__main__":
    pick_recommendation()
