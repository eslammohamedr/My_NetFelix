#!/usr/bin/env python3
"""
NetFelix Telegram Downloader Bot
Allows controlling the AI Media Agent from anywhere via Telegram:
- Send any movie, series, play, or cartoon name to download.
- Send direct URLs (YouTube, m3u8, direct video links).
- /status : Check active downloads & queue.
- /history : Show recent completed downloads.
- /refresh : Trigger Jellyfin library refresh.
- Auto-notifies when downloads complete.
"""

import os
import sys
import time
import json
import logging
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
AI_SERVICE_URL = "http://127.0.0.1:8092"


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
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()


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


def send_message(chat_id, text, parse_mode="HTML"):
    """Send text message to Telegram chat."""
    return telegram_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    })


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


def handle_message(msg):
    """Process incoming message from Telegram."""
    chat_id = msg.get("chat", {}).get("id")
    user_id = str(msg.get("from", {}).get("id", ""))
    first_name = msg.get("from", {}).get("first_name", "المستخدم")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return

    # Check security whitelist
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        send_message(
            chat_id,
            f"⚠️ عذراً {first_name}، أنت غير مصرح لك باستخدام هذا البوت.\n"
            f"معرّف حسابك (User ID): <code>{user_id}</code>\n"
            f"قم بإضافته إلى متغير <code>TELEGRAM_ALLOWED_USER_ID</code> في ملف <code>.env</code> على السيرفر."
        )
        return

    if text.startswith("/start"):
        welcome = (
            f"👋 <b>أهلاً بك يا {first_name} في بوت NetFelix الذكي!</b>\n\n"
            f"أنا مساعدك الشخصي لتحميل أي فيلم أو مسلسل مباشرة إلى سيرفر منزلك وأنت في أي مكان في العالم 🌍\n\n"
            f"📌 <b>كيف تستخدم البوت؟</b>\n"
            f"• أرسل اسم أي فيلم أو مسلسل أو مسرحية بالعربي أو الإنجليزي.\n"
            f"• أرسل أي رابط مباشر أو رابط يوتيوب.\n\n"
            f"⚡ <b>الأوامر المتاحة:</b>\n"
            f"• /status - عرض حالة التحميلات الحالية وشريط التقدم.\n"
            f"• /history - عرض آخر ما تم تحميله بنجاح.\n"
            f"• /refresh - تحديث مكتبة Jellyfin فوراً.\n\n"
            f"<i>معرّف حسابك (User ID): <code>{user_id}</code></i>"
        )
        send_message(chat_id, welcome)
        return

    if text.startswith("/status"):
        st = get_ai_status()
        if "error" in st:
            send_message(chat_id, f"❌ تعذر الاتصال بمحرك التحميل: {st['error']}")
            return

        active = st.get("active_job")
        pending = st.get("pending_count", 0)
        if not active and pending == 0:
            send_message(chat_id, "💤 <b>لا توجد تحميلات نشطة حالياً.</b>\nالمحرك جاهز وفي انتظار طلباتك!")
        else:
            title = active.get("title") or active.get("query") if active else "غير مسمى"
            source = active.get("source", "محرك الذكاء الاصطناعي") if active else ""
            status = (
                f"⚡ <b>حالة التحميل الآن:</b>\n\n"
                f"🎬 <b>جاري تحميل:</b> {title}\n"
                f"📡 <b>المصدر:</b> {source}\n"
                f"⏳ <b>في الانتظار:</b> {pending} ملفات\n"
            )
            send_message(chat_id, status)
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
                    f"💡 <i>لتحميل هذا الفيلم، أرسل اسمه الآن: <code>{rec.get('title')}</code></i>"
                )
                send_message(chat_id, msg)
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


def main():
    global BOT_TOKEN, ALLOWED_USER_ID
    if not BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set in .env. Bot daemon is standing by.")
        while True:
            time.sleep(60)
            load_env()
            BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
            if BOT_TOKEN:
                logger.info("TELEGRAM_BOT_TOKEN detected! Starting Telegram Bot polling...")
                break

    logger.info("Starting NetFelix Telegram Downloader Bot...")
    offset = 0

    # Test token
    me = telegram_api("getMe")
    if me and me.get("ok"):
        bot_user = me["result"]["username"]
        logger.info(f"Bot connected successfully as @{bot_user}")
        telegram_api("setMyCommands", {
            "commands": [
                {"command": "start", "description": "بدء استخدام البوت ومساعد NetFelix"},
                {"command": "status", "description": "عرض حالة التحميلات وطابور الانتظار"},
                {"command": "history", "description": "عرض آخر التحميلات المكتملة"},
                {"command": "recommend", "description": "اقتراح سهرة اليوم بالذكاء الاصطناعي"},
                {"command": "refresh", "description": "تحديث وفحص مكتبة Jellyfin فوراً"}
            ]
        })
    else:
        logger.error(f"Failed to authenticate bot token. Verify TELEGRAM_BOT_TOKEN in .env.")

    last_active_id = None

    while True:
        try:
            # Poll for new messages
            updates = telegram_api("getUpdates", {"offset": offset, "timeout": 20})
            if updates and updates.get("ok"):
                for u in updates.get("result", []):
                    offset = u["update_id"] + 1
                    if "message" in u:
                        handle_message(u["message"])

            # Check if active download completed and notify
            st = get_ai_status()
            active = st.get("active_job")
            current_active_id = active.get("id") if active else None

            if last_active_id and not current_active_id:
                # Job finished! Get last history item
                hist = get_ai_history()
                history_list = hist.get("history") or []
                if history_list:
                    last_item = history_list[-1]
                    if last_item.get("id") == last_active_id and last_item.get("status") == "COMPLETED":
                        if ALLOWED_USER_ID:
                            send_message(
                                ALLOWED_USER_ID,
                                f"🎉 <b>اكتمل التحميل بنجاح!</b>\n\n"
                                f"🎬 <b>العنوان:</b> {last_item.get('title')}\n"
                                f"🍿 تم فحص المكتبة وأصبح متاحاً للمشاهدة الآن في Jellyfin!"
                            )
            last_active_id = current_active_id

        except Exception as e:
            logger.error(f"Polling loop exception: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()
