#!/usr/bin/env python3
"""
NetFelix AI Universal Media Agent & Omni-Downloader
Full autonomous pipeline to download *ANYTHING*:
1. Arabic Movies, Plays, and Series (Archive.org, YouTube Full Releases, Web Scrapers).
2. Classic Disney & Cartoon Series in Egyptian Arabic Dubbing (Archive.org Suite, Stardima).
3. International / English Movies & Series with Auto Arabic Subtitles (Radarr, Sonarr, Prowlarr, Bazarr).
4. Direct URLs (YouTube, Dailymotion, direct MP4/m3u8, Magnets).
5. Headless Antigravity AI Agent (agy) for deep web scraping and rare content.
6. Embedded Dark-Mode Web Studio at http://<ip>:8092/ for direct downloads, queue tracking, and library control.
7. Jellyseerr Integration via Custom Action Buttons and Webhooks.
"""

import os
import sys
import time
import json
import re
import html
import queue
import logging
import threading
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("NetFelixAI")

# System & Media Paths
BASE_MEDIA = Path("/media/dell/Data1/netfelix_data/media")
MOVIES_DIR = BASE_MEDIA / "movies"
TV_DIR = BASE_MEDIA / "tv"
CONFIG_DIR = Path("/home/dell/Desktop/My_NetFelix/config")
HISTORY_FILE = CONFIG_DIR / "ai_media_history.json"
SCRIPTS_DIR = Path("/home/dell/Desktop/My_NetFelix/scripts")

# Service URLs & API Keys
JELLYSEERR_URL = os.getenv("JELLYSEERR_URL", "http://127.0.0.1:5055")
JELLYSEERR_KEY = os.getenv("JELLYSEERR_API_KEY", "MTc5MDAxMjMyMzcwOTUxY2M5MjhmLWNiNzEtNGQwYi04YjY4LTQ0YTVhZDhlZGQ3YQ==")
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "http://127.0.0.1:8096")
JELLYFIN_KEY = os.getenv("JELLYFIN_API_KEY", "4d40f90a8b854cdcbb4faa23134d057b")
JELLYFIN_AUTH = (
    'MediaBrowser Client="Jellyseerr", DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="'
    + JELLYFIN_KEY
    + '"'
)

RADARR_URL = os.getenv("RADARR_URL", "http://127.0.0.1:7878")
RADARR_KEY = os.getenv("RADARR_API_KEY", "6254cab200464f29a49cdb10060a5a26")
SONARR_URL = os.getenv("SONARR_URL", "http://127.0.0.1:8989")
SONARR_KEY = os.getenv("SONARR_API_KEY", "29adbfd421e4418bb35dfc5fcddff7e6")
PROWLARR_URL = os.getenv("PROWLARR_URL", "http://127.0.0.1:9696")
PROWLARR_KEY = os.getenv("PROWLARR_API_KEY", "5d8c7982ab084676bce252498714c760")
QBT_URL = os.getenv("QBT_URL", "http://127.0.0.1:8080")
BAZARR_URL = os.getenv("BAZARR_URL", "http://127.0.0.1:6767")
BAZARR_KEY = os.getenv("BAZARR_API_KEY", "36ee82e7b103b981f2097c25f859b9a1")

# Known Archive.org Egyptian Dub Catalog (70 Classic Disney Masterpieces)
ARCHIVE_EGYPTIAN_BASE = "https://archive.org/download/www.arabp-2p.net_202312/%D8%AF%D9%8A%D8%B2%D9%86%D9%89%20%D9%85%D8%AF%D8%A8%D9%84%D8%AC%20%D9%88%D8%A3%D9%81%D9%84%D8%A7%D9%85%20%D8%A3%D8%AE%D8%B1%D9%89/Dubbing%20Egyptian%20Suite/"

EGYPTIAN_MOVIES_MAP = {
    "aladdin": "Aladdin 1/Aladdin 1.By.Monster.mp4",
    "aladdin 2": "Aladdin 2/Aladdin 2.By.Monster.mp4",
    "aladdin ii": "Aladdin 2/Aladdin 2.By.Monster.mp4",
    "the return of jafar": "Aladdin 2/Aladdin 2.By.Monster.mp4",
    "aladdin 3": "Aladdin 3/Aladdin 3.By.Monster.mp4",
    "aladdin and the king of thieves": "Aladdin 3/Aladdin 3.By.Monster.mp4",
    "101 dalmatians": "101 Dalmatian/101 Dalmatian.By.Monster.mp4",
    "101 dalmatians ii": "101 Dalmatian 2/101 Dalmatian.2.By.Monster.mp4",
    "alice in wonderland": "Alice In Wonderland/Alice In Wonderland.mp4",
    "atlantis the lost empire": "Atlantis I -By.Monster/Atlantis I -By.Monster.mp4",
    "atlantis milo's return": "Atlantis II,By.Monster/Atlantis II,By.Monster.mp4",
    "bambi": "Bambi I/Bambi I.mp4",
    "bambi ii": "Bambi 2/Bambi.2.mp4",
    "beauty and the beast": "Beauty and the Beast/Beauty and the Beast.mp4",
    "bolt": "Bolt/Bolt.2008.DvDrip.mp4",
    "brother bear": "Brother Bear/Brother Bear 2003.mp4",
    "a bug's life": "Bug's Life/Bug's Life.mp4",
    "cars": "Cars/Cars[2006]DvDrip.mp4",
    "chicken little": "Chicken Little/Chicken Little.mp4",
    "cinderella": "Cinderella 1/Cinderella1.mp4",
    "cinderella ii": "Cinderella 2/Cinderella2.mp4",
    "dinosaur": "Dinosaur/Dinosaur.mp4",
    "dumbo": "Dumbo/Dumbo.mp4",
    "hercules": "Hercules/Hercules.mp4",
    "home on the range": "Home on The Range/Home on The Range.mp4",
    "lady and the tramp ii": "Lady.And.The.Tramp.2 [2000]/Lady.And.The.Tramp.2 [2000].mp4",
    "lilo & stitch": "Lilo And Stitch 1/Lilo And Stitch 1.mp4",
    "lilo and stitch": "Lilo And Stitch 1/Lilo And Stitch 1.mp4",
    "lilo & stitch 2": "Lilo And Stitch 2/Lilo And Stitch 2.mp4",
    "lilo & stitch 2: stitch has a glitch": "Lilo And Stitch 2/Lilo And Stitch 2.mp4",
    "the lion king": "Lion King 1/Lion King 1.mp4",
    "the lion king ii: simba's pride": "Lion King 2/Lion King 2.mp4",
    "the lion king 1 1/2": "Lion King 3/Lion King 3.mp4",
    "meet the robinsons": "Meet.The.Robinsons[2007]/Meet.The.Robinsons[2007].By.Monster.MST.mp4",
    "monsters, inc.": "Monesters inc/Monesters inc.By.Monster.MST.mp4",
    "monsters inc": "Monesters inc/Monesters inc.By.Monster.MST.mp4",
    "mulan": "Mulan 1/Mulan 1.mp4",
    "mulan ii": "Mulan 2/Mulan 2.mp4",
    "finding nemo": "Nemo/Nemo.By.Monster.MST.mp4",
    "pinocchio": "Pinocchio/Pinocchio.arabic.mp4",
    "pocahontas": "Pocahontas 1/Pocahontas 1.mp4",
    "pocahontas ii": "Pocahontas 2/Pocahontas 2.mp4",
    "ratatouille": "Ratatouille/Ratatouille.2007.mp4",
    "sleeping beauty": "Sleeping.Beauty.1959/Sleeping.Beauty.1959.By.Monster.mp4",
    "snow white and the seven dwarfs": "Snow White and the Seven Dwarfs/Snow White and the Seven Dwarfs.By.Monster.MST.mp4",
    "treasure planet": "TREASURE PLANET/TREASURE PLANET.DvDrip.By.Monster.mp4",
    "tarzan": "Tarzan 1/Tarzan 1.mp4",
    "tarzan ii": "Tarzan 2/Tarzan 2.mp4",
    "the emperor's new groove": "The Emperor New Groove/The Emperor New Groove.mp4",
    "the hunchback of notre dame": "The Hunchback of Notre Dame/The Hunchback of Notre Dame.By.Monster.MST.mp4",
    "the little mermaid": "The Little Mermaid I/The Little Mermaid I.mp4",
    "the little mermaid ii: return to the sea": "The Little Mermaid II/The Little Mermaid II.mp4",
    "the sword in the stone": "The Sword in the Stone/The Sword in the Stone.mp4",
    "the incredibles": "The.Incredibles.2004/The.Incredibles.2004..DVDRip.By.Monster.mp4",
    "the princess and the frog": "The.Princess.and.the.Frog.2009/The.Princess.and.the.Frog.2009.mp4",
    "the rescuers": "The.Rescuers/The.Rescuers.By.Monster.MST.mp4",
    "toy story": "Toy story I/Toy story I.By.Monster.MST.mp4",
    "toy story 2": "Toy story II/Toy story II.By.Monster.MST.mp4",
    "toy story 3": "Toy.Story.3.2010/Toy.Story.3.2010.DVDRip.Arabic.By.Monster.mp4",
    "up": "Up.2009/Up.2009.DVDRip.By.Monster.MST.mp4",
    "wall-e": "WALL-E.2008/WALL-E.2008.DVDRip.By.Monster.mp4",
    "peter pan": "peter.Pan 1/peter.Pan 1.mp4",
    "peter pan 2": "peter.Pan 2/peter.Pan 2.mp4",
}

# In-memory Job Queue & History
JOB_QUEUE = queue.Queue()
ACTIVE_JOB = None
JOB_HISTORY = []


def load_history():
    global JOB_HISTORY
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                JOB_HISTORY = json.load(f)
        except Exception:
            JOB_HISTORY = []


def save_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(JOB_HISTORY[-100:], f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")


def is_arabic_text(text):
    """Check if string contains Arabic characters."""
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def refresh_jellyfin():
    try:
        req = urllib.request.Request(
            f"{JELLYFIN_URL}/Library/Refresh",
            data=b"",
            headers={"Authorization": JELLYFIN_AUTH},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info(f"[Jellyfin] Library scan triggered (Status {resp.status}).")
    except Exception as e:
        logger.warning(f"[Jellyfin] Library scan note: {e}")


def refresh_jellyseerr():
    try:
        req = urllib.request.Request(
            f"{JELLYSEERR_URL}/api/v1/settings/jobs/jellyfin-recently-added-scan/run",
            data=b"",
            headers={"X-Api-Key": JELLYSEERR_KEY},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info(f"[Jellyseerr] Availability sync triggered (Status {resp.status}).")
    except Exception as e:
        logger.warning(f"[Jellyseerr] Sync note: {e}")


def run_subtitle_sync(target_path=None):
    """Triggers subtitle sync script to extract and translate subtitles to Arabic."""
    def _run():
        try:
            cmd = ["/usr/bin/python3", str(SCRIPTS_DIR / "sync_subtitles.py")]
            subprocess.run(cmd, timeout=300, capture_output=True)
            logger.info("[Subtitles] Arabic subtitle synchronization completed.")
        except Exception as e:
            logger.warning(f"[Subtitles] Note during sync: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def fetch_jellyseerr_metadata(media_type, tmdb_id):
    """Fetches English and Arabic metadata for TMDb ID from Jellyseerr."""
    meta = {"en": {}, "ar": {}}
    for lang in ("en", "ar"):
        try:
            url = f"{JELLYSEERR_URL}/api/v1/{media_type}/{tmdb_id}?language={lang}"
            req = urllib.request.Request(url, headers={"X-Api-Key": JELLYSEERR_KEY})
            with urllib.request.urlopen(req, timeout=10) as resp:
                meta[lang] = json.load(resp)
        except Exception as e:
            logger.warning(f"Metadata fetch error ({lang}) for {media_type}/{tmdb_id}: {e}")

    en_title = meta["en"].get("title") or meta["en"].get("name") or ""
    ar_title = meta["ar"].get("title") or meta["ar"].get("name") or en_title
    year = ""
    release_date = meta["en"].get("releaseDate") or meta["en"].get("firstAirDate") or ""
    if release_date:
        year = release_date.split("-")[0]
    genres = [g.get("name", "") for g in meta["en"].get("genres", [])]
    orig_lang = meta["en"].get("originalLanguage") or ""

    return {
        "media_type": media_type,
        "tmdb_id": tmdb_id,
        "title_en": en_title,
        "title_ar": ar_title,
        "year": year,
        "genres": genres,
        "original_language": orig_lang,
        "overview": meta["ar"].get("overview") or meta["en"].get("overview") or "",
        "poster_path": meta["en"].get("posterPath") or "",
    }


def find_archive_egyptian_movie(title_en):
    """Matches an English movie title against 70 classic Egyptian dubs on Archive.org."""
    clean_en = re.sub(r"[^a-z0-9 ]", "", title_en.lower()).strip()
    if clean_en in EGYPTIAN_MOVIES_MAP:
        return ARCHIVE_EGYPTIAN_BASE + urllib.parse.quote(EGYPTIAN_MOVIES_MAP[clean_en])
    for key, path in EGYPTIAN_MOVIES_MAP.items():
        if key in clean_en or clean_en in key:
            return ARCHIVE_EGYPTIAN_BASE + urllib.parse.quote(path)
    return None


def search_archive_arabic_media(query):
    """Searches Archive.org for full Arabic movies, plays, or shows."""
    clean_q = re.sub(r"^(فيلم|مسرحية|مسلسل|حلقات|كرتون)\s+", "", query.strip()).strip()
    search_q = f'title:("{clean_q}") AND mediatype:(movies)'
    url = f"https://archive.org/advancedsearch.php?q={urllib.parse.quote(search_q)}&fl[]=identifier,title,downloads&sort[]=downloads+desc&output=json&rows=3"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                ident = doc["identifier"]
                meta_url = f"https://archive.org/metadata/{ident}/files"
                meta_req = urllib.request.Request(meta_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(meta_req, timeout=10) as mr:
                    files = json.load(mr).get("result", [])
                    for f in files:
                        name = f.get("name", "")
                        size = int(f.get("size", 0))
                        if name.endswith(".mp4") and size > 80 * 1024 * 1024:
                            download_url = f"https://archive.org/download/{ident}/{urllib.parse.quote(name)}"
                            logger.info(f"Archive.org found: {doc['title']} -> {download_url}")
                            return download_url
    except Exception as e:
        logger.warning(f"Archive.org search error: {e}")
    return None


def search_youtube_full_movie(query):
    """Searches YouTube via yt-dlp for full Arabic movies or long-form videos (>40 mins)."""
    try:
        clean_q = re.sub(r"^(فيلم|مسرحية|مسلسل|حلقات|كرتون)\s+", "", query.strip()).strip()
        search_terms = f"{query} كامل HD" if ("مسرحية" in query or "مسلسل" in query) else f"فيلم {clean_q} كامل HD"
        cmd = [
            "/home/dell/.local/bin/yt-dlp",
            f"ytsearch3:{search_terms}",
            "--dump-json",
            "--default-search", "ytsearch",
            "--no-playlist"
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        for line in p.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                item = json.loads(line)
                duration = item.get("duration", 0)
                if duration > 2400:  # > 40 minutes
                    url = item.get("webpage_url")
                    logger.info(f"YouTube full movie found: '{item.get('title')}' ({round(duration/60)} min) -> {url}")
                    return url
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"YouTube search error: {e}")
    return None


def add_to_radarr(tmdb_id, title, year=None):
    """Adds a movie to Radarr and commands it to search across all Prowlarr indexers."""
    try:
        # Check if already added
        req = urllib.request.Request(f"{RADARR_URL}/api/v3/movie", headers={"X-Api-Key": RADARR_KEY})
        with urllib.request.urlopen(req, timeout=10) as resp:
            existing = json.load(resp)
        for m in existing:
            if m.get("tmdbId") == tmdb_id:
                cmd_data = json.dumps({"name": "MoviesSearch", "movieIds": [m["id"]]}).encode("utf-8")
                cmd_req = urllib.request.Request(
                    f"{RADARR_URL}/api/v3/command",
                    data=cmd_data,
                    headers={"X-Api-Key": RADARR_KEY, "Content-Type": "application/json"}
                )
                urllib.request.urlopen(cmd_req, timeout=10)
                logger.info(f"[Radarr] Triggered search for already tracked movie: {title}")
                return True, "Triggered search in Radarr"

        # Lookup by TMDb ID
        req = urllib.request.Request(f"{RADARR_URL}/api/v3/movie/lookup?term=tmdb:{tmdb_id}", headers={"X-Api-Key": RADARR_KEY})
        with urllib.request.urlopen(req, timeout=10) as resp:
            lookup = json.load(resp)
        if not lookup:
            return False, "Not found in Radarr lookup"

        movie = lookup[0]
        movie["qualityProfileId"] = 6  # HD 720p/1080p
        movie["rootFolderPath"] = "/data/media/movies"
        movie["monitored"] = True
        movie["addOptions"] = {"searchForMovie": True}
        data = json.dumps(movie).encode("utf-8")
        post_req = urllib.request.Request(
            f"{RADARR_URL}/api/v3/movie",
            data=data,
            headers={"X-Api-Key": RADARR_KEY, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(post_req, timeout=10) as resp:
            res = json.load(resp)
        logger.info(f"[Radarr] Successfully added and commanded search for: {movie.get('title')}")
        return True, "Added to Radarr and searching indexers"
    except Exception as e:
        logger.error(f"[Radarr] Error adding movie: {e}")
        return False, str(e)


def add_to_radarr_by_name(title):
    """Lookup movie in Radarr by title and command search."""
    try:
        req = urllib.request.Request(
            f"{RADARR_URL}/api/v3/movie/lookup?term={urllib.parse.quote(title)}",
            headers={"X-Api-Key": RADARR_KEY}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            lookup = json.load(resp)
        if not lookup:
            return False, "Not found in Radarr lookup"
        movie = lookup[0]
        return add_to_radarr(movie["tmdbId"], movie["title"], movie.get("year"))
    except Exception as e:
        logger.error(f"[Radarr] Error in lookup by name: {e}")
        return False, str(e)


def add_to_sonarr(query, tvdb_id=None):
    """Adds a TV series to Sonarr and triggers automated episode search."""
    try:
        term = f"tvdb:{tvdb_id}" if tvdb_id else query
        req = urllib.request.Request(
            f"{SONARR_URL}/api/v3/series/lookup?term={urllib.parse.quote(str(term))}",
            headers={"X-Api-Key": SONARR_KEY}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            lookup = json.load(resp)
        if not lookup:
            return False, "Not found in Sonarr lookup"

        series = lookup[0]
        # Check existing
        req_all = urllib.request.Request(f"{SONARR_URL}/api/v3/series", headers={"X-Api-Key": SONARR_KEY})
        with urllib.request.urlopen(req_all, timeout=10) as resp:
            all_series = json.load(resp)
        for s in all_series:
            if s.get("tvdbId") == series.get("tvdbId"):
                cmd_data = json.dumps({"name": "SeriesSearch", "seriesId": s["id"]}).encode("utf-8")
                cmd_req = urllib.request.Request(
                    f"{SONARR_URL}/api/v3/command",
                    data=cmd_data,
                    headers={"X-Api-Key": SONARR_KEY, "Content-Type": "application/json"}
                )
                urllib.request.urlopen(cmd_req, timeout=10)
                logger.info(f"[Sonarr] Triggered search for already tracked series: {s.get('title')}")
                return True, "Triggered search in Sonarr"

        series["qualityProfileId"] = 6
        series["rootFolderPath"] = "/data/media/tv"
        series["monitored"] = True
        series["addOptions"] = {"searchForMissingEpisodes": True}
        data = json.dumps(series).encode("utf-8")
        post_req = urllib.request.Request(
            f"{SONARR_URL}/api/v3/series",
            data=data,
            headers={"X-Api-Key": SONARR_KEY, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(post_req, timeout=10) as resp:
            res = json.load(resp)
        logger.info(f"[Sonarr] Added and commanded search for: {series.get('title')}")
        return True, "Added to Sonarr and searching indexers"
    except Exception as e:
        logger.error(f"[Sonarr] Error adding series: {e}")
        return False, str(e)


def download_file(url, dest_path):
    """Downloads a video file directly or via yt-dlp if it is an m3u8/stream/YouTube link."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(".temp.mp4")

    logger.info(f"Downloading to: {dest_path.name}")
    is_stream_or_yt = (
        ".m3u8" in url
        or "youtube.com" in url
        or "youtu.be" in url
        or "uqload" in url
        or "hyperwatching" in url
        or "dailymotion" in url
    )

    if is_stream_or_yt:
        cmd = [
            "/home/dell/.local/bin/yt-dlp",
            "--no-warning",
            "-q",
            "--progress",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", str(temp_path),
            url,
        ]
        res = subprocess.run(cmd)
        if res.returncode == 0 and temp_path.exists() and temp_path.stat().st_size > 10 * 1024 * 1024:
            temp_path.rename(dest_path)
            return True
    else:
        # Direct HTTP stream download
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(temp_path, "wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        if temp_path.exists() and temp_path.stat().st_size > 10 * 1024 * 1024:
            temp_path.rename(dest_path)
            return True

    if temp_path.exists():
        temp_path.unlink()
    return False


def run_antigravity_agent(prompt_text):
    """Invokes Antigravity Headless CLI (agy) for deep autonomous search and download."""
    logger.info(f"Invoking Antigravity Autonomous Agent: {prompt_text}")
    cmd = [
        "/home/dell/.local/bin/agy",
        "--prompt",
        prompt_text,
        "--dangerously-skip-permissions",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    logger.info(f"Antigravity Agent finished with exit code {res.returncode}")
    return res.returncode == 0


def process_media_request(job):
    """The central omni-decision engine for downloading ANY media."""
    global ACTIVE_JOB
    ACTIVE_JOB = job
    job["status"] = "PROCESSING"
    job["start_time"] = time.time()

    title = job.get("title", "").strip()
    media_type = job.get("media_type") or "movie"
    tmdb_id = job.get("tmdb_id")
    dub_pref = job.get("dub_preference", "auto")
    raw_query = job.get("query") or title

    # Auto-detect TV series from query words
    if any(w in raw_query.lower() for w in ["مسلسل", "series", "season", "حلقات", "حلقة", "انمي", "anime", "موسم"]):
        media_type = "tv"
        job["media_type"] = "tv"

    logger.info(f"==================================================")
    logger.info(f"Job: '{title or raw_query}' | Type: {media_type} | TMDb: {tmdb_id} | Dub: {dub_pref}")
    logger.info(f"==================================================")

    # Direct URL Download
    if raw_query.startswith("http://") or raw_query.startswith("https://"):
        dest = MOVIES_DIR / f"Web_Download_{int(time.time())}" / f"media_{int(time.time())}.mp4"
        if download_file(raw_query, dest):
            job["status"] = "COMPLETED"
            job["source"] = "Direct URL Download"
            job["output_file"] = str(dest)
            refresh_jellyfin()
            refresh_jellyseerr()
            return True

    # Step 1: Metadata Enrichment (if TMDb ID exists)
    meta = {}
    if tmdb_id:
        meta = fetch_jellyseerr_metadata(media_type, tmdb_id)
        title_en = meta.get("title_en") or title
        title_ar = meta.get("title_ar") or title_en
        year = meta.get("year", "")
        genres = meta.get("genres", [])
        orig_lang = meta.get("original_language", "")
    else:
        title_en = raw_query
        title_ar = raw_query
        year = ""
        genres = []
        orig_lang = "ar" if is_arabic_text(raw_query) else "en"

    is_animation = any(g.lower() in ("animation", "family", "kids") for g in genres)
    is_arabic_content = orig_lang == "ar" or is_arabic_text(title_ar) or is_arabic_text(raw_query)

    job["enriched_meta"] = {
        "title_en": title_en,
        "title_ar": title_ar,
        "year": year,
        "genres": genres,
        "is_arabic": is_arabic_content,
        "is_animation": is_animation,
    }

    # Step 2: Check if already present on disk
    if media_type == "movie" and title_en:
        folder_name = f"{title_en} ({year})" if year else title_en
        target_dir = MOVIES_DIR / folder_name
        existing_files = list(target_dir.glob("*.mp4")) + list(target_dir.glob("*.mkv"))
        if existing_files and existing_files[0].stat().st_size > 50 * 1024 * 1024:
            logger.info(f"Media already exists on disk: {existing_files[0]}")
            job["status"] = "COMPLETED"
            job["message"] = f"Already present: {existing_files[0].name}"
            refresh_jellyfin()
            refresh_jellyseerr()
            return True

    # Step 3: Handle Disney / Animation Egyptian Dub Requests
    if dub_pref == "egyptian" or (is_animation and dub_pref != "original"):
        archive_dub_url = find_archive_egyptian_movie(title_en)
        if archive_dub_url and media_type == "movie":
            logger.info(f"[Egyptian Dub Archive] Found: {archive_dub_url}")
            folder_name = f"{title_en} ({year})" if year else title_en
            dest_file = MOVIES_DIR / folder_name / f"{folder_name}.mp4"
            if download_file(archive_dub_url, dest_file):
                logger.info(f"[SUCCESS] Downloaded Egyptian Dub: {title_en}")
                job["status"] = "COMPLETED"
                job["source"] = "Archive.org (Egyptian Dub Suite)"
                job["output_file"] = str(dest_file)
                refresh_jellyfin()
                refresh_jellyseerr()
                return True

    # Step 4: Handle Arabic Movies / Plays (Egyptian / Arabic Content)
    if is_arabic_content and dub_pref != "english" and media_type == "movie":
        search_terms = [title_ar, title_en, raw_query]
        clean_search = next((t for t in search_terms if t and is_arabic_text(t)), title_en)

        # 4A: Check Archive.org for full Arabic movies or plays
        archive_ar_url = search_archive_arabic_media(clean_search)
        if archive_ar_url:
            folder_name = f"{title_en} ({year})" if year else title_en
            dest_file = MOVIES_DIR / folder_name / f"{folder_name}.mp4"
            if download_file(archive_ar_url, dest_file):
                logger.info(f"[SUCCESS] Downloaded Arabic media from Archive.org: {dest_file.name}")
                job["status"] = "COMPLETED"
                job["source"] = "Archive.org (Arabic Cinema Archive)"
                job["output_file"] = str(dest_file)
                refresh_jellyfin()
                refresh_jellyseerr()
                return True

        # 4B: Check YouTube via yt-dlp for full official HD movies
        yt_movie_url = search_youtube_full_movie(clean_search)
        if yt_movie_url:
            folder_name = f"{title_en} ({year})" if year else title_en
            dest_file = MOVIES_DIR / folder_name / f"{folder_name}.mp4"
            if download_file(yt_movie_url, dest_file):
                logger.info(f"[SUCCESS] Downloaded full Arabic movie from YouTube: {dest_file.name}")
                job["status"] = "COMPLETED"
                job["source"] = "YouTube (Official Full Movie)"
                job["output_file"] = str(dest_file)
                refresh_jellyfin()
                refresh_jellyseerr()
                return True

    # Step 5: International / English Movies & Series via Radarr & Sonarr
    if not is_arabic_content or dub_pref in ("auto", "english", "arabic_subs") or media_type == "tv":
        if media_type == "movie":
            logger.info(f"[Radarr] Routing movie {title_en} to Radarr auto-downloader...")
            ok, msg = add_to_radarr(tmdb_id, title_en, year) if tmdb_id else add_to_radarr_by_name(title_en)
            if ok:
                job["status"] = "FORWARDED_TO_ARR"
                job["source"] = "Radarr + Prowlarr Indexers"
                job["message"] = f"Radarr searching for {title_en}. Subtitles will sync automatically."
                run_subtitle_sync()
                return True

        elif media_type == "tv":
            clean_tv = re.sub(r"^(مسلسل|series|season|حلقات|حلقة)\s+", "", title_en, flags=re.IGNORECASE).strip()
            logger.info(f"[Sonarr] Routing series '{clean_tv}' to Sonarr auto-downloader...")
            ok, msg = add_to_sonarr(clean_tv)
            if ok:
                job["status"] = "FORWARDED_TO_ARR"
                job["source"] = "Sonarr + Prowlarr Indexers"
                job["message"] = f"Sonarr searching for {clean_tv}. Subtitles will sync automatically."
                run_subtitle_sync()
                return True

    # Step 6: Fallback to Autonomous AI Agent (agy) for Rare or Custom Requests
    logger.info(f"[AI Agent Fallback] Invoking Antigravity autonomous scraper for '{title_ar}'...")
    agent_prompt = (
        f"Download the media item '{title_en}' (Arabic title: '{title_ar}', Year: '{year}'). "
        f"Preference: {dub_pref}. Search the web (Arabic streaming/download sites like Akwam, MyCima, Arabseed, Archive, or torrents). "
        f"Save the downloaded video into /media/dell/Data1/netfelix_data/media/{'movies' if media_type == 'movie' else 'tv'}/ "
        f"using standard naming and make sure subtitles or Arabic audio are included."
    )
    try:
        success = run_antigravity_agent(agent_prompt)
        if success:
            job["status"] = "COMPLETED"
            job["source"] = "Antigravity Autonomous Agent"
            refresh_jellyfin()
            refresh_jellyseerr()
            run_subtitle_sync()
            return True
    except Exception as e:
        logger.error(f"Antigravity Autonomous Agent failed: {e}")

    job["status"] = "FAILED"
    job["error"] = "Could not resolve a working download source automatically."
    return False


def worker_thread():
    """Background queue worker."""
    global ACTIVE_JOB
    load_history()
    while True:
        try:
            job = JOB_QUEUE.get()
            try:
                process_media_request(job)
            except Exception as e:
                logger.error(f"Error processing job: {e}", exc_info=True)
                job["status"] = "FAILED"
                job["error"] = str(e)
            finally:
                job["end_time"] = time.time()
                JOB_HISTORY.append(job)
                save_history()
                ACTIVE_JOB = None
                JOB_QUEUE.task_done()
        except Exception as e:
            logger.error(f"Queue worker exception: {e}")
            time.sleep(1)


# Embedded Dark-Themed Web Studio HTML
WEB_STUDIO_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NetFelix AI Universal Downloader | محرك التحميل الذكي</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0f1015;
      --card: #181922;
      --card-border: #282a36;
      --accent: #e50914;
      --accent-hover: #f40612;
      --text: #ffffff;
      --text-muted: #9aa0a6;
      --gold: #f59e0b;
      --green: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Cairo', -apple-system, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 24px 16px;
    }
    .container {
      width: 100%;
      max-width: 900px;
    }
    header {
      text-align: center;
      margin-bottom: 28px;
    }
    .badge {
      display: inline-block;
      background: rgba(229, 9, 20, 0.15);
      color: #ff4d4d;
      border: 1px solid rgba(229, 9, 20, 0.3);
      padding: 4px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 12px;
    }
    h1 {
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.5px;
      margin-bottom: 8px;
      background: linear-gradient(135deg, #fff 40%, #ff6b6b 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    p.subtitle {
      color: var(--text-muted);
      font-size: 15px;
    }
    .search-card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      margin-bottom: 24px;
    }
    .input-group {
      display: flex;
      gap: 10px;
      margin-bottom: 16px;
    }
    input[type="text"] {
      flex: 1;
      background: #0b0c10;
      border: 1px solid #333644;
      border-radius: 10px;
      padding: 14px 18px;
      color: #fff;
      font-size: 16px;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s;
    }
    input[type="text"]:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(229, 9, 20, 0.2);
    }
    button.btn-primary {
      background: linear-gradient(135deg, var(--accent) 0%, #b80710 100%);
      color: white;
      border: none;
      border-radius: 10px;
      padding: 14px 28px;
      font-size: 16px;
      font-weight: 700;
      font-family: inherit;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: transform 0.15s, opacity 0.2s;
      white-space: nowrap;
    }
    button.btn-primary:hover {
      opacity: 0.95;
      transform: translateY(-1px);
    }
    button.btn-primary:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .options-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .option-btn {
      background: #20222e;
      border: 1px solid #333644;
      color: var(--text-muted);
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 13px;
      cursor: pointer;
      text-align: center;
      transition: all 0.2s;
      font-family: inherit;
    }
    .option-btn.active {
      background: rgba(229, 9, 20, 0.2);
      border-color: var(--accent);
      color: #fff;
      font-weight: 600;
    }
    .quick-examples {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      font-size: 13px;
      color: var(--text-muted);
    }
    .tag {
      background: #20222e;
      padding: 4px 10px;
      border-radius: 6px;
      cursor: pointer;
      color: #cbd5e1;
      transition: background 0.2s;
    }
    .tag:hover {
      background: #2f3244;
      color: #fff;
    }
    .status-banner {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px 22px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      background: var(--green);
      border-radius: 50%;
      display: inline-block;
      margin-left: 8px;
      box-shadow: 0 0 10px var(--green);
    }
    .history-card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
    }
    .history-card h2 {
      font-size: 18px;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .history-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 14px;
      background: #12131a;
      border: 1px solid #252733;
      border-radius: 8px;
      margin-bottom: 8px;
      font-size: 14px;
    }
    .history-meta {
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .history-title {
      font-weight: 600;
      color: #fff;
    }
    .history-source {
      font-size: 12px;
      color: var(--text-muted);
    }
    .badge-status {
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-completed { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .badge-processing { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
    .badge-forwarded { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
    .btn-small {
      background: #252838;
      border: 1px solid #373b52;
      color: #fff;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      font-family: inherit;
      text-decoration: none;
    }
    .btn-small:hover { background: #32364c; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="badge">🤖 محرك NetFelix الذكي الموحد</div>
      <h1>حَمّل أي حاجة تخطر ببالك</h1>
      <p class="subtitle">أفلام ومسرحيات مصرية، كلاسيكيات ديزني بالمصري، مسلسلات وأفلام أجنبية بأعلى جودة مع ترجمة عربية تلقائية</p>
    </header>

    <div class="search-card">
      <div class="input-group">
        <input type="text" id="queryInput" placeholder="اكتب اسم أي فيلم، مسلسل، مسرحية، أو الصق رابطاً مباشراً..." autofocus>
        <button class="btn-primary" id="downloadBtn" onclick="submitRequest()">
          <span>🚀 ابدأ التحميل</span>
        </button>
      </div>

      <div class="options-grid">
        <div class="option-btn active" data-mode="auto" onclick="selectMode('auto', this)">⚡ تلقائي ذكي (Smart Auto)</div>
        <div class="option-btn" data-mode="egyptian" onclick="selectMode('egyptian', this)">🇪🇬 دبلجة مصرية أصلية</div>
        <div class="option-btn" data-mode="arabic_subs" onclick="selectMode('arabic_subs', this)">🔤 أجنبي + ترجمة عربي</div>
        <div class="option-btn" data-mode="arabic" onclick="selectMode('arabic', this)">🎭 مصري / عربي أصلي</div>
      </div>

      <div class="quick-examples">
        <span>أمثلة سريعة:</span>
        <span class="tag" onclick="setQuery('فيلم عسل اسود')">فيلم عسل أسود</span>
        <span class="tag" onclick="setQuery('مسرحية العيال كبرت')">مسرحية العيال كبرت</span>
        <span class="tag" onclick="setQuery('الأسد الملك')">الأسد الملك (بالمصري)</span>
        <span class="tag" onclick="setQuery('Inception')">Inception + ترجمة</span>
        <span class="tag" onclick="setQuery('Breaking Bad')">Breaking Bad</span>
      </div>
    </div>

    <div class="status-banner">
      <div>
        <span class="status-dot"></span>
        <span id="activeStatus">المحرك جاهز لاستقبال الطلبات على المنفذ 8092</span>
      </div>
      <div>
        <button class="btn-small" onclick="refreshJellyfin()">🔄 تحديث مكتبة Jellyfin</button>
      </div>
    </div>

    <div class="history-card">
      <h2>
        <span>📋 سجل التحميلات الأخيرة</span>
        <button class="btn-small" onclick="loadStatus()">تحديث ⟳</button>
      </h2>
      <div id="historyList">
        <div style="color: var(--text-muted); text-align: center; padding: 20px;">جاري تحميل السجل...</div>
      </div>
    </div>
  </div>

  <script>
    let currentMode = 'auto';

    function selectMode(mode, el) {
      currentMode = mode;
      document.querySelectorAll('.option-btn').forEach(b => b.classList.remove('active'));
      el.classList.add('active');
    }

    function setQuery(text) {
      document.getElementById('queryInput').value = text;
      document.getElementById('queryInput').focus();
    }

    async function submitRequest() {
      const input = document.getElementById('queryInput');
      const btn = document.getElementById('downloadBtn');
      const val = input.value.trim();
      if (!val) return;

      btn.disabled = true;
      btn.innerHTML = '<span>جاري الإرسال...</span>';

      try {
        const res = await fetch('/api/request', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: val,
            query: val,
            mediaType: 'movie',
            dub: currentMode
          })
        });
        const data = await res.json();
        alert(data.message || 'تم استلام طلبك بنجاح! جاري معالجته في الخلفية.');
        input.value = '';
        loadStatus();
      } catch (err) {
        alert('حدث خطأ أثناء إرسال الطلب: ' + err);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>🚀 ابدأ التحميل</span>';
      }
    }

    async function refreshJellyfin() {
      try {
        await fetch('/api/refresh', { method: 'POST' });
        alert('تم إرسال أمر فحص وتحديث مكتبة Jellyfin بنجاح!');
      } catch (err) {
        alert('خطأ أثناء التحديث: ' + err);
      }
    }

    async function loadStatus() {
      try {
        const [qRes, hRes] = await Promise.all([
          fetch('/api/queue').then(r => r.json()),
          fetch('/api/history').then(r => r.json())
        ]);

        const statusEl = document.getElementById('activeStatus');
        if (qRes.active_job) {
          statusEl.innerText = `جاري الآن تحميل: ${qRes.active_job.title} (${qRes.active_job.source || 'محرك الذكاء الاصطناعي'})`;
        } else {
          statusEl.innerText = `المحرك جاهز (0 قيد الانتظار) - متصل بـ Jellyfin و Jellyseerr`;
        }

        const histEl = document.getElementById('historyList');
        const history = (hRes.history || []).reverse();
        if (history.length === 0) {
          histEl.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px;">لا توجد عمليات سابقة بعد.</div>';
          return;
        }

        histEl.innerHTML = history.map(item => {
          let badgeClass = 'badge-completed';
          let statusText = 'مكتمل';
          if (item.status === 'PROCESSING') {
            badgeClass = 'badge-processing';
            statusText = 'جاري التحميل';
          } else if (item.status === 'FORWARDED_TO_ARR') {
            badgeClass = 'badge-forwarded';
            statusText = 'مرسل لـ Radarr/Sonarr';
          }
          return `
            <div class="history-item">
              <div class="history-meta">
                <div class="history-title">${item.title || item.query || 'محتوى غير مسمى'}</div>
                <div class="history-source">${item.source || 'AI Downloader'} ${item.message ? '• ' + item.message : ''}</div>
              </div>
              <span class="badge-status ${badgeClass}">${statusText}</span>
            </div>
          `;
        }).join('');
      } catch (e) {
        console.error('Status load error:', e);
      }
    }

    document.getElementById('queryInput').addEventListener('keypress', function(e) {
      if (e.key === 'Enter') submitRequest();
    });

    setInterval(loadStatus, 4000);
    loadStatus();
  </script>
</body>
</html>
"""


class AIRequestHandler(BaseHTTPRequestHandler):
    """HTTP API, Embedded Web Studio, and Webhook Handler."""

    def _send_json(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html_content):
        data = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/index.html", "/studio"):
            self._send_html(WEB_STUDIO_HTML)
        elif path == "/health":
            self._send_json(200, {"status": "ok", "service": "NetFelix AI Universal Downloader"})
        elif path == "/api/queue":
            self._send_json(200, {
                "active_job": ACTIVE_JOB,
                "pending_count": JOB_QUEUE.qsize(),
            })
        elif path == "/api/history":
            self._send_json(200, {"history": JOB_HISTORY[-25:]})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(length) if length > 0 else b"{}"

        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            body = {}

        if path == "/webhook/jellyseerr":
            event = body.get("event") or body.get("notification_type") or "UNKNOWN"
            subject = body.get("subject", "")
            media = body.get("media") or {}
            media_type = media.get("media_type") or ("tv" if "tv" in event.lower() else "movie")
            tmdb_id = media.get("tmdbId") or media.get("tmdb_id")

            logger.info(f"[Webhook Received] Event: '{event}' | Subject: '{subject}' | Type: {media_type} | TMDb: {tmdb_id}")

            if tmdb_id and event not in ("TEST_NOTIFICATION",):
                job = {
                    "id": f"job_{int(time.time()*1000)}",
                    "source": "Jellyseerr Webhook",
                    "event": event,
                    "title": subject,
                    "media_type": media_type,
                    "tmdb_id": int(tmdb_id),
                    "dub_preference": "auto",
                    "status": "QUEUED",
                    "created_at": time.time(),
                }
                JOB_QUEUE.put(job)
                self._send_json(200, {"status": "queued", "job_id": job["id"]})
            else:
                self._send_json(200, {"status": "acknowledged", "note": "Test notification or missing TMDb ID"})

        elif path in ("/api/request", "/api/download"):
            tmdb_id = body.get("tmdbId") or body.get("tmdb_id")
            media_type = body.get("mediaType") or body.get("media_type", "movie")
            title = body.get("title") or body.get("query", "").strip()
            dub = body.get("dub", "auto")
            raw_query = body.get("query", "").strip()

            if not title and not raw_query and not tmdb_id:
                self._send_json(400, {"error": "Missing title, query, or tmdbId"})
                return

            job = {
                "id": f"job_{int(time.time()*1000)}",
                "source": "Universal AI Downloader",
                "title": title or raw_query,
                "query": raw_query or title,
                "media_type": media_type,
                "tmdb_id": int(tmdb_id) if tmdb_id else None,
                "dub_preference": dub,
                "status": "QUEUED",
                "created_at": time.time(),
            }
            JOB_QUEUE.put(job)
            logger.info(f"[Omni Download Request] Queued: {job['title']} | Type: {media_type} | Dub: {dub}")
            self._send_json(200, {
                "status": "queued",
                "job_id": job["id"],
                "message": f"تم استلام طلب تحميل '{job['title']}' بنجاح! جاري المعالجة."
            })

        elif path == "/api/refresh":
            refresh_jellyfin()
            refresh_jellyseerr()
            run_subtitle_sync()
            self._send_json(200, {"status": "ok", "message": "Triggered Jellyfin & Jellyseerr library scans."})

        elif path == "/api/prompt":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_json(400, {"error": "Missing prompt"})
                return

            def run_async():
                run_antigravity_agent(prompt)
                refresh_jellyfin()
                refresh_jellyseerr()

            t = threading.Thread(target=run_async)
            t.daemon = True
            t.start()
            self._send_json(200, {"status": "started", "prompt": prompt})

        else:
            self._send_json(404, {"error": "Endpoint not found"})


def main():
    logger.info("=" * 70)
    logger.info("Starting NetFelix Universal AI Downloader & Media Agent")
    logger.info("Port: 8092 | Web Studio: http://0.0.0.0:8092/ | API: /api/request")
    logger.info("=" * 70)

    # Start Queue Worker Thread
    t = threading.Thread(target=worker_thread, daemon=True)
    t.start()

    # Start HTTP Server
    server = HTTPServer(("0.0.0.0", 8092), AIRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Universal AI Downloader...")
        server.server_close()


if __name__ == "__main__":
    main()
