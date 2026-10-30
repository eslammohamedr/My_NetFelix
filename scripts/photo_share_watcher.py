#!/usr/bin/env python3
"""
NetFelix Photo Share Watcher & Telegram Notification Bot
Monitors Caddy access logs for visits to shared Immich photo albums (https://eslam-photos.duckdns.org/share/*).
Identifies:
- Visitor IP address
- Geolocation, City, Country, ISP (with national flag emoji)
- Device Type (iPhone, Android, Windows, Mac, Linux) & Browser
- Link preview crawlers (Telegram, WhatsApp, Facebook bots)
- Album / Folder name from Immich database & API
- Instant Telegram notification with direct link & map buttons
- Anti-spam debounce / cooldown per visitor session
"""

import os
from local_env import load_local_env
load_local_env()
import os
import sys
import time
import json
import html
import logging
import re
import datetime
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import ipaddress
from pathlib import Path

# Paths
BASE_DIR = Path("/home/dell/Desktop/My_NetFelix")
ENV_FILE = BASE_DIR / ".env"
CONFIG_DIR = BASE_DIR / "config"
CADDY_LOG_FILE = CONFIG_DIR / "caddy" / "data" / "photos_access.log"
STATE_FILE = CONFIG_DIR / "photo_share_watcher_state.json"

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PhotoWatcher] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PhotoWatcher")

# Cooldown between alerts for same visitor + share link (15 minutes)
COOLDOWN_SECONDS = 900
IMMICH_URL = "http://localhost:2283/api"
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY", "")

# Caches
GEO_CACHE = {}
SHARE_CACHE = {}
VISITOR_SESSIONS = {}


def load_env():
    """Loads environment variables from .env."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k not in os.environ:
                        os.environ[k] = v


load_env()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "850274229").strip()
SERVER_PUBLIC_IP = "102.188.219.75"


def load_state():
    """Loads cached geolocation and visitor sessions from state file."""
    global GEO_CACHE, VISITOR_SESSIONS
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                GEO_CACHE = data.get("geo_cache", {})
                # Restore sessions, pruning expired ones
                sessions = data.get("sessions", {})
                now = time.time()
                VISITOR_SESSIONS = {
                    k: v for k, v in sessions.items()
                    if now - v.get("last_alert", 0) < 86400  # keep for 24h
                }
                logger.info(f"Loaded state: {len(GEO_CACHE)} GeoIP entries, {len(VISITOR_SESSIONS)} sessions.")
        except Exception as e:
            logger.warning(f"Error loading state: {e}")


def save_state():
    """Persists GeoIP cache and visitor sessions."""
    try:
        now = time.time()
        pruned_sessions = {
            k: v for k, v in VISITOR_SESSIONS.items()
            if now - v.get("last_alert", 0) < 86400
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "geo_cache": GEO_CACHE,
                "sessions": pruned_sessions,
                "updated_at": datetime.datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Error saving state: {e}")


def country_code_to_flag(code):
    """Converts 2-letter ISO country code to Unicode Flag emoji."""
    if not code or len(code) != 2:
        return "🌍"
    try:
        return "".join(chr(127397 + ord(c.upper())) for c in code)
    except Exception:
        return "🌍"


def is_private_ip(ip_str):
    """Checks if an IP string is private, loopback, or link-local."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def extract_client_ip(req_dict):
    """Extracts actual visitor IP from Caddy request object."""
    headers = req_dict.get("headers", {})
    xff = headers.get("X-Forwarded-For")
    if xff:
        raw_xff = xff[0] if isinstance(xff, list) and xff else str(xff)
        if raw_xff:
            parts = [p.strip() for p in raw_xff.split(",") if p.strip()]
            for part in parts:
                if not is_private_ip(part):
                    return part
            if parts:
                return parts[0]

    client_ip = req_dict.get("client_ip")
    if client_ip and client_ip != "127.0.0.1" and not is_private_ip(client_ip):
        return client_ip

    remote_ip = req_dict.get("remote_ip", "")
    if remote_ip and not is_private_ip(remote_ip):
        return remote_ip

    return client_ip or remote_ip or "Unknown"


def get_geoip_info(ip):
    """Resolves IP to country, city, ISP and coordinates."""
    if not ip or ip == "Unknown":
        return {
            "country": "غير معروف",
            "city": "غير معروف",
            "region": "",
            "isp": "غير محدد",
            "flag": "🌐",
            "lat": None,
            "lon": None
        }

    if is_private_ip(ip):
        return {
            "country": "الشبكة الداخلية (LAN)",
            "city": "منزل / راوتر",
            "region": "Local",
            "isp": "NetFelix Host",
            "flag": "🏠",
            "lat": None,
            "lon": None
        }

    if ip == SERVER_PUBLIC_IP:
        return {
            "country": "مصر (شبكة المنزل)",
            "country_code": "EG",
            "city": "الإسكندرية (راوتر المنزل)",
            "region": "Home Wi-Fi",
            "isp": "TE Data (شبكة المنزل)",
            "flag": "🏠",
            "lat": None,
            "lon": None
        }

    if ip in GEO_CACHE:
        return GEO_CACHE[ip]

    url = f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,regionName,city,lat,lon,isp,org,as,query"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NetFelix-PhotoWatcher/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                cc = data.get("countryCode", "")
                flag = country_code_to_flag(cc)
                res = {
                    "country": data.get("country", "Unknown"),
                    "country_code": cc,
                    "city": data.get("city", "Unknown"),
                    "region": data.get("regionName", ""),
                    "isp": data.get("isp", data.get("org", "Unknown")),
                    "flag": flag,
                    "lat": data.get("lat"),
                    "lon": data.get("lon")
                }
                GEO_CACHE[ip] = res
                save_state()
                return res
    except Exception as e:
        logger.warning(f"GeoIP resolution failed for {ip}: {e}")

    fallback = {
        "country": "خارجي (Unknown)",
        "country_code": "",
        "city": "غير محدد",
        "region": "",
        "isp": "غير محدد",
        "flag": "🌍",
        "lat": None,
        "lon": None
    }
    GEO_CACHE[ip] = fallback
    return fallback


SAMSUNG_MODELS = {
    # Galaxy S25 Series
    "SM-S938": "Samsung Galaxy S25 Ultra",
    "SM-S936": "Samsung Galaxy S25+",
    "SM-S931": "Samsung Galaxy S25",
    # Galaxy S24 Series
    "SM-S928": "Samsung Galaxy S24 Ultra",
    "SM-S926": "Samsung Galaxy S24+",
    "SM-S921": "Samsung Galaxy S24",
    # Galaxy S23 Series
    "SM-S918": "Samsung Galaxy S23 Ultra",
    "SM-S916": "Samsung Galaxy S23+",
    "SM-S911": "Samsung Galaxy S23",
    # Galaxy S22 Series
    "SM-S908": "Samsung Galaxy S22 Ultra",
    "SM-S906": "Samsung Galaxy S22+",
    "SM-S901": "Samsung Galaxy S22",
    # Galaxy S21 Series
    "SM-G998": "Samsung Galaxy S21 Ultra",
    "SM-G996": "Samsung Galaxy S21+",
    "SM-G991": "Samsung Galaxy S21",
    # Galaxy Note Series
    "SM-N986": "Samsung Galaxy Note 20 Ultra",
    "SM-N981": "Samsung Galaxy Note 20",
    # Galaxy Foldables
    "SM-F956": "Samsung Galaxy Z Fold 6",
    "SM-F741": "Samsung Galaxy Z Flip 6",
    "SM-F946": "Samsung Galaxy Z Fold 5",
    "SM-F731": "Samsung Galaxy Z Flip 5",
    "SM-F936": "Samsung Galaxy Z Fold 4",
    "SM-F721": "Samsung Galaxy Z Flip 4",
    # Galaxy A Series
    "SM-A556": "Samsung Galaxy A55",
    "SM-A546": "Samsung Galaxy A54",
    "SM-A536": "Samsung Galaxy A53",
    "SM-A528": "Samsung Galaxy A52s",
    "SM-A356": "Samsung Galaxy A35",
    "SM-A346": "Samsung Galaxy A34",
}


def resolve_device_model(raw_model):
    """Maps device model strings to friendly names."""
    if not raw_model:
        return ""
    clean = raw_model.strip()
    upper = clean.upper()
    for prefix, name in SAMSUNG_MODELS.items():
        if upper.startswith(prefix):
            return f"{name} ({clean})"
    if upper.startswith("SM-"):
        return f"Samsung ({clean})"
    return clean


def parse_user_agent(ua_string):
    """Parses User-Agent into readable device, browser, and bot classification."""
    if not ua_string:
        return {
            "device": "جهاز غير معروف",
            "browser": "متصفح غير معروف",
            "is_bot": False,
            "bot_name": None
        }

    ua = ua_string

    # 1. Check known bots and link previewers
    bot_match = None
    if "facebookexternalhit" in ua:
        bot_match = "Facebook Link Preview Bot"
    elif "TelegramBot" in ua:
        bot_match = "Telegram Preview Bot"
    elif "WhatsApp" in ua and ("compatible" in ua or "bot" in ua.lower()):
        bot_match = "WhatsApp Preview Bot"
    elif "Twitterbot" in ua:
        bot_match = "Twitter/X Preview Bot"
    elif "LinkedInBot" in ua:
        bot_match = "LinkedIn Preview Bot"
    elif "Googlebot" in ua:
        bot_match = "Googlebot"
    elif "bingbot" in ua:
        bot_match = "Bingbot"
    elif "curl" in ua:
        bot_match = "cURL Script / CLI"

    if bot_match:
        return {
            "device": "🤖 بوت معاينة روابط",
            "browser": bot_match,
            "is_bot": True,
            "bot_name": bot_match
        }

    # 2. In-app browsers
    app_tag = ""
    if "WhatsApp" in ua:
        app_tag = " (داخل تطبيق WhatsApp)"
    elif "Instagram" in ua:
        app_tag = " (داخل تطبيق Instagram)"
    elif "FBAN" in ua or "FBIOS" in ua:
        app_tag = " (داخل تطبيق Facebook)"
    elif "Snapchat" in ua:
        app_tag = " (داخل تطبيق Snapchat)"
    elif "Telegram" in ua:
        app_tag = " (داخل تطبيق Telegram)"

    # 3. Detect Device / OS
    device = "جهاز غير معروف"
    if "iPhone" in ua:
        m = re.search(r"iPhone OS (\d+[_\d]*)", ua)
        ver = f" iOS {m.group(1).replace('_', '.')}" if m else ""
        device = f"📱 Apple iPhone{ver}"
    elif "iPad" in ua:
        m = re.search(r"CPU OS (\d+[_\d]*)", ua)
        ver = f" iPadOS {m.group(1).replace('_', '.')}" if m else ""
        device = f"📱 Apple iPad{ver}"
    elif "Android" in ua:
        m_ver = re.search(r"Android (\d+(\.\d+)?)", ua)
        and_ver = f" {m_ver.group(1)}" if m_ver else ""
        m_model = re.search(r";\s*([^;)]+)\s+Build/", ua)
        raw_model = m_model.group(1) if m_model else ""
        friendly_model = resolve_device_model(raw_model)
        if friendly_model:
            device = f"📱 {friendly_model} • Android{and_ver}"
        else:
            device = f"📱 Android{and_ver}"
    elif "Macintosh" in ua or "Mac OS X" in ua:
        device = "💻 Apple Mac (macOS)"
    elif "Windows NT 10.0" in ua:
        device = "💻 كمبيوتر (Windows 10/11)"
    elif "Windows" in ua:
        device = "💻 كمبيوتر (Windows)"
    elif "Linux" in ua:
        device = "💻 كمبيوتر (Linux)"

    # 4. Detect Browser
    browser = "متصفح الويب"
    if "SamsungBrowser" in ua:
        browser = "Samsung Internet"
    elif "Edg/" in ua or "Edge/" in ua:
        browser = "Microsoft Edge"
    elif "OPR/" in ua or "Opera" in ua:
        browser = "Opera"
    elif "Chrome" in ua and "Chromium" not in ua:
        browser = "Google Chrome"
    elif "Safari" in ua and "Chrome" not in ua:
        browser = "Apple Safari"
    elif "Firefox" in ua:
        browser = "Mozilla Firefox"
    elif "Chromium" in ua:
        browser = "Chromium"

    return {
        "device": device,
        "browser": f"{browser}{app_tag}",
        "is_bot": False,
        "bot_name": None
    }


def get_share_details(share_key):
    """Queries Immich API or DB to find title and description of the shared link."""
    now = time.time()
    if share_key in SHARE_CACHE and (now - SHARE_CACHE[share_key]["cached_at"] < 300):
        return SHARE_CACHE[share_key]["data"]

    # Refresh all shares from Immich API
    try:
        url = f"{IMMICH_URL}/shared-links"
        req = urllib.request.Request(url, headers={"x-api-key": IMMICH_API_KEY, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            items = json.loads(resp.read().decode("utf-8"))
            for item in items:
                k = item.get("key")
                slug = item.get("slug")
                album = item.get("album") or {}
                album_name = album.get("albumName")
                desc = item.get("description") or album.get("description", "")
                if not album_name:
                    if item.get("type") == "INDIVIDUAL":
                        assets = item.get("assets", [])
                        if assets:
                            album_name = f"صورة فردية ({assets[0].get('originalFileName', 'صورة')})"
                        else:
                            album_name = "مشاركة صور فردية"
                    else:
                        album_name = desc or "ألبوم صور"

                info = {
                    "id": item.get("id"),
                    "key": k,
                    "slug": slug,
                    "title": album_name,
                    "description": desc,
                    "type": item.get("type", "ALBUM"),
                    "allow_download": item.get("allowDownload", False)
                }
                if k:
                    SHARE_CACHE[k] = {"data": info, "cached_at": now}
                if slug:
                    SHARE_CACHE[slug] = {"data": info, "cached_at": now}
    except Exception as e:
        logger.warning(f"Immich API shared links fetch failed: {e}")

    if share_key in SHARE_CACHE:
        return SHARE_CACHE[share_key]["data"]

    # Database fallback
    try:
        sql = f"SELECT sl.id, sl.type, sl.description, a.\"albumName\" FROM shared_link sl LEFT JOIN album a ON sl.\"albumId\" = a.id WHERE sl.slug = '{share_key}' OR encode(sl.key, 'base64') LIKE '{share_key[:12]}%' LIMIT 1;"
        proc = subprocess.run(
            ["docker", "exec", "-i", "netfelix-immich-postgres", "psql", "-U", "postgres", "-d", "immich", "-t", "-A", "-F", "||", "-c", sql],
            capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parts = proc.stdout.strip().split("||")
            title = parts[3] if len(parts) > 3 and parts[3] else (parts[2] if len(parts) > 2 and parts[2] else "ألبوم صور")
            desc = parts[2] if len(parts) > 2 else ""
            info = {"title": title, "description": desc, "type": parts[1] if len(parts) > 1 else "ALBUM"}
            SHARE_CACHE[share_key] = {"data": info, "cached_at": now}
            return info
    except Exception as e:
        logger.warning(f"Database fallback query failed: {e}")

    # Default unknown share
    info = {"title": f"رابط مشاركة ({share_key[:10]}...)", "description": "", "type": "ALBUM"}
    SHARE_CACHE[share_key] = {"data": info, "cached_at": now}
    return info


def send_telegram_alert(text, reply_markup=None):
    """Dispatches Telegram notification to owner."""
    if not BOT_TOKEN or not ALLOWED_USER_ID:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_ALLOWED_USER_ID")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALLOWED_USER_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error(f"Failed to dispatch Telegram message: {e}")
        return False


def handle_share_visit(req_data):
    """Processes a matching GET /share/* request."""
    uri = req_data.get("uri", "")
    method = req_data.get("method", "GET")

    if method != "GET":
        return

    # Extract share key from /share/<key> or /share/<key>/...
    m = re.match(r"^/share/([A-Za-z0-9_-]+)", uri)
    if not m:
        return

    share_key = m.group(1)

    # Ignore internal test probe if called
    if share_key == "test-key-probe":
        return

    ip = extract_client_ip(req_data)
    headers = req_data.get("headers", {})
    ua_list = headers.get("User-Agent", [""])
    ua_str = ua_list[0] if isinstance(ua_list, list) and ua_list else str(ua_list)

    ua_info = parse_user_agent(ua_str)
    is_bot = ua_info.get("is_bot", False)

    # Session key for debouncing
    session_key = f"{ip}_{share_key}"
    now = time.time()
    session = VISITOR_SESSIONS.get(session_key)

    is_revisit = False
    if session:
        last_alert = session.get("last_alert", 0)
        time_since = now - last_alert
        if time_since < COOLDOWN_SECONDS:
            # Within cooldown, update hit count without sending alert
            session["hits"] = session.get("hits", 1) + 1
            session["last_seen"] = now
            return
        else:
            # Returning visitor after cooldown
            is_revisit = True

    # Record / update session
    VISITOR_SESSIONS[session_key] = {
        "ip": ip,
        "share_key": share_key,
        "first_seen": session.get("first_seen", now) if session else now,
        "last_seen": now,
        "last_alert": now,
        "hits": (session.get("hits", 0) + 1) if session else 1
    }
    save_state()

    # Resolve Geolocation & Album Info
    geo = get_geoip_info(ip)
    share_info = get_share_details(share_key)

    # Build Message
    album_title = share_info.get("title", "ألبوم صور")
    album_desc = share_info.get("description", "").strip()
    flag = geo.get("flag", "📍")
    country = geo.get("country", "غير معروف")
    city = geo.get("city", "")
    loc_str = f"{city}، {country}" if city and city != "Unknown" else country
    isp = geo.get("isp", "غير محدد")
    device = ua_info.get("device", "غير معروف")
    browser = ua_info.get("browser", "غير معروف")

    if is_bot:
        header = "🤖 <b>معاينة رابط (Crawler / Link Preview)</b>"
    elif is_revisit:
        header = "🔄 <b>تجدد زيارة: عودة لتصفح الألبوم!</b>"
    else:
        header = "📸 <b>تنبيه: تم فتح رابط ألبوم صور!</b>"

    share_url = f"https://eslam-photos.duckdns.org/share/{share_key}"
    now_str = datetime.datetime.now().strftime("%I:%M:%S %p")

    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━━━",
        f"📂 <b>الألبوم:</b> <code>{html.escape(album_title)}</code>",
    ]
    if album_desc:
        short_desc = (album_desc[:80] + "...") if len(album_desc) > 80 else album_desc
        lines.append(f"📝 <b>الوصف:</b> <i>{html.escape(short_desc)}</i>")

    lines.extend([
        "",
        "👤 <b>تفاصيل الزائر (Visitor Info):</b>",
        f"• 🌐 <b>عنوان IP:</b> <code>{ip}</code>",
        f"• {flag} <b>الموقع:</b> {html.escape(loc_str)}",
        f"• 🏢 <b>مزود الخدمة (ISP):</b> {html.escape(isp)}",
        f"• 📱 <b>نوع الجهاز:</b> {html.escape(device)}",
        f"• 🧭 <b>المتصفح:</b> {html.escape(browser)}",
        "",
        f"⏰ <b>الوقت:</b> {now_str}",
        "━━━━━━━━━━━━━━━━━━━━"
    ])

    text = "\n".join(lines)

    # Interactive inline buttons
    inline_keyboard = [
        [{"text": "📂 فتح الألبوم المعني", "url": share_url}]
    ]
    lat = geo.get("lat")
    lon = geo.get("lon")
    if lat and lon:
        maps_url = f"https://www.google.com/maps?q={lat},{lon}"
        inline_keyboard[0].append({"text": f"🗺️ خريطة الموقع", "url": maps_url})

    reply_markup = {"inline_keyboard": inline_keyboard}

    logger.info(f"Sending notification for share '{album_title}' visited by {ip} ({loc_str})")
    send_telegram_alert(text, reply_markup)


def tail_caddy_log():
    """Follows Caddy access log file continuously."""
    logger.info(f"Starting Photo Share Watcher on {CADDY_LOG_FILE}...")
    load_state()

    while not CADDY_LOG_FILE.exists():
        logger.warning(f"Log file {CADDY_LOG_FILE} not found. Waiting...")
        time.sleep(3)

    # Open file and seek to end on first startup
    f = open(CADDY_LOG_FILE, "r", encoding="utf-8", errors="ignore")
    f.seek(0, os.SEEK_END)
    current_inode = os.fstat(f.fileno()).st_ino

    while True:
        line = f.readline()
        if line:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                entry = json.loads(line_str)
                req = entry.get("request", {})
                uri = req.get("uri", "")
                if uri.startswith("/share/"):
                    handle_share_visit(req)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"Error handling log entry: {e}", exc_info=True)
        else:
            time.sleep(0.3)
            # Check for log rotation
            try:
                if CADDY_LOG_FILE.exists():
                    new_stat = os.stat(CADDY_LOG_FILE)
                    if new_stat.st_ino != current_inode or new_stat.st_size < f.tell():
                        logger.info("Log rotation detected. Reopening log file...")
                        f.close()
                        f = open(CADDY_LOG_FILE, "r", encoding="utf-8", errors="ignore")
                        current_inode = os.fstat(f.fileno()).st_ino
            except Exception as e:
                logger.warning(f"Log rotation check error: {e}")


if __name__ == "__main__":
    tail_caddy_log()
