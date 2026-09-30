#!/usr/bin/env python3
"""
NetFelix Supercharged Telegram Bot
Allows controlling the NetFelix Media ecosystem from anywhere via Telegram:
- Interactive search with Posters & Inline Buttons (/search <name>)
- Real-time TV Playback Monitor (/nowplaying)
- Active Torrent & AI Download Progress (/status)
- AI Daily Recommendations (/recommend)
- Jellyfin Library Refresh (/refresh)
- Instant Push Notifications on Download Completion with Posters
"""

import os
import sys
import time
import json
import logging
import re
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TelegramBot] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TelegramBot")

ENV_FILE = Path("/home/dell/Desktop/My_NetFelix/.env")
CONFIG_DIR = Path("/home/dell/Desktop/My_NetFelix/config")
SUBSCRIBERS_FILE = CONFIG_DIR / "telegram_subscribers.json"
NOTIFIED_FILE = CONFIG_DIR / "telegram_notified.json"


def load_env():
    """Loads environment variables from .env file."""
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
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8092").rstrip("/")
QBITTORRENT_URL = os.getenv("QBITTORRENT_URL", "http://127.0.0.1:8080").rstrip("/")
JELLYSEERR_URL = os.getenv("JELLYSEERR_URL", "http://127.0.0.1:5055").rstrip("/")
JELLYSEERR_KEY = os.getenv("JELLYSEERR_API_KEY", "MTc5MDAxMjMyMzcwOTUxY2M5MjhmLWNiNzEtNGQwYi04YjY4LTQ0YTVhZDhlZGQ3YQ==")
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "http://127.0.0.1:8096").rstrip("/")
JELLYFIN_KEY = os.getenv("JELLYFIN_API_KEY", "4d40f90a8b854cdcbb4faa23134d057b")
JELLYFIN_AUTH = f'MediaBrowser Client="Jellyseerr", DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="{JELLYFIN_KEY}"'


def get_subscribers():
    """Returns list of subscribed chat IDs."""
    subscribers = set()
    if ALLOWED_USER_ID:
        try:
            subscribers.add(int(ALLOWED_USER_ID))
        except ValueError:
            pass
    if SUBSCRIBERS_FILE.exists():
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                subscribers.update(data)
        except Exception:
            pass
    return list(subscribers)


def register_subscriber(chat_id):
    """Registers a chat ID to receive notifications."""
    try:
        subs = set(get_subscribers())
        if chat_id not in subs:
            subs.add(chat_id)
            with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(subs), f)
    except Exception as e:
        logger.warning(f"Failed to register subscriber {chat_id}: {e}")


def telegram_api(method, data=None):
    """Call Telegram Bot API."""
    if not BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        logger.error(f"Telegram API error ({method}): {e}")
        return None


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    """Send text message to Telegram chat."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api("sendMessage", payload)


def send_photo(chat_id, photo_url, caption="", reply_markup=None, parse_mode="HTML"):
    """Send photo with caption to Telegram chat."""
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    res = telegram_api("sendPhoto", payload)
    if not res or not res.get("ok"):
        # Fallback to text message
        return send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
    return res


def broadcast_notification(text, photo_url=None):
    """Broadcast notification to all subscribed users."""
    for chat_id in get_subscribers():
        try:
            if photo_url:
                send_photo(chat_id, photo_url, caption=text)
            else:
                send_message(chat_id, text)
        except Exception as e:
            logger.warning(f"Failed to notify chat {chat_id}: {e}")


def get_ai_status():
    """Fetch active queue from AI Media Agent."""
    try:
        req = urllib.request.Request(f"{AI_SERVICE_URL}/api/queue")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)}


def get_ai_history():
    """Fetch download history from AI Media Agent."""
    try:
        req = urllib.request.Request(f"{AI_SERVICE_URL}/api/history")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)}


def get_torrent_downloads():
    """Fetch active downloading torrents from qBittorrent."""
    try:
        req = urllib.request.Request(f"{QBITTORRENT_URL}/api/v2/torrents/info?filter=downloading")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except Exception as e:
        logger.debug(f"Failed to query qBittorrent: {e}")
        return []


def get_completed_torrents():
    """Fetch completed torrents from qBittorrent."""
    try:
        req = urllib.request.Request(f"{QBITTORRENT_URL}/api/v2/torrents/info?filter=completed")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except Exception as e:
        return []


def refresh_jellyfin():
    """Trigger library refresh on AI Media Agent."""
    try:
        req = urllib.request.Request(f"{AI_SERVICE_URL}/api/refresh", data=b"{}")
        with urllib.request.urlopen(req, timeout=5) as r:
            return True
    except Exception:
        return False


def request_download(query, media_type="movie", dub_mode="auto"):
    """Send download request to AI Media Agent."""
    try:
        payload = json.dumps({
            "title": query,
            "query": query,
            "mediaType": media_type,
            "dub": dub_mode
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{AI_SERVICE_URL}/api/request",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)}


def search_media(query):
    """Search for movies and TV series via Jellyseerr API."""
    try:
        encoded = urllib.parse.quote(query)
        req = urllib.request.Request(
            f"{JELLYSEERR_URL}/api/v1/search?query={encoded}",
            headers={"X-Api-Key": JELLYSEERR_KEY}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
            results = data.get("results", [])
            # Filter only movies and tv
            return [x for x in results if x.get("mediaType") in ("movie", "tv")][:2]
    except Exception as e:
        logger.error(f"Search media error: {e}")
        return []


def get_now_playing():
    """Fetch currently active playback sessions from Jellyfin."""
    try:
        req = urllib.request.Request(
            f"{JELLYFIN_URL}/Sessions",
            headers={"Authorization": JELLYFIN_AUTH}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            sessions = json.load(r)

        playing = []
        for s in sessions:
            item = s.get("NowPlayingItem")
            if not item:
                continue

            user = s.get("UserName", "مستخدم")
            client = s.get("Client", "تطبيق")
            device = s.get("DeviceName", "جهاز")
            title = item.get("Name", "غير محدد")
            series = item.get("SeriesName")
            if series:
                title = f"{series} - {title}"

            play_method = s.get("PlayMethod", "DirectPlay")
            state = s.get("PlayState", {})
            pos = state.get("PositionTicks", 0)
            runtime = item.get("RunTimeTicks", 1)
            pct = min(100.0, max(0.0, (pos / runtime) * 100)) if runtime else 0.0

            pos_min = int(pos / (10000000 * 60))
            tot_min = int(runtime / (10000000 * 60))

            playing.append({
                "user": user,
                "client": client,
                "device": device,
                "title": title,
                "play_method": play_method,
                "pct": pct,
                "pos_min": pos_min,
                "tot_min": tot_min
            })
        return playing
    except Exception as e:
        logger.error(f"Error fetching now playing: {e}")
        return []


def handle_callback_query(cq):
    """Handle inline button callback clicks."""
    cq_id = cq["id"]
    from_user = cq.get("from", {})
    user_id = str(from_user.get("id", ""))
    chat_id = cq.get("message", {}).get("chat", {}).get("id")
    data = cq.get("data", "")

    logger.info(f"Callback query from {user_id}: {data}")

    # Acknowledge callback
    telegram_api("answerCallbackQuery", {
        "callback_query_id": cq_id,
        "text": "🚀 جاري معالجة الطلب بالذكاء الاصطناعي..."
    })

    if data.startswith("req:"):
        parts = data.split(":", 3)
        if len(parts) >= 4:
            mode = parts[1]
            tmdb_id = parts[2]
            title = parts[3]

            media_type = "tv" if mode == "tv" else "movie"
            dub_mode = "egyptian" if mode == "dub" else "auto"

            type_label = "مسلسل" if media_type == "tv" else "فيلم"
            dub_label = " (🇪🇬 دبلجة مصرية)" if dub_mode == "egyptian" else ""

            send_message(
                chat_id,
                f"⚡ <b>تم تأكيد طلبك:</b> {type_label} <i>{title}</i>{dub_label}\n"
                f"📡 جاري البحث عبر فهارس التورنت والأرشيف وجلب أعلى جودة..."
            )

            res = request_download(title, media_type=media_type, dub_mode=dub_mode)
            if "error" in res:
                send_message(chat_id, f"❌ حدث خطأ: {res['error']}")
            else:
                send_message(chat_id, f"🚀 <b>{res.get('message', 'تم إرسال الطلب بنجاح!')}</b>\nسأرسل لك إشعاراً فور اكتمال التنزيل.")


def handle_message(msg):
    """Process incoming message from Telegram."""
    chat_id = msg.get("chat", {}).get("id")
    user_id = str(msg.get("from", {}).get("id", ""))
    first_name = msg.get("from", {}).get("first_name", "المستخدم")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return

    logger.info(f"Incoming message from {first_name} (User ID: {user_id}, Chat: {chat_id}): '{text}'")
    register_subscriber(chat_id)

    # Check security whitelist
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        send_message(
            chat_id,
            f"⚠️ عذراً {first_name}، هذا البوت خاص بسيرفر NetFelix المنزلي.\n"
            f"معرّف حسابك (User ID): <code>{user_id}</code>\n"
            f"يرجى السماح لك في ملف <code>.env</code> على السيرفر."
        )
        return

    if text.startswith("/start"):
        welcome = (
            f"👋 <b>أهلاً بك يا {first_name} في مساعد NetFelix الذكي!</b>\n\n"
            f"أنا نظامك الترفيهي المتكامل لتحميل وإدارة الأفلام والمسلسلات والقنوات التلفزيونية 🌍\n\n"
            f"⚡ <b>أبرز الأوامر المتاحة:</b>\n"
            f"• <code>/search &lt;الاسم&gt;</code> - بحث تفاعلي مع البوستر وأزرار التحميل المباشرة.\n"
            f"• <code>/nowplaying</code> - عرض ما يتم تشغيله على شاشات المنزل حالياً.\n"
            f"• <code>/status</code> - مراقبة سرعة التنزيلات والتورنت وطابور الانتظار.\n"
            f"• <code>/history</code> - عرض أحدث العناوين التي اكتمل تنزيلها.\n"
            f"• <code>/recommend</code> - اقتراح سهرة اليوم بالذكاء الاصطناعي.\n"
            f"• <code>/refresh</code> - تحديث وفحص مكتبة Jellyfin فوراً.\n\n"
            f"💡 <i>يمكنك أيضاً كتابة اسم أي فيلم أو مسلسل مباشرة وسأقوم بتحميله تلقائياً!</i>"
        )
        send_message(chat_id, welcome)
        return

    if text.startswith("/search"):
        query = text.replace("/search", "", 1).strip()
        if not query:
            send_message(chat_id, "💡 <b>طريقة الاستخدام:</b>\nاكتب <code>/search اسم العمل</code>\nمثال: <code>/search Gladiator</code>")
            return

        send_message(chat_id, f"🔍 <b>جاري البحث في قاعدة بيانات السينما عن:</b> <i>{query}</i>...")
        results = search_media(query)
        if not results:
            send_message(chat_id, f"❌ لم يتم العثور على نتائج مطابقة لـ: <i>{query}</i>. جرب اسماً آخر.")
            return

        for r in results:
            m_type = r.get("mediaType", "movie")
            m_id = r.get("id")
            title = r.get("title") or r.get("name", query)
            year = (r.get("releaseDate") or r.get("firstAirDate") or "")[:4]
            rating = r.get("voteAverage", 0)
            overview = r.get("overview", "")
            if len(overview) > 180:
                overview = overview[:175] + "..."

            poster_path = r.get("posterPath")
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

            type_label = "مسلسل 📺" if m_type == "tv" else "فيلم 🎬"
            caption = (
                f"🎬 <b>{title}</b> ({year})\n"
                f"📌 <b>النوع:</b> {type_label} | ⭐ <b>التقييم:</b> {rating:.1f}/10\n\n"
                f"📝 <i>{overview or 'لا يتوفر ملخص.'}</i>"
            )

            # Keyboard buttons
            buttons = [
                {"text": f"📥 تحميل كـ {type_label}", "callback_data": f"req:{m_type}:{m_id}:{title}"},
                {"text": "🇪🇬 بالدبلجة المصرية", "callback_data": f"req:dub:{m_id}:{title}"}
            ]
            keyboard = {"inline_keyboard": [buttons]}

            if poster_url:
                send_photo(chat_id, poster_url, caption=caption, reply_markup=keyboard)
            else:
                send_message(chat_id, caption, reply_markup=keyboard)
        return

    if text.startswith("/nowplaying"):
        sessions = get_now_playing()
        if not sessions:
            send_message(chat_id, "💤 <b>لا يوجد أي شخص يشاهد محتوى على السيرفر حالياً.</b>\nالشاشات في وضع الانتظار.")
            return

        lines = ["🍿 <b>المشاهدات المباشرة على سيرفر NetFelix:</b>\n"]
        for s in sessions:
            p_icon = "⚡ Direct Play" if "direct" in s["play_method"].lower() else "🔄 Transcoding"
            lines.append(
                f"👤 <b>{s['user']}</b> ({s['client']} على {s['device']})\n"
                f"🎬 <b>المحتوى:</b> {s['title']}\n"
                f"📊 <b>التقدم:</b> {s['pct']:.1f}% ({s['pos_min']}/{s['tot_min']} دقيقة)\n"
                f"📡 <b>نوع البث:</b> {p_icon}\n"
            )
        send_message(chat_id, "\n".join(lines))
        return

    if text.startswith("/status"):
        st = get_ai_status()
        torrents = get_torrent_downloads()
        active = st.get("active_job") if isinstance(st, dict) else None
        pending = st.get("pending_count", 0) if isinstance(st, dict) else 0

        if not active and pending == 0 and not torrents:
            send_message(chat_id, "💤 <b>لا توجد تحميلات نشطة حالياً.</b>\nالمحرك جاهز وفي انتظار طلباتك!")
            return

        status_lines = ["⚡ <b>حالة التحميلات الحالية:</b>\n"]
        if active:
            title = active.get("title") or active.get("query") or "غير مسمى"
            source = active.get("source", "محرك الذكاء الاصطناعي")
            status_lines.append(f"🤖 <b>تحميل مباشر (AI):</b> {title}")
            status_lines.append(f"📡 <b>المصدر:</b> {source}\n")

        if torrents:
            status_lines.append("🌊 <b>تنزيلات التورنت (Sonarr/Radarr):</b>")
            for t in torrents[:5]:
                t_name = t.get("name", "Torrent")
                if len(t_name) > 35:
                    t_name = t_name[:32] + "..."
                prog = t.get("progress", 0) * 100
                speed = t.get("dlspeed", 0) / 1024 / 1024
                seeds = t.get("num_seeds", 0)
                status_lines.append(f"• <b>{t_name}</b>\n  📊 التقدم: <code>{prog:.1f}%</code> | ⚡ السرعة: <code>{speed:.2f} MB/s</code> (🌱 {seeds})")
            if len(torrents) > 5:
                status_lines.append(f"<i>...و {len(torrents) - 5} ملفات أخرى قيد التنزيل</i>")
            status_lines.append("")

        if pending > 0:
            status_lines.append(f"⏳ <b>في الانتظار:</b> {pending} ملفات")

        send_message(chat_id, "\n".join(status_lines))
        return

    if text.startswith("/history"):
        hist = get_ai_history()
        items = (hist.get("history") or [])[-5:]
        if not items:
            send_message(chat_id, "📋 لا توجد عمليات سابقة بعد.")
            return

        lines = ["📋 <b>آخر ما تم تحميله في NetFelix:</b>\n"]
        for it in reversed(items):
            status_icon = "✅" if it.get("status") == "COMPLETED" else "⏳"
            lines.append(f"{status_icon} <b>{it.get('title') or it.get('query')}</b> ({it.get('source', 'AI')})")
        send_message(chat_id, "\n".join(lines))
        return

    if text.startswith("/refresh"):
        if refresh_jellyfin():
            send_message(chat_id, "🔄 <b>تم إرسال أمر فحص وتحديث مكتبة Jellyfin بنجاح!</b>")
        else:
            send_message(chat_id, "❌ تعذر إرسال أمر التحديث.")
        return

    if text.startswith("/recommend"):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("rec", "/home/dell/Desktop/My_NetFelix/scripts/ai_recommendations.py")
            rec_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rec_mod)
            rec = rec_mod.pick_recommendation()
            if rec:
                msg = (
                    f"🌟 <b>سهرة اليوم من اختيار الذكاء الاصطناعي:</b>\n\n"
                    f"🎬 <b>{rec.get('title')}</b> ({rec.get('releaseDate')})\n"
                    f"⭐ <b>التقييم:</b> {rec.get('rating')}/10\n\n"
                    f"📝 <i>{rec.get('overview')}</i>\n\n"
                    f"💡 <i>لتحميل هذا العمل مباشرة، اضغط على اسمه أدناه:</i>"
                )
                buttons = [
                    {"text": f"📥 تحميل {rec.get('title')}", "callback_data": f"req:movie:{rec.get('id')}:{rec.get('title')}"}
                ]
                poster = rec.get("poster")
                if poster:
                    send_photo(chat_id, poster, caption=msg, reply_markup={"inline_keyboard": [buttons]})
                else:
                    send_message(chat_id, msg, reply_markup={"inline_keyboard": [buttons]})
            else:
                send_message(chat_id, "تعذر إنشاء الاقتراح حالياً.")
        except Exception as e:
            send_message(chat_id, f"خطأ في جلب الاقتراح: {e}")
        return

    # Natural Language / Query Request
    is_tv = any(w in text.lower() for w in ["مسلسل", "series", "season", "حلقات", "حلقة", "انمي", "anime", "موسم"])
    media_type = "tv" if is_tv else "movie"

    clean_query = re.sub(r"^(مسلسل|سلسلة|حلقات|فيلم|series|season)\s+", "", text, flags=re.IGNORECASE).strip()
    clean_query = clean_query.replace("بالمصري", "").replace("مدبلج", "").strip()
    dub_mode = "egyptian" if ("بالمصري" in text or "مدبلج" in text) else "auto"

    type_label = "مسلسل" if is_tv else "فيلم"
    send_message(chat_id, f"🔍 <b>جاري البحث والتحميل لـ {type_label}:</b> <i>{clean_query}</i> بالذكاء الاصطناعي...")

    res = request_download(clean_query, media_type=media_type, dub_mode=dub_mode)
    if "error" in res:
        send_message(chat_id, f"❌ حدث خطأ أثناء إرسال الطلب: {res['error']}")
    else:
        send_message(
            chat_id,
            f"🚀 <b>{res.get('message', 'تم استلام الطلب بنجاح!')}</b>\n"
            f"سأقوم بإعلامك فور اكتمال التنزيل وأرشفته في Jellyfin."
        )


def load_notified():
    """Load previously notified item keys."""
    if NOTIFIED_FILE.exists():
        try:
            with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_notified(notified_set):
    """Save notified item keys."""
    try:
        with open(NOTIFIED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(notified_set), f)
    except Exception as e:
        logger.warning(f"Failed to save notified file: {e}")


def check_and_send_completion_notifications(notified_set):
    """Check AI history and qBittorrent for newly completed downloads and notify."""
    # 1. Check AI Media Agent History
    hist = get_ai_history()
    history_items = hist.get("history") or []
    for item in history_items:
        job_id = str(item.get("id"))
        status = item.get("status")
        title = item.get("title") or item.get("query")
        if status == "COMPLETED" and job_id not in notified_set:
            notified_set.add(job_id)
            save_notified(notified_set)
            msg = (
                f"🎉 <b>اكتمل تنزيل المحتوى بنجاح!</b>\n\n"
                f"🎬 <b>العنوان:</b> {title}\n"
                f"📡 <b>المصدر:</b> {item.get('source', 'محرك الذكاء الاصطناعي')}\n"
                f"🍿 تم فحص المكتبة وأصبح متوفراً الآن في Jellyfin!"
            )
            broadcast_notification(msg)

    # 2. Check qBittorrent completed torrents
    completed_torrents = get_completed_torrents()
    for t in completed_torrents:
        h = t.get("hash")
        name = t.get("name")
        size_gb = t.get("total_size", 0) / (1024 * 1024 * 1024)
        if h and h not in notified_set:
            notified_set.add(h)
            save_notified(notified_set)
            msg = (
                f"🎉 <b>تم اكتمال تنزيل التورنت بنجاح!</b>\n\n"
                f"🎬 <b>الملف:</b> {name}\n"
                f"📦 <b>الحجم:</b> {size_gb:.2f} GB\n"
                f"🍿 تم إدراجه وتوليد الترجمة العربية وهو جاهز للمشاهدة في Jellyfin!"
            )
            broadcast_notification(msg)


def main():
    global BOT_TOKEN, ALLOWED_USER_ID
    if not BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set in .env. Bot daemon is standing by.")
        while True:
            time.sleep(60)
            load_env()
            BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "850274229").strip()
            if BOT_TOKEN:
                logger.info("TELEGRAM_BOT_TOKEN detected! Starting Telegram Bot polling...")
                break

    logger.info("Starting Supercharged NetFelix Telegram Bot...")
    offset = 0

    # Test token
    me = telegram_api("getMe")
    if me and me.get("ok"):
        bot_user = me["result"]["username"]
        logger.info(f"Bot connected successfully as @{bot_user}")
        telegram_api("setMyCommands", {
            "commands": [
                {"command": "start", "description": "بدء استخدام البوت ومساعد NetFelix"},
                {"command": "search", "description": "بحث تفاعلي بالبوستر وأزرار التحميل"},
                {"command": "nowplaying", "description": "عرض ما يتم تشغيله على الشاشات حالياً"},
                {"command": "status", "description": "حالة التنزيلات والتورنت الحية"},
                {"command": "history", "description": "عرض آخر التحميلات المكتملة"},
                {"command": "recommend", "description": "اقتراح سهرة اليوم بالذكاء الاصطناعي"},
                {"command": "refresh", "description": "تحديث وفحص مكتبة Jellyfin فوراً"}
            ]
        })
    else:
        logger.error("Failed to authenticate bot token. Verify TELEGRAM_BOT_TOKEN in .env.")

    notified_set = load_notified()
    last_check_time = 0

    while True:
        try:
            # Poll for new messages and callback queries
            updates = telegram_api("getUpdates", {"offset": offset, "timeout": 20})
            if updates and updates.get("ok"):
                for u in updates.get("result", []):
                    offset = u["update_id"] + 1
                    if "message" in u:
                        handle_message(u["message"])
                    elif "callback_query" in u:
                        handle_callback_query(u["callback_query"])

            # Periodic check for completed downloads (every 25 seconds)
            now = time.time()
            if now - last_check_time > 25:
                check_and_send_completion_notifications(notified_set)
                last_check_time = now

        except Exception as e:
            logger.error(f"Polling loop exception: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()
