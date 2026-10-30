#!/usr/bin/env python3
"""
NetFelix AI Personalized Recommendation & Movie Matchmaker Engine
Supports:
1. Local Library Matching ("متوفر في مكتبتك جاهز للعرض الفوري")
2. Trending Discoveries via Jellyseerr ("سهرة مقترحة للتحميل والمشاهدة")
3. Natural Language Genre/Mood Query Matching
"""

import os
from local_env import load_local_env
load_local_env()
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
JELLYSEERR_KEY = os.getenv("JELLYSEERR_API_KEY", "")
JELLYFIN_URL = "http://127.0.0.1:8096"
JELLYFIN_KEY = os.getenv("JELLYFIN_API_KEY", "")
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


def pick_library_movie(query=None):
    """Picks a movie from Jellyfin library, optionally matching query or genre."""
    try:
        url = f"{JELLYFIN_URL}/Items?IncludeItemTypes=Movie&Recursive=true&Fields=Overview,CommunityRating,Genres,ProductionYear&SortBy=Random"
        if query:
            url += f"&SearchTerm={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"Authorization": f'MediaBrowser Token="{JELLYFIN_KEY}"'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
            items = data.get("Items", [])

            if not items and query:
                url_genre = f"{JELLYFIN_URL}/Items?IncludeItemTypes=Movie&Recursive=true&Fields=Overview,CommunityRating,Genres,ProductionYear&Genres={urllib.parse.quote(query)}"
                req_g = urllib.request.Request(url_genre, headers={"Authorization": f'MediaBrowser Token="{JELLYFIN_KEY}"'})
                with urllib.request.urlopen(req_g, timeout=8) as resp_g:
                    items = json.load(resp_g).get("Items", [])

            if items:
                pick = random.choice(items[:10])
                rating = round(pick.get("CommunityRating") or 7.5, 1)
                genres = pick.get("Genres", [])
                year = str(pick.get("ProductionYear") or "")
                return {
                    "source": "library",
                    "id": pick.get("Id"),
                    "title": pick.get("Name"),
                    "releaseDate": year,
                    "rating": rating,
                    "genres": ", ".join(genres) if genres else "أفلام",
                    "overview": pick.get("Overview", "سهرة مميزة متوفرة وجاهزة للمشاهدة فوراً على سيرفرك!"),
                    "posterPath": f"{JELLYFIN_URL}/Items/{pick.get('Id')}/Images/Primary?fillWidth=500&quality=90"
                }
    except Exception as e:
        logger.warning(f"Error picking from library: {e}")
    return None


def pick_recommendation(query=None):
    """Picks either a local library favorite or a trending new discovery."""
    # If query is passed, try local library first
    if query:
        lib_match = pick_library_movie(query)
        if lib_match:
            return lib_match

    # Discover popular movies from Jellyseerr
    url = f"{JELLYSEERR_URL}/api/v1/discover/movies?sortBy=popularity.desc&page=1"
    req = urllib.request.Request(url, headers={"X-Api-Key": JELLYSEERR_KEY})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            results = data.get("results", [])
    except Exception as e:
        logger.error(f"Error fetching recommendations: {e}")
        # Fallback to library
        return pick_library_movie()

    existing = get_existing_titles()
    candidates = [
        m for m in results
        if m.get("title", "").lower() not in existing
        and (m.get("mediaInfo", {}).get("status") or 1) == 1
    ]

    if not candidates:
        # If no new candidates, pick from library!
        lib_pick = pick_library_movie()
        if lib_pick:
            return lib_pick
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
        "source": "discover",
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
    q = sys.argv[1] if len(sys.argv) > 1 else None
    print(pick_recommendation(q))
