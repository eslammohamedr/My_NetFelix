#!/usr/bin/env python3
"""
NetFelix Supercharged Telegram Bot
Allows controlling the NetFelix Media ecosystem from anywhere via Telegram:
- Real-time Wi-Fi Device Discovery & Intruder Watchdog (/devices)
- Laptop Server Telemetry, CPU Temperature & AC Power Alarm (/server)
- Interactive TV Playback Remote Control (/nowplaying with play/pause/stop/seek)
- On-Demand Arabic Subtitle Generator & Sync (/subtitles <title>)
- AI Arabic & English Voice Note Recognition (Voice-to-Download)
- Tailscale Zero-Config Remote Access Status (/tailscale)
- One-Tap Interactive Keyboard for Mobile Screens
- Direct Magnet & Torrent Link Ingestion
- Interactive search with Posters & Inline Buttons (/search <name>)
- Active Torrent & AI Download Progress (/status)
- AI Daily Recommendations (/recommend)
- Jellyfin Library Refresh (/refresh)
- Instant Push Notifications on Download Completion with Posters
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
import shutil
import datetime
import subprocess
import threading
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
PROJECT_DIR = Path("/home/dell/Desktop/My_NetFelix")
AGY_BIN = "/home/dell/.local/bin/agy"
AGY_SESSIONS_FILE = CONFIG_DIR / "agy_telegram_sessions.json"
CODEX_BIN = "/home/dell/.local/bin/codex"
CODEX_SESSIONS_FILE = CONFIG_DIR / "codex_telegram_sessions.json"

SUBSCRIBERS_FILE = CONFIG_DIR / "telegram_subscribers.json"
NOTIFIED_FILE = CONFIG_DIR / "telegram_notified.json"
DEVICES_FILE = CONFIG_DIR / "known_devices.json"
PARENTAL_SEEN_FILE = CONFIG_DIR / "parental_seen_queries.json"
PARENTAL_COOLDOWN_FILE = CONFIG_DIR / "parental_cooldown.json"

MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "📱 الأجهزة المتصلة"}, {"text": "📺 ريموت الشاشة"}],
        [{"text": "🍿 شاشات العرض"}, {"text": "🎬 وضع السينما"}],
        [{"text": "💡 سهرة اليوم"}, {"text": "🧹 تنظيف المساحة"}],
        [{"text": "⚡ سرعة التورنت"}, {"text": "📊 حالة السيرفر"}],
        [{"text": "🔄 فحص المكتبة"}, {"text": "🌐 ريموت Tailscale"}],
        [{"text": "🤖 محادثة AGY"}, {"text": "⚡ فتح Codex --yolo"}]
    ],
    "resize_keyboard": True
}

AGY_KEYBOARD = {
    "keyboard": [
        [{"text": "🆕 جلسة جديدة"}, {"text": "🔄 متابعة الجلسة"}],
        [{"text": "⚡ فتح Codex --yolo"}, {"text": "📊 حالة السيرفر"}],
        [{"text": "❌ إنهاء محادثة AGY"}]
    ],
    "resize_keyboard": True
}

CODEX_KEYBOARD = {
    "keyboard": [
        [{"text": "🆕 جلسة جديدة"}, {"text": "🔄 متابعة الجلسة"}],
        [{"text": "🤖 محادثة AGY"}, {"text": "🖥️ فتح في Terminal"}],
        [{"text": "📊 حالة السيرفر"}, {"text": "❌ إنهاء محادثة Codex"}]
    ],
    "resize_keyboard": True
}


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
JELLYSEERR_KEY = os.getenv("JELLYSEERR_API_KEY", "")
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "http://127.0.0.1:8096").rstrip("/")
JELLYFIN_KEY = os.getenv("JELLYFIN_API_KEY", "")
JELLYFIN_AUTH = f'MediaBrowser Client="Jellyseerr", DeviceId="5e868332d3e44ac4b2039ae239698f4d", Version="2.7.3", Token="{JELLYFIN_KEY}"'

LAST_POWER_ONLINE = None


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
    except urllib.error.HTTPError as e:
        desc = ""
        try:
            raw = e.read().decode("utf-8", errors="ignore")
            err_body = json.loads(raw)
            desc = err_body.get("description", "")
            if "message is not modified" in desc.lower():
                return {"ok": False, "description": "not_modified"}
        except Exception:
            pass
        logger.error(f"Telegram API HTTP error ({method}): {e} - {desc}")
        return None
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
    if reply_markup is not None:
        if reply_markup is not False:
            payload["reply_markup"] = reply_markup
    else:
        payload["reply_markup"] = MAIN_KEYBOARD
    return telegram_api("sendMessage", payload)


def edit_telegram_message(chat_id, message_id, text, parse_mode="HTML"):
    """Edits an existing Telegram message with error handling and fallback."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    res = telegram_api("editMessageText", payload)
    if res and res.get("description") == "not_modified":
        return res
    if not res or not res.get("ok"):
        # If HTML parsing failed or formatting error, retry with plain text
        if parse_mode:
            payload.pop("parse_mode", None)
            res = telegram_api("editMessageText", payload)
            if res and res.get("description") == "not_modified":
                return res
    return res


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
        return send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
    return res


def broadcast_notification(text, photo_url=None):
    """Broadcast notification to all subscribed users."""
    for chat_id in get_subscribers():
        try:
            if photo_url:
                send_photo(chat_id, photo_url, caption=text, reply_markup=MAIN_KEYBOARD)
            else:
                send_message(chat_id, text, reply_markup=MAIN_KEYBOARD)
        except Exception as e:
            logger.warning(f"Failed to notify chat {chat_id}: {e}")


# ==========================================
# Antigravity CLI (AGY) Interactive Integration
# ==========================================

def load_agy_sessions():
    """Loads active AGY conversation sessions from disk."""
    if AGY_SESSIONS_FILE.exists():
        try:
            with open(AGY_SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_agy_sessions(sessions):
    """Saves active AGY conversation sessions to disk."""
    try:
        with open(AGY_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save AGY sessions: {e}")


def is_agy_mode(chat_id):
    """Checks if chat is currently in interactive AGY mode."""
    sessions = load_agy_sessions()
    session = sessions.get(str(chat_id), {})
    return session.get("active", False)


def set_agy_mode(chat_id, active=True, continue_conv=True):
    """Enables or disables interactive AGY mode for chat."""
    sessions = load_agy_sessions()
    cid = str(chat_id)
    if active:
        sessions[cid] = {
            "active": True,
            "continue_conv": continue_conv,
            "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        if cid in sessions:
            sessions[cid]["active"] = False
    save_agy_sessions(sessions)


def markdown_to_telegram_html(md_text):
    """Converts common Markdown syntax (bold, italic, code blocks) to Telegram-safe HTML."""
    if not md_text:
        return ""
    code_blocks = []
    def save_code_block(match):
        code = match.group(1)
        code_blocks.append(f"<pre><code>{html.escape(code.strip())}</code></pre>")
        return f"ZZZCODEBLOCK{len(code_blocks)-1}ZZZ"

    # Multi-line code blocks ```lang\n...\n```
    text = re.sub(r"```(?:\w+)?\n?(.*?)```", save_code_block, md_text, flags=re.DOTALL)

    inline_codes = []
    def save_inline_code(match):
        code = match.group(1)
        inline_codes.append(f"<code>{html.escape(code)}</code>")
        return f"ZZZINLINECODE{len(inline_codes)-1}ZZZ"

    # Inline code `...`
    text = re.sub(r"`([^`\n]+)`", save_inline_code, text)

    # Escape HTML
    text = html.escape(text)

    # Bold **...** or __...__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # Italic *...* or _..._
    text = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", text)

    # Restore code blocks & inline codes
    for i, cb in enumerate(code_blocks):
        text = text.replace(f"ZZZCODEBLOCK{i}ZZZ", cb)
    for i, ic in enumerate(inline_codes):
        text = text.replace(f"ZZZINLINECODE{i}ZZZ", ic)

    return text


def send_long_telegram_message(chat_id, text, reply_markup=None):
    """Sends text in chunks <= 3900 characters, trying HTML first and falling back to plain text."""
    max_len = 3900
    if len(text) <= max_len:
        chunks = [text]
    else:
        chunks = []
        curr = ""
        for line in text.split("\n"):
            if len(curr) + len(line) + 1 > max_len:
                if curr:
                    chunks.append(curr)
                    curr = ""
                while len(line) > max_len:
                    chunks.append(line[:max_len])
                    line = line[max_len:]
                curr = line
            else:
                curr = (curr + "\n" + line) if curr else line
        if curr:
            chunks.append(curr)

    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        res = send_message(chat_id, chunk, reply_markup=markup, parse_mode="HTML")
        if not res or not res.get("ok"):
            send_message(chat_id, chunk, reply_markup=markup, parse_mode=None)


def handle_agy_task(chat_id, prompt, continue_conv=True):
    """Runs AGY CLI in the project directory with live streaming output to Telegram."""
    agy_exec = shutil.which("agy") or AGY_BIN
    if not os.path.exists(agy_exec):
        send_message(chat_id, "❌ لم يتم العثور على أداة agy في المسار: /home/dell/.local/bin/agy", reply_markup=AGY_KEYBOARD)
        return

    prompt_preview = prompt[:70] + ("..." if len(prompt) > 70 else "")
    init_msg = (
        "💻 <b>Antigravity CLI (Live):</b>\n"
        f"📝 <i>\"{html.escape(prompt_preview)}\"</i>\n"
        "────────────────────\n"
        "⏳ <i>جاري تشغيل الجلسة وبدء المعالجة...</i>"
    )
    status_res = send_message(chat_id, init_msg, reply_markup=AGY_KEYBOARD)
    msg_id = status_res.get("result", {}).get("message_id") if status_res else None

    # Send typing status in background
    stop_typing = threading.Event()
    def keep_typing():
        while not stop_typing.is_set():
            telegram_api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
            stop_typing.wait(4.0)

    typing_thread = threading.Thread(target=keep_typing, daemon=True)
    typing_thread.start()

    cmd = [agy_exec, "-p", prompt, "--output-format", "stream-json", "--dangerously-skip-permissions"]
    if continue_conv:
        cmd.append("--continue")

    env = os.environ.copy()
    env["PATH"] = f"/home/dell/.local/bin:/usr/local/bin:/usr/bin:/bin:{env.get('PATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    accumulated_text = ""
    active_tool = None
    tool_history = []
    final_response = None
    last_edit_time = 0.0
    last_sent_content = ""
    proc = None
    stderr_output = ""

    def push_live_update(force=False):
        nonlocal last_edit_time, last_sent_content
        if not msg_id:
            return
        now = time.time()
        if not force and (now - last_edit_time < 1.3):
            return

        header = (
            "💻 <b>Antigravity CLI (Live):</b>\n"
            f"📝 <i>\"{html.escape(prompt_preview)}\"</i>\n"
            "────────────────────\n"
        )
        tools_part = ""
        if tool_history:
            for t in tool_history[-2:]:
                tools_part += f"⚙️ <code>{html.escape(t)}</code>\n"
        if active_tool:
            tools_part += f"🔧 <i>{html.escape(active_tool[:70])}...</i>\n"

        if tools_part and accumulated_text:
            tools_part += "\n"

        body = tools_part
        if accumulated_text:
            snippet = accumulated_text
            if len(snippet) > 2800:
                snippet = "..." + snippet[-2800:]
            body += f"<pre>{html.escape(snippet)}</pre>"
        elif not tools_part:
            body = "⏳ <i>جاري التفكير والتنفيذ...</i>"

        footer = "\n────────────────────\n⚡ <i>جاري التوليد المباشر...</i>"
        full_text = header + body + footer

        if full_text != last_sent_content:
            last_sent_content = full_text
            last_edit_time = now
            edit_telegram_message(chat_id, msg_id, full_text)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env
        )

        for raw_line in iter(proc.stdout.readline, ""):
            line = raw_line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                accumulated_text += raw_line
                push_live_update()
                continue

            event_type = data.get("event")
            if event_type == "step_update":
                su = data.get("step_update", {})
                stype = su.get("step_type")
                state = su.get("state")
                if stype == "tool":
                    tname = su.get("tool_name", "tool")
                    params = su.get("tool_info", {}).get("parameters", {})
                    summary = ""
                    if "CommandLine" in params:
                        summary = params["CommandLine"]
                    elif "AbsolutePath" in params:
                        summary = os.path.basename(params["AbsolutePath"])
                    elif "TargetFile" in params:
                        summary = os.path.basename(params["TargetFile"])
                    elif params:
                        summary = str(list(params.values())[0])

                    if state == "ACTIVE":
                        active_tool = f"{tname}: {summary}" if summary else tname
                    elif state == "DONE":
                        done_label = f"✓ {tname}: {summary[:40]}" if summary else f"✓ {tname}"
                        tool_history.append(done_label)
                        active_tool = None
                    push_live_update()

                elif stype == "agent_response":
                    delta = su.get("text_delta", "")
                    if delta:
                        accumulated_text += delta
                        push_live_update()

            elif event_type == "result":
                res_obj = data.get("result", {})
                final_response = res_obj.get("response", "")
                break

        if proc.stdout:
            proc.stdout.close()
        stderr_output = proc.stderr.read() if proc.stderr else ""
        if proc.stderr:
            proc.stderr.close()
        proc.wait(timeout=10)

    except Exception as e:
        logger.error(f"AGY live execution error: {e}")
        accumulated_text += f"\n❌ حدث خطأ أثناء تشغيل AGY: {e}"
    finally:
        stop_typing.set()

    # Determine final output text
    final_text = (final_response or accumulated_text or "").strip()
    if not final_text:
        if proc and proc.returncode != 0:
            final_text = f"⚠️ خطأ أثناء تشغيل AGY:\n{stderr_output.strip() or f'Exit code {proc.returncode}'}"
        else:
            final_text = "✅ تم التنفيذ بنجاح (بدون مخرجات نصية)."

    # Final presentation
    if len(final_text) <= 3500:
        html_body = markdown_to_telegram_html(final_text)
        final_msg = (
            "💻 <b>Antigravity (AGY):</b>\n"
            "────────────────────\n"
            f"{html_body}"
        )
        if msg_id:
            res = edit_telegram_message(chat_id, msg_id, final_msg, parse_mode="HTML")
            if not res or not res.get("ok"):
                plain_msg = f"💻 Antigravity (AGY):\n────────────────────\n{final_text}"
                edit_telegram_message(chat_id, msg_id, plain_msg, parse_mode=None)
        else:
            send_message(chat_id, final_msg, reply_markup=AGY_KEYBOARD, parse_mode="HTML")
    else:
        if msg_id:
            summary_msg = (
                "💻 <b>Antigravity CLI:</b>\n"
                f"📝 <i>\"{html.escape(prompt_preview)}\"</i>\n"
                "────────────────────\n"
                "✅ <b>اكتمل التنفيذ بنجاح!</b>\n"
                "📥 <i>المخرجات كبيرة، جاري إرسالها مقسمة أدناه...</i>"
            )
            edit_telegram_message(chat_id, msg_id, summary_msg)
        send_long_telegram_message(chat_id, f"💻 <b>رد Antigravity:</b>\n\n{final_text}", reply_markup=AGY_KEYBOARD)


# ==========================================
# OpenAI Codex CLI (--yolo) Interactive Integration
# ==========================================

def load_codex_sessions():
    """Loads active Codex conversation sessions from disk."""
    if CODEX_SESSIONS_FILE.exists():
        try:
            with open(CODEX_SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_codex_sessions(sessions):
    """Saves active Codex conversation sessions to disk."""
    try:
        with open(CODEX_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save Codex sessions: {e}")


def is_codex_mode(chat_id):
    """Checks if chat is currently in interactive Codex mode."""
    sessions = load_codex_sessions()
    session = sessions.get(str(chat_id), {})
    return session.get("active", False)


def set_codex_mode(chat_id, active=True, continue_conv=True):
    """Enables or disables interactive Codex mode for chat."""
    sessions = load_codex_sessions()
    cid = str(chat_id)
    if active:
        set_agy_mode(chat_id, active=False)
        curr = sessions.get(cid, {})
        sessions[cid] = {
            "active": True,
            "continue_conv": continue_conv,
            "session_id": curr.get("session_id") if continue_conv else None,
            "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        if cid in sessions:
            sessions[cid]["active"] = False
    save_codex_sessions(sessions)


def find_active_display():
    """Detects active X11 display (:10.0, :0, or current)."""
    disp = os.environ.get("DISPLAY")
    if disp:
        try:
            r = subprocess.run(["xdpyinfo", "-display", disp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            if r.returncode == 0:
                return disp
        except Exception:
            pass

    for candidate in [":10.0", ":0", ":1"]:
        try:
            r = subprocess.run(["xdpyinfo", "-display", candidate], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            if r.returncode == 0:
                return candidate
        except Exception:
            continue
    return ":10.0"


def get_running_codex_pids():
    """Returns list of running codex --yolo PIDs."""
    pids = []
    try:
        out = subprocess.check_output(["pgrep", "-x", "codex"], text=True, timeout=5)
        for line in out.strip().splitlines():
            line = line.strip()
            if line and line.isdigit():
                p = int(line)
                try:
                    with open(f"/proc/{p}/cmdline", "rb") as f:
                        cmd = f.read().decode("utf-8", errors="ignore")
                        if "--yolo" in cmd or "yolo" in cmd:
                            pids.append(p)
                except Exception:
                    pass
    except subprocess.CalledProcessError:
        pass
    except Exception as e:
        logger.warning(f"Error checking codex pids: {e}")
    return pids


def open_codex_terminal(chat_id, force_new=False):
    """Launches or activates a terminal window running codex --yolo on the server desktop."""
    codex_exec = shutil.which("codex") or CODEX_BIN
    if not os.path.exists(codex_exec):
        send_message(chat_id, "❌ لم يتم العثور على أداة codex في المسار: /home/dell/.local/bin/codex", reply_markup=MAIN_KEYBOARD)
        return

    display = find_active_display()
    existing_pids = get_running_codex_pids()

    if existing_pids and not force_new:
        focused = False
        try:
            env = os.environ.copy()
            env["DISPLAY"] = display
            env["XAUTHORITY"] = "/home/dell/.Xauthority"
            q_out = subprocess.run(["xdotool", "search", "--class", "qterminal"], env=env, capture_output=True, text=True, timeout=3)
            win_ids = [w.strip() for w in q_out.stdout.splitlines() if w.strip()]
            if win_ids:
                subprocess.run(["xdotool", "windowactivate", win_ids[0]], env=env, timeout=3)
                focused = True
        except Exception:
            pass

        inline_kb = {
            "inline_keyboard": [
                [
                    {"text": "🖥️ فتح نافذة إضافية", "callback_data": "codex:new_window"},
                    {"text": "💬 محادثة في تليجرام", "callback_data": "codex:chat_mode"}
                ],
                [
                    {"text": "📊 فحص العمليات", "callback_data": "codex:status"},
                    {"text": "🛑 إغلاق Codex", "callback_data": "codex:kill"}
                ]
            ]
        }

        pids_str = ", ".join(str(p) for p in existing_pids)
        focus_msg = "✅ تم التركيز على نافذة Terminal في شاشة السيرفر." if focused else "النافذة مفتوحة في خلفية سطح المكتب."
        msg = (
            "⚡ <b>جلسة Codex (--yolo) نشطة بالفعل على السيرفر!</b>\n\n"
            f"🆔 <b>رقم العملية (PID):</b> <code>{pids_str}</code>\n"
            f"📺 <b>الشاشة النشطة:</b> <code>{display}</code>\n"
            f"📂 <b>المسار:</b> <code>/home/dell/Desktop/My_NetFelix</code>\n"
            "🛡️ <b>الوضع:</b> <code>--yolo</code> (صلاحيات كاملة بدون قيود)\n\n"
            f"💡 {focus_msg}\n"
            "يمكنك فتح نافذة جديدة، أو التحدث مباشرة هنا في تليجرام."
        )
        send_message(chat_id, msg, reply_markup=inline_kb)
        return

    term_bin = shutil.which("qterminal") or shutil.which("x-terminal-emulator")
    if not term_bin:
        send_message(chat_id, "❌ لم يتم العثور على محاكي Terminal (qterminal) لتشغيل الواجهة.", reply_markup=MAIN_KEYBOARD)
        return

    env = os.environ.copy()
    env["DISPLAY"] = display
    env["XAUTHORITY"] = "/home/dell/.Xauthority"
    env["PATH"] = f"/home/dell/.local/bin:/usr/local/bin:/usr/bin:/bin:{env.get('PATH', '')}"

    try:
        cmd = [term_bin, "-w", str(PROJECT_DIR), "-e", "zsh -c 'codex --yolo; exec zsh'"]
        subprocess.Popen(cmd, cwd=str(PROJECT_DIR), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)
        new_pids = get_running_codex_pids()
        new_pids_str = ", ".join(str(p) for p in new_pids) if new_pids else "قيد الإقلاع"

        inline_kb = {
            "inline_keyboard": [
                [
                    {"text": "💬 محادثة مباشرة في تليجرام", "callback_data": "codex:chat_mode"},
                    {"text": "🖥️ نافذة أخرى", "callback_data": "codex:new_window"}
                ],
                [
                    {"text": "📊 فحص الحالة", "callback_data": "codex:status"},
                    {"text": "🛑 إغلاق Codex", "callback_data": "codex:kill"}
                ]
            ]
        }

        success_msg = (
            "🚀 <b>تم فتح Codex (--yolo) في نافذة Terminal بنجاح!</b>\n\n"
            f"📺 <b>الشاشة:</b> <code>{display}</code>\n"
            f"🆔 <b>العملية (PID):</b> <code>{new_pids_str}</code>\n"
            f"📂 <b>المجلد:</b> <code>/home/dell/Desktop/My_NetFelix</code>\n"
            "🛡️ <b>الوضع:</b> <code>--yolo</code> (تنفيذ وتعديل بدون قيود)\n\n"
            "💻 النافذة مفتوحة الآن على شاشة اللابتوب وجاهزة للاستخدام.\n"
            "أو اضغط <b>محادثة مباشرة</b> للعمل مع Codex من تليجرام."
        )
        send_message(chat_id, success_msg, reply_markup=inline_kb)

    except Exception as e:
        logger.error(f"Failed to open codex terminal: {e}")
        send_message(chat_id, f"❌ حدث خطأ أثناء فتح Terminal: {e}", reply_markup=MAIN_KEYBOARD)


def handle_codex_task(chat_id, prompt, continue_conv=True):
    """Runs Codex CLI in exec mode with --yolo and live streaming output to Telegram."""
    codex_exec = shutil.which("codex") or CODEX_BIN
    if not os.path.exists(codex_exec):
        send_message(chat_id, "❌ لم يتم العثور على أداة codex في المسار: /home/dell/.local/bin/codex", reply_markup=CODEX_KEYBOARD)
        return

    sessions = load_codex_sessions()
    session_info = sessions.get(str(chat_id), {})
    session_id = session_info.get("session_id") if continue_conv else None

    prompt_preview = prompt[:70] + ("..." if len(prompt) > 70 else "")
    init_msg = (
        "⚡ <b>OpenAI Codex (--yolo Live):</b>\n"
        f"📝 <i>\"{html.escape(prompt_preview)}\"</i>\n"
        "────────────────────\n"
        "⏳ <i>جاري بدء الجلسة وتنفيذ الأوامر...</i>"
    )
    status_res = send_message(chat_id, init_msg, reply_markup=CODEX_KEYBOARD)
    msg_id = status_res.get("result", {}).get("message_id") if status_res else None

    # Keep typing indicator
    stop_typing = threading.Event()
    def keep_typing():
        while not stop_typing.is_set():
            telegram_api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
            stop_typing.wait(4.0)

    typing_thread = threading.Thread(target=keep_typing, daemon=True)
    typing_thread.start()

    cmd = [codex_exec, "exec"]
    if session_id:
        cmd += ["resume", session_id, "--yolo", "--json", prompt]
    else:
        cmd += ["--yolo", "--json", prompt]

    env = os.environ.copy()
    env["PATH"] = f"/home/dell/.local/bin:/usr/local/bin:/usr/bin:/bin:{env.get('PATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    accumulated_text = ""
    active_tool = None
    tool_history = []
    captured_session_id = session_id
    last_edit_time = 0.0
    last_sent_content = ""
    proc = None
    stderr_output = ""

    def push_live_update(force=False):
        nonlocal last_edit_time, last_sent_content
        if not msg_id:
            return
        now = time.time()
        if not force and (now - last_edit_time < 1.3):
            return

        header = (
            "⚡ <b>OpenAI Codex (--yolo Live):</b>\n"
            f"📝 <i>\"{html.escape(prompt_preview)}\"</i>\n"
            "────────────────────\n"
        )
        tools_part = ""
        if tool_history:
            for t in tool_history[-2:]:
                tools_part += f"⚙️ <code>{html.escape(t)}</code>\n"
        if active_tool:
            tools_part += f"🔧 <i>{html.escape(active_tool[:70])}...</i>\n"

        if tools_part and accumulated_text:
            tools_part += "\n"

        body = tools_part
        if accumulated_text:
            snippet = accumulated_text
            if len(snippet) > 2800:
                snippet = "..." + snippet[-2800:]
            body += f"<pre>{html.escape(snippet)}</pre>"
        elif not tools_part:
            body = "⏳ <i>جاري التفكير والتنفيذ...</i>"

        footer = "\n────────────────────\n⚡ <i>جاري التوليد المباشر...</i>"
        full_text = header + body + footer

        if full_text != last_sent_content:
            last_sent_content = full_text
            last_edit_time = now
            edit_telegram_message(chat_id, msg_id, full_text)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env
        )

        for raw_line in iter(proc.stdout.readline, ""):
            line = raw_line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                accumulated_text += raw_line
                push_live_update()
                continue

            event_type = data.get("type")
            if event_type == "thread.started":
                captured_session_id = data.get("thread_id")
                if captured_session_id:
                    sessions = load_codex_sessions()
                    cid = str(chat_id)
                    if cid in sessions:
                        sessions[cid]["session_id"] = captured_session_id
                        save_codex_sessions(sessions)

            elif event_type == "item.started":
                item = data.get("item", {})
                itype = item.get("type")
                if itype == "command_execution":
                    c_cmd = item.get("command", "")
                    active_tool = f"exec: {c_cmd}"
                    push_live_update()

            elif event_type == "item.completed":
                item = data.get("item", {})
                itype = item.get("type")
                if itype == "command_execution":
                    c_cmd = item.get("command", "")
                    exit_c = item.get("exit_code", 0)
                    summary = f"✓ exec: {c_cmd[:40]}" if exit_c == 0 else f"⚠️ exec: {c_cmd[:40]}"
                    tool_history.append(summary)
                    active_tool = None
                    push_live_update()
                elif itype == "agent_message":
                    text_delta = item.get("text", "")
                    if text_delta:
                        accumulated_text += ("\n\n" if accumulated_text else "") + text_delta
                        push_live_update()

            elif event_type == "turn.completed":
                break

        if proc.stdout:
            proc.stdout.close()
        stderr_output = proc.stderr.read() if proc.stderr else ""
        if proc.stderr:
            proc.stderr.close()
        proc.wait(timeout=10)

    except Exception as e:
        logger.error(f"Codex live execution error: {e}")
        accumulated_text += f"\n❌ حدث خطأ أثناء تشغيل Codex: {e}"
    finally:
        stop_typing.set()

    # Retry cleanly if session resume failed due to lock/conflict
    if proc and proc.returncode != 0 and session_id and ("conflict" in stderr_output.lower() or "active writer" in stderr_output.lower()):
        logger.info(f"Retrying Codex task with fresh session due to conflict on {session_id}")
        sessions = load_codex_sessions()
        cid = str(chat_id)
        if cid in sessions:
            sessions[cid]["session_id"] = None
            save_codex_sessions(sessions)
        return handle_codex_task(chat_id, prompt, continue_conv=False)

    final_text = accumulated_text.strip()
    if not final_text:
        if proc and proc.returncode != 0:
            final_text = f"⚠️ خطأ أثناء تشغيل Codex:\n{stderr_output.strip() or f'Exit code {proc.returncode}'}"
        else:
            final_text = "✅ تم التنفيذ بنجاح بواسطة Codex (--yolo)."

    if len(final_text) <= 3500:
        html_body = markdown_to_telegram_html(final_text)
        final_msg = (
            "⚡ <b>OpenAI Codex (--yolo):</b>\n"
            "────────────────────\n"
            f"{html_body}"
        )
        if msg_id:
            res = edit_telegram_message(chat_id, msg_id, final_msg, parse_mode="HTML")
            if not res or not res.get("ok"):
                plain_msg = f"⚡ OpenAI Codex (--yolo):\n────────────────────\n{final_text}"
                edit_telegram_message(chat_id, msg_id, plain_msg, parse_mode=None)
        else:
            send_message(chat_id, final_msg, reply_markup=CODEX_KEYBOARD, parse_mode="HTML")
    else:
        if msg_id:
            summary_msg = (
                "⚡ <b>OpenAI Codex (--yolo):</b>\n"
                f"📝 <i>\"{html.escape(prompt_preview)}\"</i>\n"
                "────────────────────\n"
                "✅ <b>اكتمل التنفيذ بنجاح!</b>\n"
                "📥 <i>المخرجات كبيرة، جاري إرسالها مقسمة أدناه...</i>"
            )
            edit_telegram_message(chat_id, msg_id, summary_msg)
        send_long_telegram_message(chat_id, f"⚡ <b>رد Codex (--yolo):</b>\n\n{final_text}", reply_markup=CODEX_KEYBOARD)


# ==========================================
# Network Device Scanner & Intrusion Watchdog
# ==========================================

def load_known_devices():
    """Load dictionary of known devices."""
    if DEVICES_FILE.exists():
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_known_devices(data):
    """Save dictionary of known devices."""
    try:
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save known devices: {e}")


def scan_network_devices():
    """Performs a fast ping scan on the 192.168.1.0/24 subnet."""
    try:
        out = subprocess.check_output(["nmap", "-sn", "192.168.1.0/24"], timeout=15).decode()
    except Exception as e:
        logger.error(f"Network scan error: {e}")
        return []

    devices = []
    current = {}
    for line in out.splitlines():
        if "Nmap scan report for" in line:
            raw = line.split("for ")[1].strip()
            m = re.match(r"(?:([^\s()]+)\s+\()?([0-9.]+)\)?", raw)
            if m:
                h_name = m.group(1) or ""
                ip = m.group(2)
            else:
                ip = raw
                h_name = ""
            current = {"ip": ip, "hostname": h_name, "mac": "", "vendor": "Unknown"}
            devices.append(current)
        elif "MAC Address:" in line and current:
            parts = line.split("MAC Address:")[1].strip().split(" ", 1)
            current["mac"] = parts[0].upper()
            if len(parts) > 1:
                current["vendor"] = parts[1].strip("()")

    for d in devices:
        if d["ip"] == "192.168.1.15":
            d["hostname"] = "NetFelix Server (هذا الجهاز)"
            d["vendor"] = "Host Server"
        if not d["hostname"] and d["mac"]:
            try:
                cmd = ["nmblookup", "-A", d["ip"]]
                nb = subprocess.check_output(cmd, timeout=0.4, stderr=subprocess.DEVNULL).decode()
                for nbl in nb.splitlines():
                    if "<00> -" in nbl and "<GROUP>" not in nbl:
                        d["hostname"] = nbl.split()[0].strip()
                        break
            except Exception:
                pass
    return devices


def format_devices_report(devices):
    """Formats connected devices into a readable Telegram message."""
    if not devices:
        return "❌ تعذر مسح شبكة الواي فاي حالياً. يرجى المحاولة بعد قليل."

    known = load_known_devices()
    now_str = datetime.datetime.now().strftime("%H:%M:%S")

    lines = [
        f"📶 <b>الأجهزة المتصلة بشبكة الواي فاي ({len(devices)} أجهزة):</b>",
        f"🕒 <i>آخر فحص: {now_str}</i>\n"
    ]

    for idx, d in enumerate(devices, 1):
        ip = d["ip"]
        mac = d["mac"]
        vendor = d.get("vendor", "Unknown")
        hostname = d.get("hostname", "")

        known_info = known.get(mac, {})
        alias = known_info.get("alias") or ""

        icon = "📱"
        if ip == "192.168.1.1":
            icon = "🌐"
            display_name = "راوتر المنزل الأساسي (ZTE Gateway)"
        elif ip == "192.168.1.15":
            icon = "🖥️"
            display_name = "سيرفر NetFelix (لابتوب الخادم)"
        elif alias:
            display_name = alias
            if any(w in alias.lower() for w in ["لابتوب", "كمبيوتر", "pc", "laptop"]):
                icon = "💻"
            elif any(w in alias.lower() for w in ["شاشة", "tv", "تلفزيون"]):
                icon = "📺"
        elif hostname:
            display_name = hostname
            if "LABTOP" in hostname or "PC" in hostname:
                icon = "💻"
        elif vendor != "Unknown":
            display_name = f"جهاز {vendor}"
            if any(w in vendor.lower() for w in ["samsung", "apple", "xiaomi", "huawei"]):
                icon = "📱"
            elif "intel" in vendor.lower():
                icon = "💻"
        else:
            display_name = "هاتف محمول / جهاز ذكي"

        mac_display = f"<code>{mac}</code>" if mac else "<i>المحلي</i>"
        lines.append(
            f"{idx}. {icon} <b>{display_name}</b>\n"
            f"   • IP: <code>{ip}</code>\n"
            f"   • MAC: {mac_display} | المصنع: <i>{vendor}</i>"
        )

    lines.append("\n💡 <i>لمعرفة نشاط أي جهاز وماذا يتصفح، اضغط على الزر بالأسفل 👇</i>")
    lines.append("<i>أو لتسمية جهاز:</i> <code>/name &lt;IP أو MAC&gt; الاسم</code>")

    buttons = []
    for d in devices:
        dip = d.get("ip")
        if dip and dip not in ("192.168.1.1", "192.168.1.15"):
            dmac = d.get("mac")
            k_info = known.get(dmac, {})
            dname = k_info.get("alias") or d.get("hostname") or d.get("vendor") or dip
            # Clean up display label
            clean_name = dname.split("(")[0].strip() if "(" in dname else dname
            buttons.append([{"text": f"🔍 نشاط: {clean_name[:16]} ({dip})", "callback_data": f"act:{dip}"}])

    keyboard = {"inline_keyboard": buttons} if buttons else None
    return "\n".join(lines), keyboard


def humanize_domain(d):
    """Translates cryptic CDN, streaming, and internal subdomains into clear human-friendly labels."""
    d = d.lower().strip(".")
    if d.endswith(".in-addr.arpa") or d.endswith(".ip6.arpa"):
        return None  # Filter out internal network routing lookups
    if "3gppnetwork.org" in d:
        return "📞 مكالمات الواي فاي (VoWiFi)"
    if "googlevideo.com" in d:
        return "📺 تشغيل فيديو يوتيوب (YouTube Stream)"
    if "ggpht.com" in d or "ytimg.com" in d:
        return "📺 وسائط وقنوات يوتيوب (YouTube Media)"
    if "phncdn.com" in d:
        return "🔞 خوادم تشغيل الفيديو (Video CDN)"
    if any(k in d for k in ["trafficjunky", "adtng.com", "etahub.com"]):
        return "🔞 خوادم توثيق وتصفح المواقع"
    if "fbcdn.net" in d or "fbsbx.com" in d:
        return "🔵 وسائط وصور فيسبوك (Facebook CDN)"
    if "cdninstagram.com" in d:
        return "📸 وسائط وصور إنستغرام (Instagram CDN)"
    if "mtalk.google.com" in d:
        return "🔔 إشعارات وتنبيهات أندرويد (Google Push)"
    if "connectivitycheck" in d or "connectivity" in d:
        return "📶 فحص اتصال الواي فاي بالإنترنت"
    if "inbox.google.com" in d or "mail.google.com" in d:
        return "✉️ بريد جوجل (Gmail / Inbox)"
    if "googleapis.com" in d:
        return "⚙️ خدمات نظام أندرويد (Google Services)"
    if "googletagmanager.com" in d or "analytics" in d:
        return "📊 إحصائيات التصفح (Analytics)"
    if d.startswith("www."):
        d = d[4:]
    return f"🌐 {d}"


def get_device_activity(ip):
    """Fetches recent web activity and categories from AdGuard for a specific IP."""
    import urllib.request
    from collections import Counter
    try:
        url = f"http://127.0.0.1:8085/control/querylog?search={ip}&limit=50"
        req = urllib.request.Request(url, headers={"Authorization": "Basic YWRtaW46bmV0ZmVsaXg="})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.load(r)

        entries = data.get("data", [])
        dev_name = get_device_name(ip)
        if not entries:
            return (
                f"📡 <b>تقرير نشاط الجهاز:</b> <b>{dev_name}</b> (<code>{ip}</code>)\n\n"
                f"ℹ️ لا توجد استعلامات مسجلة لهذا الجهاز في الـ DNS حتى الآن.\n\n"
                f"💡 <i>ملاحظة: لكي تظهر كل المواقع والتطبيقات التي يفتحها هذا الجهاز، يجب أن يكون الـ DNS في الراوتر أو في الجهاز مضبوطاً على <code>192.168.1.15</code>.</i>"
            )

        human_domains = []
        blocked_count = 0
        categories = Counter()

        for e in entries:
            q = e.get("question", {})
            d = q.get("name", "").lower()
            if not d:
                continue

            h = humanize_domain(d)
            if h:
                human_domains.append(h)

            if e.get("reason", "").startswith("Filter"):
                blocked_count += 1

            if is_adult_domain(d):
                categories["🔞 مواقع للبالغين (Adult Content)"] += 1
            elif any(k in d for k in ["youtube", "googlevideo", "ytimg", "youtu.be", "gvt1", "gvt2", "gvt3"]):
                categories["📺 يوتيوب (YouTube)"] += 1
            elif any(k in d for k in ["tiktok", "byteoversea", "ibytedtos", "musical.ly"]):
                categories["🎵 تيك توك (TikTok)"] += 1
            elif any(k in d for k in ["netflix", "nflx"]):
                categories["🍿 نتفليكس (Netflix)"] += 1
            elif any(k in d for k in ["facebook", "fbcdn", "fbsbx", "fb.me", "meta.com", "messenger"]):
                categories["🔵 فيسبوك (Facebook)"] += 1
            elif any(k in d for k in ["instagram", "cdninstagram", "ig.me"]):
                categories["📸 إنستغرام (Instagram)"] += 1
            elif any(k in d for k in ["whatsapp", "wa.me"]):
                categories["💬 واتساب (WhatsApp)"] += 1
            elif any(k in d for k in ["telegram", "t.me"]):
                categories["✈️ تيليجرام (Telegram)"] += 1
            elif any(k in d for k in ["twitter", "x.com", "twimg", "t.co"]):
                categories["🐦 تويتر / إكس (X)"] += 1
            elif "3gppnetwork.org" in d:
                categories["📞 مكالمات الواي فاي (VoWiFi)"] += 1
            elif any(k in d for k in ["snapchat"]):
                categories["👻 سناب شات (Snapchat)"] += 1
            elif any(k in d for k in ["discord"]):
                categories["🎮 ديسكورد (Discord)"] += 1
            elif any(k in d for k in ["spotify"]):
                categories["🎧 سبوتيفاي (Spotify)"] += 1
            elif any(k in d for k in ["google", "gstatic", "googleapis", "googleadservices", "googletagmanager", "doubleclick"]):
                categories["🔍 خدمات جوجل (Google)"] += 1
            elif any(k in d for k in ["apple", "icloud"]):
                categories["🍏 خدمات آبل (Apple)"] += 1
            elif any(k in d for k in ["samsung"]):
                categories["📱 خدمات سامسونج (Samsung)"] += 1

        lines = [
            f"🌐 <b>تقرير نشاط الجهاز:</b> <b>{dev_name}</b> (<code>{ip}</code>)\n",
            f"📊 <b>إجمالي الطلبات الأخيرة:</b> <code>{len(entries)}</code> طلب",
            f"🛡️ <b>إعلانات وتتبع تم حجبها:</b> <code>{blocked_count}</code> إعلان تم إيقافه ✅\n"
        ]

        if categories:
            lines.append("📱 <b>أبرز التطبيقات والخدمات المستخدمة:</b>")
            for cat, count in categories.most_common(6):
                lines.append(f"  • {cat}: <code>{count}</code> استعلام")
            lines.append("")

        c = Counter(human_domains)
        lines.append("🌍 <b>أكثر الأنشطة والمواقع زيارة مؤخراً:</b>")
        for dom, cnt in c.most_common(5):
            lines.append(f"  • {dom} (<code>{cnt}</code>)")

        lines.append("\n💡 <i>لإدارة أمان هذا الجهاز أو إيقاف مواقع معينة عنه:</i>\n<code>http://192.168.1.15:8085</code>")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error inspecting IP {ip}: {e}")
        return f"❌ تعذر جلب نشاط الجهاز: {e}"


def check_new_devices():
    """Background watchdog check for newly connected devices."""
    try:
        devices = scan_network_devices()
        known = load_known_devices()
        new_devices = []
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for d in devices:
            mac = d.get("mac")
            ip = d.get("ip")
            if not mac or ip in ("192.168.1.15", "192.168.1.1"):
                continue

            if mac not in known:
                known[mac] = {
                    "mac": mac,
                    "ip": ip,
                    "vendor": d.get("vendor", "Unknown"),
                    "hostname": d.get("hostname", ""),
                    "alias": "",
                    "first_seen": now_str,
                    "last_seen": now_str
                }
                new_devices.append(known[mac])
            else:
                known[mac]["last_seen"] = now_str
                known[mac]["ip"] = ip
                if d.get("hostname") and not known[mac].get("hostname"):
                    known[mac]["hostname"] = d["hostname"]

        if new_devices:
            save_known_devices(known)
            for nd in new_devices:
                v = nd["vendor"]
                h = nd["hostname"] or "غير محدد"
                alert = (
                    f"🚨 <b>تنبيه أمني: جهاز جديد اتصل بشبكة الواي فاي!</b>\n\n"
                    f"📍 <b>العنوان (IP):</b> <code>{nd['ip']}</code>\n"
                    f"🏷️ <b>الماك (MAC):</b> <code>{nd['mac']}</code>\n"
                    f"🏭 <b>المصنع:</b> <i>{v}</i>\n"
                    f"💻 <b>الاسم:</b> <i>{h}</i>\n"
                    f"⏰ <b>وقت الاتصال:</b> {now_str}\n\n"
                    f"💡 <i>لحفظ اسم لهذا الجهاز، اكتب:</i>\n"
                    f"<code>/name {nd['ip']} الاسم المطلوب</code>"
                )
                broadcast_notification(alert)
    except Exception as e:
        logger.error(f"Error in check_new_devices: {e}")


# ==========================================
# Laptop Server Telemetry & Power Watchdog
# ==========================================

def get_server_telemetry():
    """Collects CPU, RAM, Temp, Power, and Disk telemetry."""
    temp_c = 0
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp_c = int(f.read().strip()) // 1000
    except Exception:
        pass

    ac_online = True
    try:
        with open("/sys/class/power_supply/ACAD/online") as f:
            ac_online = (f.read().strip() == "1")
    except Exception:
        pass

    try:
        load1, load5, _ = os.getloadavg()
    except Exception:
        load1, load5 = 0.0, 0.0

    ram_used_gb, ram_total_gb, ram_pct = 0, 0, 0
    try:
        with open("/proc/meminfo") as f:
            m = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    m[parts[0].strip()] = int(parts[1].split()[0])
            total = m.get("MemTotal", 1)
            avail = m.get("MemAvailable", 0)
            used = total - avail
            ram_used_gb = used / (1024 * 1024)
            ram_total_gb = total / (1024 * 1024)
            ram_pct = (used / total) * 100
    except Exception:
        pass

    disk_free_gb, disk_total_gb, disk_pct_free = 0, 0, 0
    try:
        du = shutil.disk_usage("/media/dell/Data1")
        disk_free_gb = du.free / (1024 ** 3)
        disk_total_gb = du.total / (1024 ** 3)
        disk_pct_free = (du.free / du.total) * 100
    except Exception:
        pass

    docker_running = 0
    try:
        out = subprocess.check_output(["docker", "ps", "-q"], timeout=5).decode()
        docker_running = len([x for x in out.splitlines() if x.strip()])
    except Exception:
        pass

    return {
        "temp_c": temp_c,
        "ac_online": ac_online,
        "load1": load1,
        "load5": load5,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "ram_pct": ram_pct,
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb,
        "disk_pct_free": disk_pct_free,
        "docker_running": docker_running
    }


def format_server_report():
    """Formats server telemetry into an executive Telegram card."""
    data = get_server_telemetry()
    power_icon = "🔌 شاحن متصل (AC Power)" if data["ac_online"] else "🔋 يعمل على البطارية (Battery)"
    temp_icon = "❄️" if data["temp_c"] < 65 else ("🔥" if data["temp_c"] > 80 else "🌡️")

    lines = [
        "🖥️ <b>تقرير صحة وحالة سيرفر NetFelix:</b>\n",
        f"⚡ <b>مصدر الطاقة:</b> {power_icon}",
        f"{temp_icon} <b>حرارة المعالج (CPU):</b> <code>{data['temp_c']}°C</code>",
        f"⚙️ <b>ضغط المعالج (Load):</b> <code>{data['load1']:.2f}</code> (1m) | <code>{data['load5']:.2f}</code> (5m)",
        f"🧠 <b>الذاكرة (RAM):</b> <code>{data['ram_used_gb']:.1f} GB</code> / <code>{data['ram_total_gb']:.1f} GB</code> ({data['ram_pct']:.1f}%)",
        f"💾 <b>مساحة التخزين (Data1):</b> <code>{data['disk_free_gb']:.1f} GB</code> متاح ({data['disk_pct_free']:.1f}%)",
        f"🐳 <b>حاويات Docker:</b> <code>{data['docker_running']}</code> حاوية نشطة وقيد العمل ✅",
        "\n<i>💡 جميع الخدمات تعمل بكفاءة تحت إدارة NetFelix.</i>"
    ]
    return "\n".join(lines)


def check_power_status():
    """Checks for AC power transitions (unplugged/restored)."""
    global LAST_POWER_ONLINE
    try:
        power_path = Path("/sys/class/power_supply/ACAD/online")
        if not power_path.exists():
            return
        with open(power_path, "r") as f:
            is_online = (f.read().strip() == "1")

        if LAST_POWER_ONLINE is None:
            LAST_POWER_ONLINE = is_online
            return

        if LAST_POWER_ONLINE and not is_online:
            LAST_POWER_ONLINE = False
            msg = (
                "⚠️ <b>تنبيه عاجل: انقطعت الكهرباء عن السيرفر!</b>\n\n"
                "🔌 تم فصل الشاحن أو انقطاع التيار الكهربائي.\n"
                "🔋 السيرفر يعمل الآن على البطارية الداخلية لحين عودة الكهرباء."
            )
            broadcast_notification(msg)
        elif not LAST_POWER_ONLINE and is_online:
            LAST_POWER_ONLINE = True
            msg = (
                "⚡ <b>تمت استعادة الكهرباء بنجاح!</b>\n\n"
                "🔌 شاحن السيرفر متصل الآن ويعيد شحن البطارية."
            )
            broadcast_notification(msg)
    except Exception as e:
        logger.error(f"Error in check_power_status: {e}")


# ==========================================
# Family Protection & Adult Site Watchdog (Alert Only - No Blocking)
# ==========================================

ADULT_DOMAINS_FILE = CONFIG_DIR / "adult_domains.txt"
ADULT_DOMAINS_SET = set()
if ADULT_DOMAINS_FILE.exists():
    try:
        with open(ADULT_DOMAINS_FILE, "r", encoding="utf-8") as f:
            ADULT_DOMAINS_SET = set(line.strip().lower() for line in f if line.strip())
    except Exception as e:
        logger.warning(f"Error loading adult domains: {e}")


def is_adult_domain(domain):
    """Detects if a domain is an adult/pornographic site using the local 76,000+ domain database."""
    d = domain.lower().strip(".")
    if not d:
        return False
    # Whitelist torrent trackers incorrectly categorized in generic adult blocklists
    if any(d == t or d.endswith("." + t) for t in ("rarbg.to", "rarbg.me", "rarbg.com", "therarbg.to")):
        return False
    if d in ADULT_DOMAINS_SET:
        return True
    parts = d.split(".")
    if len(parts) > 2:
        root2 = ".".join(parts[-2:])
        if root2 in ADULT_DOMAINS_SET:
            return True
        root3 = ".".join(parts[-3:])
        if root3 in ADULT_DOMAINS_SET:
            return True
    keywords = ["porn", "xvideos", "xnxx", "redtube", "youporn", "stripchat", "chaturbate", "beeg.com", "brazzers", "spankbang", "eporner"]
    return any(k in d for k in keywords)


def get_device_name(client_ip):
    """Resolves friendly device name using live ARP table first to prevent DHCP IP collision false positives."""
    if client_ip in ("192.168.1.15", "127.0.0.1"):
        return "سيرفر NetFelix"
    if client_ip == "192.168.1.1":
        return "راوتر المنزل الأساسي"

    known = load_known_devices()

    # 1. ALWAYS check live ARP table first to find the real physical MAC currently using this IP
    active_mac = None
    try:
        with open("/proc/net/arp") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == client_ip:
                    m = parts[3].upper()
                    if m != "00:00:00:00:00:00":
                        active_mac = m
                        break
    except Exception:
        pass

    # If the active MAC is found in live ARP:
    if active_mac:
        if active_mac in known:
            info = known[active_mac]
            name = info.get("alias") or info.get("hostname")
            if not name and info.get("vendor") and info.get("vendor") != "Unknown":
                name = f"جهاز {info.get('vendor')} ({client_ip})"
            if name:
                return name
        # If active MAC is unknown/randomized, do NOT fall back to an old stale IP match of another device
        first_byte = active_mac.split(":")[0] if ":" in active_mac else ""
        if len(first_byte) == 2 and first_byte[1].upper() in ("2", "6", "A", "E"):
            return f"هاتف / جهاز غير مسمى ({client_ip})"
        return f"جهاز غير مسجل ({client_ip})"

    # 2. If no live ARP entry (device went offline immediately), check known devices sorted by most recently seen
    candidates = [info for mac, info in known.items() if info.get("ip") == client_ip]
    if candidates:
        candidates.sort(key=lambda x: x.get("last_seen", ""), reverse=True)
        best = candidates[0]
        name = best.get("alias") or best.get("hostname")
        if not name and best.get("vendor") and best.get("vendor") != "Unknown":
            name = f"جهاز {best.get('vendor')} ({client_ip})"
        if name:
            return name

    return f"جهاز ({client_ip})"


def load_seen_parental():
    if PARENTAL_SEEN_FILE.exists():
        try:
            with open(PARENTAL_SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen_parental(seen_set):
    try:
        trimmed = list(seen_set)[-500:]
        with open(PARENTAL_SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed, f)
    except Exception as e:
        logger.warning(f"Failed to save seen parental: {e}")


def load_parental_cooldown():
    """Loads parental alert cooldown timestamps (keyed by client_ip)."""
    if PARENTAL_COOLDOWN_FILE.exists():
        try:
            with open(PARENTAL_COOLDOWN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_parental_cooldown(cooldown_dict):
    """Saves parental alert cooldown timestamps to disk."""
    try:
        with open(PARENTAL_COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(cooldown_dict, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save parental cooldown: {e}")


SEEN_PARENTAL_QUERIES = load_seen_parental()


def check_parental_alerts():
    """Monitors AdGuard Query Log for adult domains and alerts via Telegram (Monitoring Only - No Blocking).
    Enforces a strict 1-hour cooldown (3600s) per device so users only receive at most 1 alert per hour.
    """
    global SEEN_PARENTAL_QUERIES
    try:
        url = "http://127.0.0.1:8085/control/querylog?limit=30"
        req = urllib.request.Request(url, headers={"Authorization": "Basic YWRtaW46bmV0ZmVsaXg="})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.load(r)

        entries = data.get("data", [])
        if not entries:
            return

        cooldowns = load_parental_cooldown()
        now_ts = time.time()
        cooldown_updated = False

        for e in entries:
            q = e.get("question", {})
            domain = q.get("name", "").lower().strip(".")
            client_ip = e.get("client", "")
            time_str = e.get("time", "")

            if not domain or client_ip in ("127.0.0.1", "::1"):
                continue

            # Check if domain is an adult site
            if is_adult_domain(domain):
                unique_key = f"{client_ip}:{domain}:{time_str[:19]}"
                if unique_key not in SEEN_PARENTAL_QUERIES:
                    SEEN_PARENTAL_QUERIES.add(unique_key)
                    save_seen_parental(SEEN_PARENTAL_QUERIES)

                    # 1-Hour Cooldown (3600 seconds) check
                    last_alert_ts = cooldowns.get(client_ip, 0)
                    if (now_ts - last_alert_ts) < 3600:
                        # Suppress notification if last alert for this device was within 60 minutes
                        continue

                    # Update device cooldown timestamp immediately
                    cooldowns[client_ip] = now_ts
                    cooldown_updated = True

                    device_name = get_device_name(client_ip)
                    now_display = datetime.datetime.now().strftime("%I:%M:%S %p")

                    alert_msg = (
                        "⚠️ <b>تنبيه أمان: محاولة فتح موقع للبالغين!</b>\n\n"
                        f"📱 <b>الجهاز:</b> <b>{device_name}</b>\n"
                        f"📍 <b>العنوان (IP):</b> <code>{client_ip}</code>\n"
                        f"🌐 <b>الموقع المطلوب:</b> <code>{domain}</code>\n"
                        f"⏰ <b>التوقيت:</b> <code>{now_display}</code>\n"
                        f"🔓 <b>الحالة:</b> <b>تم السماح بالاتصال (المراقبة فقط دون حجب)</b>\n"
                        f"⏳ <b>فترة التهدئة:</b> <i>لن يتم إرسال تنبيهات جديدة لهذا الجهاز لمدة 60 دقيقة.</i>\n\n"
                        "<i>💡 تم إرسال هذا التنبيه التلقائي لمتابعة نشاط الشبكة.</i>"
                    )
                    broadcast_notification(alert_msg)

        if cooldown_updated:
            save_parental_cooldown(cooldowns)
    except Exception as e:
        logger.error(f"Error in check_parental_alerts: {e}")


# ==========================================
# Voice Transcription & File Downloads
# ==========================================

def download_telegram_file(file_id, dest_path):
    """Downloads a file from Telegram by file_id."""
    try:
        f_info = telegram_api("getFile", {"file_id": file_id})
        if not f_info or not f_info.get("ok"):
            return False
        file_path = f_info["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        urllib.request.urlretrieve(download_url, dest_path)
        return True
    except Exception as e:
        logger.error(f"Error downloading telegram file {file_id}: {e}")
        return False

def transcribe_voice(file_id):
    """Downloads voice oga file from Telegram and transcribes via Google Speech."""
    try:
        f_info = telegram_api("getFile", {"file_id": file_id})
        if not f_info or not f_info.get("ok"):
            return None
        file_path = f_info["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        ts = int(time.time() * 1000)
        oga_path = f"/tmp/voice_{ts}.oga"
        flac_path = f"/tmp/voice_{ts}.flac"
        urllib.request.urlretrieve(download_url, oga_path)

        cmd = ["/home/dell/.local/bin/ffmpeg", "-y", "-i", oga_path, "-ar", "16000", "-ac", "1", flac_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)

        if os.path.exists(flac_path):
            with open(flac_path, "rb") as af:
                audio_data = af.read()
            url = "http://www.google.com/speech-api/v2/recognize?client=chromium&lang=ar-EG"
            req = urllib.request.Request(
                url,
                data=audio_data,
                headers={"Content-Type": "audio/x-flac; rate=16000"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                for line in raw.splitlines():
                    if line.strip():
                        try:
                            parsed = json.loads(line)
                            result = parsed.get("result", [])
                            if result and len(result) > 0:
                                alt = result[0].get("alternative", [])
                                if alt:
                                    transcript = alt[0].get("transcript")
                                    if transcript:
                                        try:
                                            os.remove(oga_path)
                                            os.remove(flac_path)
                                        except Exception:
                                            pass
                                        return transcript
                        except Exception:
                            pass
        try:
            if os.path.exists(oga_path): os.remove(oga_path)
            if os.path.exists(flac_path): os.remove(flac_path)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
    return None


# ==========================================
# Subtitles On-Demand Generator & Sync
# ==========================================

def sync_subtitles_for_query(query):
    """Finds matching video files and generates/syncs Arabic subtitles."""
    try:
        media_dir = Path("/media/dell/Data1/netfelix_data/media")
        video_files = []
        for ext in {".mkv", ".mp4", ".avi", ".m4v"}:
            video_files.extend(media_dir.rglob(f"*{ext}"))

        matches = [f for f in video_files if query.lower() in f.name.lower() or query.lower() in f.parent.name.lower()]
        if not matches:
            return 0, f"لم يتم العثور على ملفات وسائط مطابقة لـ: <i>{query}</i> في مكتبتك."

        import importlib.util
        spec = importlib.util.spec_from_file_location("sub", "/home/dell/Desktop/My_NetFelix/scripts/sync_subtitles.py")
        sub_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sub_mod)

        count = 0
        for v in matches[:6]:
            try:
                sub_mod.process_video_file(v)
                count += 1
            except Exception:
                pass

        refresh_jellyfin()
        return count, f"تم فحص وتوليد الترجمة العربية وتحديث مكتبة Jellyfin لـ <b>{count}</b> ملف لـ: <i>{query}</i> بنجاح!"
    except Exception as e:
        return 0, f"خطأ أثناء توليد الترجمة: {e}"


# ==========================================
# Media & TV Remote Control Integrations
# ==========================================

def control_playback(session_id, action, seek_ticks=None):
    """Send playback control command to Jellyfin."""
    try:
        if action == "pause":
            url = f"{JELLYFIN_URL}/Sessions/{session_id}/Playing/Pause"
        elif action == "unpause":
            url = f"{JELLYFIN_URL}/Sessions/{session_id}/Playing/Unpause"
        elif action == "stop":
            url = f"{JELLYFIN_URL}/Sessions/{session_id}/Playing/Stop"
        elif action == "next_track":
            url = f"{JELLYFIN_URL}/Sessions/{session_id}/Playing/NextTrack"
        elif action == "prev_track":
            url = f"{JELLYFIN_URL}/Sessions/{session_id}/Playing/PreviousTrack"
        elif action in ("seek_back", "seek_fwd") and seek_ticks is not None:
            url = f"{JELLYFIN_URL}/Sessions/{session_id}/Playing/Seek?SeekPositionTicks={seek_ticks}"
        else:
            return False

        req = urllib.request.Request(
            url,
            headers={"Authorization": JELLYFIN_AUTH},
            data=b""
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True
    except Exception as e:
        logger.error(f"Playback control error ({action}): {e}")
        return False


def get_tailscale_status():
    """Returns Tailscale connection status or login URL."""
    try:
        out = subprocess.check_output(["docker", "exec", "netfelix-tailscale", "tailscale", "status"], stderr=subprocess.STDOUT, timeout=5).decode().strip()
        if "Logged out" in out or "https://login.tailscale.com" in out:
            # Extract URL
            m = re.search(r"https://login\.tailscale\.com[^\s]+", out)
            login_url = m.group(0) if m else "https://login.tailscale.com"
            return (
                "🌐 <b>ربط السيرفر بشبكة Tailscale للمشاهدة خارج المنزل:</b>\n\n"
                "سيرفر NetFelix جاهز للاتصال بشبكتك الخاصة.\n"
                f"🔗 <b>رابط التفعيل:</b>\n{login_url}\n\n"
                "<i>اضغط على الرابط أعلاه وسجّل الدخول بحساب Google أو Apple ليصبح السيرفر متاحاً على هاتفك من أي مكان في العالم مجاناً وبدون فتح منافذ في الراوتر!</i>"
            )
        else:
            return f"🌐 <b>سيرفر NetFelix متصل بشبكة Tailscale بنجاح!</b>\n\n<code>{out}</code>"
    except Exception as e:
        return f"تعذر التحقق من Tailscale: {e}"


def add_magnet_torrent(magnet_link):
    """Add magnet link to qBittorrent."""
    try:
        data = urllib.parse.urlencode({"urls": magnet_link}).encode("utf-8")
        req = urllib.request.Request(
            f"{QBITTORRENT_URL}/api/v2/torrents/add",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            res = r.read().decode().strip()
            return True, res
    except Exception as e:
        return False, str(e)


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
    """Trigger library refresh on Jellyfin and AI Media Agent."""
    ok = False
    try:
        jelly_key = os.getenv("JELLYFIN_API_KEY", "")
        req = urllib.request.Request("http://localhost:8096/Library/Refresh", data=b"", headers={"X-Emby-Token": jelly_key})
        with urllib.request.urlopen(req, timeout=8) as r:
            ok = True
    except Exception as e:
        logger.warning(f"Direct Jellyfin refresh notice: {e}")

    try:
        req = urllib.request.Request(f"{AI_SERVICE_URL}/api/refresh", data=b"{}")
        with urllib.request.urlopen(req, timeout=5) as r:
            ok = True
    except Exception:
        pass
    return ok


def download_video_task(chat_id, url):
    """Downloads social media/YouTube video in background via yt-dlp."""
    try:
        send_message(chat_id, "🎬 <b>جاري فحص الرابط وتحميل الفيديو بجودة عالية (1080p)...</b>\n<i>(يتم الحفظ في مجلد التنزيلات على السيرفر)</i>")
        out_dir = "/media/dell/Data1/Downloads/YouTube"
        os.makedirs(out_dir, exist_ok=True)

        title_cmd = ["/home/dell/.local/bin/yt-dlp", "--get-title", "--no-playlist", url]
        title = subprocess.check_output(title_cmd, timeout=20, stderr=subprocess.DEVNULL).decode().strip() or "فيديو جديد"

        dl_cmd = [
            "/home/dell/.local/bin/yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--no-playlist",
            "-o", f"{out_dir}/%(title)s.%(ext)s",
            url
        ]
        subprocess.run(dl_cmd, check=True, timeout=600)

        send_message(
            chat_id,
            f"✅ <b>اكتمل تحميل الفيديو بنجاح!</b>\n\n"
            f"🎬 <b>العنوان:</b> <i>{title}</i>\n"
            f"📁 <b>المسار:</b> <code>/media/dell/Data1/Downloads/YouTube/</code>\n"
            f"🍿 يمكنك مشاهدته الآن عبر <b>FileBrowser</b> على السيرفر!"
        )
    except Exception as e:
        logger.error(f"Video download failed: {e}")
        send_message(chat_id, f"❌ حدث خطأ أثناء تحميل الفيديو: {e}")


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

            session_id = s.get("Id")
            user = s.get("UserName", "مستخدم")
            client = s.get("Client", "تطبيق")
            device = s.get("DeviceName", "جهاز")
            title = item.get("Name", "غير محدد")
            series = item.get("SeriesName")
            if series:
                title = f"{series} - {title}"

            play_method = s.get("PlayMethod", "DirectPlay")
            state = s.get("PlayState", {})
            is_paused = state.get("IsPaused", False)
            pos = state.get("PositionTicks", 0)
            runtime = item.get("RunTimeTicks", 1)
            pct = min(100.0, max(0.0, (pos / runtime) * 100)) if runtime else 0.0

            pos_min = int(pos / (10000000 * 60))
            tot_min = int(runtime / (10000000 * 60))

            playing.append({
                "id": session_id,
                "user": user,
                "client": client,
                "device": device,
                "title": title,
                "play_method": play_method,
                "is_paused": is_paused,
                "pos_ticks": pos,
                "runtime_ticks": runtime,
                "pct": pct,
                "pos_min": pos_min,
                "tot_min": tot_min,
                "supports_remote": s.get("SupportsRemoteControl", True)
            })
        return playing
    except Exception as e:
        logger.error(f"Error fetching now playing: {e}")
        return []


def send_samsung_tv_remote(chat_id):
    """Sends an interactive Samsung TV remote control panel to Telegram chat."""
    import samsung_tv
    info = samsung_tv.get_tv_info()
    p_state = "تعمل الآن ✅" if info.get("power_state") == "on" else "في وضع الاستعداد (مطفية)"

    text = (
        "📺 <b>ريموت تحكم شاشة سامسونج (Samsung 50\" Crystal 4K)</b>\n\n"
        f"🟢 <b>الحالة:</b> {p_state}\n"
        f"📍 <b>العنوان:</b> <code>192.168.1.2</code> | <b>الاقتران:</b> مقترنة ومعتمدة ✅\n\n"
        "<i>اضغط على أي زر للتحكم الفوري بالشاشة:</i>"
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "⏻ باور", "callback_data": "tv:KEY_POWER"}, {"text": "🔌 المصدر", "callback_data": "tv:KEY_SOURCE"}, {"text": "🏠 الرئيسية", "callback_data": "tv:KEY_HOME"}],
            [{"text": "🔊 صوت +", "callback_data": "tv:KEY_VOLUP"}, {"text": "🔇 كتم", "callback_data": "tv:KEY_MUTE"}, {"text": "🔉 صوت -", "callback_data": "tv:KEY_VOLDOWN"}],
            [{"text": "🔺 قناة +", "callback_data": "tv:KEY_CHUP"}, {"text": "⬆️ فوق", "callback_data": "tv:KEY_UP"}, {"text": "🔻 قناة -", "callback_data": "tv:KEY_CHDOWN"}],
            [{"text": "◀️ يسار", "callback_data": "tv:KEY_LEFT"}, {"text": "🔘 OK", "callback_data": "tv:KEY_ENTER"}, {"text": "▶️ يمين", "callback_data": "tv:KEY_RIGHT"}],
            [{"text": "↩️ رجوع", "callback_data": "tv:KEY_RETURN"}, {"text": "⬇️ تحت", "callback_data": "tv:KEY_DOWN"}, {"text": "⚙️ القائمة", "callback_data": "tv:KEY_MENU"}],
            [{"text": "▶️ تشغيل", "callback_data": "tv:KEY_PLAY"}, {"text": "⏸️ إيقاف مؤقت", "callback_data": "tv:KEY_PAUSE"}, {"text": "⏹️ إيقاف", "callback_data": "tv:KEY_STOP"}],
            [{"text": "🍿 Jellyfin", "callback_data": "tvapp:jellyfin"}, {"text": "🔴 YouTube", "callback_data": "tvapp:youtube"}, {"text": "🎬 Netflix", "callback_data": "tvapp:netflix"}],
            [{"text": "🏰 Disney+", "callback_data": "tvapp:disney"}, {"text": "📦 Prime", "callback_data": "tvapp:prime"}, {"text": "🎵 Spotify", "callback_data": "tvapp:spotify"}],
            [{"text": "🌐 فتح ريموت الويب الكامل", "url": "http://192.168.1.15:8092/tv"}]
        ]
    }
    send_message(chat_id, text, reply_markup=keyboard)


def start_cinema_mode(chat_id):
    """Executes 1-click Cinema Mode: Wakes TV, launches Jellyfin, and reports resume status."""
    import samsung_tv
    send_message(chat_id, "🎬 <b>جاري تفعيل وضع السينما...</b>\n1️⃣ إيقاظ شاشة التلفزيون (Wake-on-LAN)\n2️⃣ فتح تطبيق Jellyfin\n3️⃣ تجهيز جلسة المشاهدة...")

    # 1. Wake TV
    samsung_tv.wake_tv()
    time.sleep(2)

    # 2. Launch Jellyfin
    samsung_tv.launch_app("jellyfin")

    # 3. Check resume items
    resume_title = ""
    try:
        users_req = urllib.request.Request(f"{JELLYFIN_URL}/Users", headers={"Authorization": JELLYFIN_AUTH})
        with urllib.request.urlopen(users_req, timeout=4) as u_resp:
            users = json.load(u_resp)
            eslam_user = next((u for u in users if "eslam" in u.get("Name", "").lower()), users[0] if users else None)

        if eslam_user:
            uid = eslam_user["Id"]
            res_req = urllib.request.Request(
                f"{JELLYFIN_URL}/Users/{uid}/Items/Resume?Limit=1",
                headers={"Authorization": JELLYFIN_AUTH}
            )
            with urllib.request.urlopen(res_req, timeout=4) as r_resp:
                res_data = json.load(r_resp)
                items = res_data.get("Items", [])
                if items:
                    it = items[0]
                    series_name = it.get("SeriesName", "")
                    name = it.get("Name", "")
                    resume_title = f"{series_name} - {name}" if series_name else name
    except Exception as e:
        logger.warning(f"Error fetching resume item: {e}")

    msg = (
        "🍿 <b>تم تفعيل وضع السينما بنجاح!</b>\n\n"
        "📺 <b>الشاشة:</b> مستيقظة ومتصلة بالشبكة ✅\n"
        "🍿 <b>التطبيق:</b> تطبيق Jellyfin جاهز على الشاشة ✅\n"
    )
    if resume_title:
        msg += f"🎬 <b>آخر محتوى قيد المتابعة:</b> {resume_title}\n\n"
    msg += "<i>استمتع بالمشاهدة! يمكنك التحكم بالصوت والتشغيل عبر الأزرار أدناه:</i>"

    keyboard = {
        "inline_keyboard": [
            [{"text": "▶️ تشغيل / استئناف", "callback_data": "tv:KEY_PLAY"}, {"text": "⏸️ إيقاف مؤقت", "callback_data": "tv:KEY_PAUSE"}],
            [{"text": "🔊 صوت +", "callback_data": "tv:KEY_VOLUP"}, {"text": "🔉 صوت -", "callback_data": "tv:KEY_VOLDOWN"}, {"text": "🔇 كتم", "callback_data": "tv:KEY_MUTE"}],
            [{"text": "📺 ريموت الشاشة الكامل", "callback_data": "open_tv_remote"}]
        ]
    }
    send_message(chat_id, msg, reply_markup=keyboard)


def handle_storage_clean(chat_id):
    """Executes safe storage cleanup and reports results."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("auto_prune", "/home/dell/Desktop/My_NetFelix/scripts/auto_prune.py")
        prune_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prune_mod)

        free_before = prune_mod.get_disk_free_gb(prune_mod.MEDIA_ROOT)
        temp_mb = prune_mod.prune_stale_temp_files()
        cache_mb = prune_mod.prune_transcode_cache()
        torrents_cleaned = prune_mod.prune_completed_torrents()
        free_after = prune_mod.get_disk_free_gb(prune_mod.MEDIA_ROOT)

        reclaimed = temp_mb + cache_mb
        msg = (
            "🧹 <b>تقرير تنظيف وصيانة التخزين:</b>\n\n"
            f"💾 <b>المساحة الحرة الحالية:</b> {free_after:.1f} GB\n"
            f"🗑️ <b>ملفات الكاش المؤقتة المحذوفة:</b> {reclaimed:.1f} MB\n"
            f"⚡ <b>التورنت المكتمل المنظف:</b> {torrents_cleaned} ملف\n\n"
            "✅ <b>القرص نظيف وبحالة ممتازة ومستقرة!</b>"
        )
        send_message(chat_id, msg, reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        send_message(chat_id, f"❌ حدث خطأ أثناء فحص التخزين: {e}", reply_markup=MAIN_KEYBOARD)


def handle_recommendation(chat_id, query=None):
    """Picks either a local library movie or trending discovery and sends rich card."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("rec", "/home/dell/Desktop/My_NetFelix/scripts/ai_recommendations.py")
        rec_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rec_mod)
        rec = rec_mod.pick_recommendation(query)
        if rec:
            is_library = rec.get("source") == "library"
            badge = "🍿 <b>سهرة اليوم (جاهزة للعرض فوراً من مكتبتك):</b>" if is_library else "🌟 <b>سهرة اليوم من ترشيحات الذكاء الاصطناعي:</b>"
            msg = (
                f"{badge}\n\n"
                f"🎬 <b>{rec.get('title')}</b> ({rec.get('releaseDate')})\n"
                f"⭐ <b>التقييم:</b> {rec.get('rating')}/10\n"
            )
            if rec.get("genres"):
                msg += f"🎭 <b>التصنيف:</b> {rec.get('genres')}\n\n"
            else:
                msg += "\n"
            msg += f"📝 <i>{rec.get('overview')}</i>\n"

            inline_rows = []
            if is_library:
                inline_rows.append([
                    {"text": "▶️ تشغيل فوري على التلفزيون", "callback_data": f"play_item:{rec.get('id')}"}
                ])
                inline_rows.append([
                    {"text": "📺 ريموت الشاشة", "callback_data": "open_tv_remote"},
                    {"text": "🎲 اقتراح آخر", "callback_data": "reroll_rec"}
                ])
            else:
                inline_rows.append([
                    {"text": f"📥 تحميل {rec.get('title')}", "callback_data": f"req:movie:{rec.get('tmdbId')}:{rec.get('title')}"},
                    {"text": "🎲 اقتراح آخر", "callback_data": "reroll_rec"}
                ])

            poster = rec.get("posterPath")
            if poster:
                send_photo(chat_id, poster, caption=msg, reply_markup={"inline_keyboard": inline_rows})
            else:
                send_message(chat_id, msg, reply_markup={"inline_keyboard": inline_rows})
        else:
            send_message(chat_id, "تعذر إنشاء الاقتراح حالياً.", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.error(f"Error in recommendation: {e}")
        send_message(chat_id, f"خطأ في جلب الاقتراح: {e}", reply_markup=MAIN_KEYBOARD)


def handle_callback_query(cq):
    """Handle inline button callback clicks."""
    cq_id = cq["id"]
    from_user = cq.get("from", {})
    user_id = str(from_user.get("id", ""))
    chat_id = cq.get("message", {}).get("chat", {}).get("id")
    data = cq.get("data", "")

    logger.info(f"Callback query from {user_id}: {data}")

    # Samsung TV App Launch Callback
    if data.startswith("tvapp:"):
        app_name = data.split("tvapp:")[1]
        import samsung_tv
        res = samsung_tv.launch_app(app_name)
        resp_text = res.get("message", "✅ تم تشغيل التطبيق") if res.get("success") else res.get("error", "❌ تعذر تشغيل التطبيق")
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": resp_text
        })
        return

    # Laptop Physical Screen Power Control Callback
    if data.startswith("screen:"):
        action = data.split("screen:")[1]
        import subprocess
        subprocess.run(["/home/dell/Desktop/My_NetFelix/scripts/screen_control.sh", action])
        st_text = "تم إطفاء شاشة اللابتوب 🌑" if action == "off" else "تم تشغيل شاشة اللابتوب 💡"
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": st_text
        })
        send_message(chat_id, f"✅ <b>{st_text}</b>\n(الاتصال عن بُعد مستمر ويعمل بدون انقطاع)", reply_markup=MAIN_KEYBOARD)
        return

    # Samsung TV Direct Hardware Remote Callback
    if data.startswith("tv:"):
        key = data.split("tv:")[1]
        import samsung_tv
        res = samsung_tv.send_key(key)
        resp_text = f"✅ تم إرسال {key}" if res.get("success") else "❌ تعذر الإرسال"
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": resp_text
        })
        return

    # TV Remote Control Callback
    if data.startswith("ctrl:"):
        parts = data.split(":")
        action = parts[1]
        session_id = parts[2]
        seek_ticks = int(parts[3]) if len(parts) > 3 else None

        ok = control_playback(session_id, action, seek_ticks=seek_ticks)
        msg_text = "✅ تم إرسال أمر التحكم للشاشة!" if ok else "❌ تعذر التحكم بالشاشة حالياً."
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": msg_text
        })
        return

    # Open full Samsung TV hardware remote
    if data == "open_tv_remote":
        send_samsung_tv_remote(chat_id)
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": "📺 تم فتح ريموت التلفزيون الكامل"
        })
        return

    # Play specific item on TV
    if data.startswith("play_item:"):
        item_id = data.split("play_item:")[1]
        import samsung_tv
        samsung_tv.wake_tv()
        samsung_tv.launch_app("jellyfin")
        sessions = get_now_playing()
        played = False
        for s in sessions:
            if "samsung" in s.get("device", "").lower() or "tv" in s.get("device", "").lower():
                try:
                    p_url = f"{JELLYFIN_URL}/Sessions/{s['id']}/Playing?ItemIds={item_id}"
                    p_req = urllib.request.Request(p_url, headers={"Authorization": JELLYFIN_AUTH}, data=b"")
                    urllib.request.urlopen(p_req, timeout=5)
                    played = True
                    break
                except Exception:
                    pass
        res_text = "🍿 تم إرسال أمر التشغيل للشاشة!" if played else "📺 تم فتح تطبيق Jellyfin على الشاشة!"
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": res_text
        })
        send_message(chat_id, f"🎬 <b>جاري العرض على التلفزيون...</b>\n{res_text}")
        return

    # Reroll recommendation
    if data == "reroll_rec":
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": "🎲 جاري اختيار سهرة جديدة..."
        })
        handle_recommendation(chat_id)
        return

    # Device Web Activity Callback
    if data.startswith("act:"):
        target_ip = data.split(":")[1]
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": f"🔍 جاري فحص نشاط {target_ip}..."
        })
        rep = get_device_activity(target_ip)
        send_message(chat_id, rep)
        return

    # Codex Actions Callback
    if data.startswith("codex:"):
        action = data.split("codex:")[1]
        if action == "new_window":
            telegram_api("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "🖥️ جاري فتح نافذة جديدة..."
            })
            open_codex_terminal(chat_id, force_new=True)
            return

        elif action == "chat_mode":
            telegram_api("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "💬 تم الانتقال لوضع محادثة Codex"
            })
            set_codex_mode(chat_id, active=True, continue_conv=True)
            codex_welcome = (
                "⚡ <b>تم تفعيل محادثة OpenAI Codex (--yolo)!</b>\n\n"
                "📂 <b>المسار النشط:</b> <code>/home/dell/Desktop/My_NetFelix</code>\n"
                "🛡️ <b>الصلاحيات:</b> <code>--yolo</code> (تنفيذ وتعديل كامل وتلقائي)\n\n"
                "💬 <i>أنت الآن في محادثة مباشرة مع Codex.</i>\n"
                "أرسل أي طلب أو كود برمجياً وسيتم تنفيذه وموافاتك به فوراً.\n\n"
                "• اضغط <b>🆕 جلسة جديدة</b> لبدء محادثة جديدة بدون سياق سابق.\n"
                "• اضغط <b>🔄 متابعة الجلسة</b> للاستمرار في سياق المحادثة الحالية.\n"
                "• اضغط <b>🖥️ فتح في Terminal</b> للفتح على شاشة السيرفر.\n"
                "• اضغط <b>❌ إنهاء محادثة Codex</b> للعودة للقائمة الرئيسية."
            )
            send_message(chat_id, codex_welcome, reply_markup=CODEX_KEYBOARD)
            return

        elif action == "status":
            pids = get_running_codex_pids()
            disp = find_active_display()
            sess = load_codex_sessions().get(str(chat_id), {})
            sid = sess.get("session_id") or "لا توجد جلسة نشطة بعد"
            telegram_api("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": f"📊 العمليات: {len(pids)}"
            })
            status_text = (
                "📊 <b>حالة بيئة Codex (--yolo):</b>\n\n"
                f"🖥️ <b>عمليات Terminal النشطة:</b> <code>{len(pids)}</code> (PIDs: {', '.join(str(p) for p in pids) or 'لا يوجد'})\n"
                f"📺 <b>الشاشة النشطة:</b> <code>{disp}</code>\n"
                f"💬 <b>معرف الجلسة (Session ID):</b> <code>{sid}</code>\n"
                f"📂 <b>مسار المشروع:</b> <code>/home/dell/Desktop/My_NetFelix</code>"
            )
            send_message(chat_id, status_text)
            return

        elif action == "kill":
            pids = get_running_codex_pids()
            for p in pids:
                try:
                    os.kill(p, 9)
                except Exception:
                    pass
            lock_dir = Path("/home/dell/.codex/thread-writer-locks")
            if lock_dir.exists():
                for lf in lock_dir.glob("*.lock"):
                    try:
                        lf.unlink()
                    except Exception:
                        pass
            telegram_api("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "🛑 تم إيقاف جلسات Codex"
            })
            send_message(chat_id, "🛑 <b>تم إنهاء جميع عمليات Codex وتحرير الأقفال بنجاح.</b>")
            return

    # Download Request Callback
    telegram_api("answerCallbackQuery", {
        "callback_query_id": cq_id,
        "text": "🚀 جاري معالجة الطلب بالذكاء الاصطناعي..."
    })

    if data.startswith("req:"):
        parts = data.split(":", 3)
        if len(parts) >= 4:
            mode = parts[1]
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

    # Check security whitelist
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        send_message(
            chat_id,
            f"⚠️ عذراً {first_name}، هذا البوت خاص بسيرفر NetFelix المنزلي.\n"
            f"معرّف حسابك (User ID): <code>{user_id}</code>\n"
            f"يرجى السماح لك في ملف <code>.env</code> على السيرفر."
        )
        return

    register_subscriber(chat_id)

    # 1. Voice Note / Audio Message Handling
    voice_obj = msg.get("voice") or msg.get("audio")
    if voice_obj and voice_obj.get("file_id"):
        send_message(chat_id, "🎙️ <i>جاري الاستماع للرسالة الصوتية وتحليل الطلب بالذكاء الاصطناعي...</i>")
        transcription = transcribe_voice(voice_obj["file_id"])
        if not transcription:
            send_message(chat_id, "❌ لم أتمكن من التعرف على الصوت بدقة. يرجى التحدث بوضوح أو كتابة الاسم نصياً.")
            return

        send_message(chat_id, f"🎙️ <b>تم التعرف على الصوت:</b> <i>\"{transcription}\"</i>\n🔍 جاري البحث والمتابعة...")
        text = transcription

    # 2. Photo / Image Attachment Handling
    photo_list = msg.get("photo")
    doc_obj = msg.get("document")
    caption = (msg.get("caption") or "").strip()

    if photo_list or (doc_obj and doc_obj.get("mime_type", "").startswith("image/")):
        file_id = photo_list[-1]["file_id"] if photo_list else doc_obj["file_id"]
        saved_photo_path = str(CONFIG_DIR / "telegram_received_photo.jpg")
        send_message(chat_id, "📸 <i>تم استلام الصورة! جاري فحص التصميم وتطبيقه على شاشة التلفزيون بالذكاء الاصطناعي...</i>")
        if download_telegram_file(file_id, saved_photo_path):
            logger.info(f"Successfully downloaded photo to {saved_photo_path}")
            if is_agy_mode(chat_id):
                prompt = (
                    f"The user has sent a design reference image in Telegram, saved at: {saved_photo_path}. "
                    f"Caption: '{caption}'. Please inspect this image file, analyze its UI layout, colors, "
                    f"components, and style, and build/adapt the TV Dashboard GUI to match this design exactly."
                )
                sessions = load_agy_sessions()
                continue_conv = sessions.get(str(chat_id), {}).get("continue_conv", True)
                threading.Thread(target=handle_agy_task, args=(chat_id, prompt, continue_conv), daemon=True).start()
                return
            elif is_codex_mode(chat_id):
                prompt = (
                    f"The user has sent a photo in Telegram, saved at: {saved_photo_path}. "
                    f"Caption: '{caption}'. Please inspect this file and execute the requested task."
                )
                sessions = load_codex_sessions()
                continue_conv = sessions.get(str(chat_id), {}).get("continue_conv", True)
                threading.Thread(target=handle_codex_task, args=(chat_id, prompt, continue_conv), daemon=True).start()
                return
            else:
                send_message(chat_id, "✅ تم حفظ الصورة على السيرفر بنجاح.")
                return
        else:
            send_message(chat_id, "❌ تعذر تحميل الصورة من خوادم تيليجرام.")
            return

    if not chat_id or not text:
        return

    logger.info(f"Incoming message from {first_name} (User ID: {user_id}, Chat: {chat_id}): '{text}'")

    # Check magnet link
    if "magnet:?xt=" in text:
        magnet = re.search(r"magnet:\?xt=[^\s]+", text)
        if magnet:
            m_link = magnet.group(0)
            ok, res = add_magnet_torrent(m_link)
            if ok:
                send_message(
                    chat_id,
                    "🧲 <b>تم استلام رابط الماجنت بنجاح!</b>\n"
                    "📥 تم تمريره إلى qBittorrent وبدأ التنزيل فوراً.\n"
                    "🍿 سأرسل لك إشعاراً فور اكتمال التنزيل وجاهزيته في Jellyfin."
                )
            else:
                send_message(chat_id, f"❌ تعذر إضافة رابط الماجنت: {res}")
            return

    # Check for Video URLs (YouTube, TikTok, Instagram, Twitter/X, Facebook)
    video_url_match = re.search(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com|instagram\.com|twitter\.com|x\.com|facebook\.com|fb\.watch)[^\s]+", text)
    if video_url_match:
        target_url = video_url_match.group(0)
        threading.Thread(target=download_video_task, args=(chat_id, target_url), daemon=True).start()
        return

    # /start
    if text.startswith("/start"):
        welcome = (
            f"👋 <b>أهلاً بك يا {first_name} في مساعد NetFelix الذكي!</b>\n\n"
            f"أنا نظامك الترفيهي والأمني المتكامل لإدارة السيرفر والشبكة والتحميلات 🌍\n\n"
            f"⚡ <b>أبرز الخدمات المتاحة (يمكنك أيضاً استخدام الأزرار بالأسفل 👇):</b>\n"
            f"• ⚡ <code>/codex</code> أو <b>⚡ فتح Codex --yolo</b> - تشغيل بيئة Codex الذكية بصلاحيات كاملة في Terminal أو المحادثة المباشرة هنا.\n"
            f"• 🤖 <code>/agy</code> - محادثة Antigravity CLI الذكية للبرمجة وإدارة المشروع مباشرة.\n"
            f"• 🎙️ <b>البحث بالصوت:</b> أرسل رسالة صوتية (Voice Note) مباشرة باسم أي عمل!\n"
            f"• 🎬 <b>تحميل الفيديوهات:</b> أرسل أي رابط من YouTube أو TikTok أو Instagram وسيتم تحميله فوراً!\n"
            f"• 📱 <code>/devices</code> - فحص أجهزة الواي فاي وكشف المتطفلين.\n"
            f"• 🍿 <code>/nowplaying</code> - ريموت كنترول للشاشات والتحكم بالمشاهدة الحالية.\n"
            f"• 📝 <code>/subtitles &lt;الاسم&gt;</code> - توليد وترجمة وتصليح الترجمة العربية فوراً.\n"
            f"• 📊 <code>/server</code> - فحص حرارة اللابتوب، الشاحن، الرام، ومساحة التخزين.\n"
            f"• 🌐 <code>/tailscale</code> - ربط السيرفر للمشاهدة خارج المنزل عبر 4G/5G.\n"
            f"• 🔍 <code>/search &lt;الاسم&gt;</code> - بحث تفاعلي مع البوستر وأزرار التحميل.\n"
            f"• ⚡ <code>/status</code> - مراقبة سرعة التنزيلات والتورنت الحية.\n"
            f"• 💡 <code>/recommend</code> - اقتراح سهرة اليوم بالذكاء الاصطناعي.\n\n"
            f"💡 <i>يمكنك إرسال أي رابط Magnet مباشرة، أو كتابة اسم أي فيلم وسأقوم بتحميله تلقائياً!</i>"
        )
        send_message(chat_id, welcome, reply_markup=MAIN_KEYBOARD)
        return

    # 2. AGY Command & Mode Handlers
    if text == "🤖 محادثة AGY" or text == "/agy" or text == "/antigravity":
        set_codex_mode(chat_id, active=False)
        set_agy_mode(chat_id, active=True, continue_conv=True)
        agy_welcome = (
            "🤖 <b>تم تفعيل محادثة Antigravity CLI (AGY)!</b>\n\n"
            "📂 <b>المسار النشط:</b> <code>/home/dell/Desktop/My_NetFelix</code>\n"
            "⚡ <b>الصلاحيات:</b> <code>--dangerously-skip-permissions</code> (تنفيذ فوري تلقائي)\n\n"
            "💬 <i>أنت الآن في محادثة مباشرة مع Antigravity داخل مشروعك.</i>\n"
            "أي رسالة نصية أو تسجيل صوتي ترسله الآن سيُرسل كأمر لـ agy، وسيقوم بفحص الملفات، كتابة الكود، وتشغيل الأوامر وموافاتها لك فوراً!\n\n"
            "• اكتب أي سؤال برمجي أو طلب للنظام.\n"
            "• اضغط <b>🆕 جلسة جديدة</b> لبدء محادثة جديدة بدون سياق سابق.\n"
            "• اضغط <b>🔄 متابعة الجلسة</b> للاستمرار في سياق المحادثة الحالية.\n"
            "• اضغط <b>❌ إنهاء محادثة AGY</b> للعودة للقائمة العادية."
        )
        send_message(chat_id, agy_welcome, reply_markup=AGY_KEYBOARD)
        return

    if text.startswith("/agy ") or text.startswith("/antigravity "):
        prompt = text.split(" ", 1)[1].strip()
        if prompt:
            threading.Thread(target=handle_agy_task, args=(chat_id, prompt, True), daemon=True).start()
        return

    if text in ["❌ إنهاء محادثة AGY", "/exit_agy"]:
        if is_agy_mode(chat_id):
            set_agy_mode(chat_id, active=False)
            send_message(
                chat_id,
                "👋 <b>تم إنهاء محادثة AGY بنجاح.</b>\nالعودة إلى قائمة NetFelix الرئيسية.",
                reply_markup=MAIN_KEYBOARD
            )
            return

    if is_agy_mode(chat_id) and text in ["🆕 جلسة جديدة", "🆕 جلسة جديدة (New Chat)"]:
        set_agy_mode(chat_id, active=True, continue_conv=False)
        send_message(
            chat_id,
            "🆕 <b>تم بدء جلسة AGY جديدة ونظيفة!</b>\nأرسل رسالتك القادمة وسيبدأ Antigravity محادثة جديدة بدون سياق سابق.",
            reply_markup=AGY_KEYBOARD
        )
        return

    if is_agy_mode(chat_id) and text in ["🔄 متابعة الجلسة", "🔄 متابعة الجلسة (Continue)"]:
        set_agy_mode(chat_id, active=True, continue_conv=True)
        send_message(
            chat_id,
            "🔄 <b>وضع متابعة الجلسة مفعّل!</b>\nAntigravity سيتذكر سياق الأوامر السابقة في هذا المشروع.",
            reply_markup=AGY_KEYBOARD
        )
        return

    # 3. OpenAI Codex (--yolo) Command & Mode Handlers
    if text in ["⚡ فتح Codex --yolo", "open codex --yolo", "codex --yolo", "/opencodex", "/open_codex", "/codex_yolo", "افتح codex", "افتح كودكس"]:
        open_codex_terminal(chat_id)
        return

    if text in ["🤖 محادثة Codex", "💬 محادثة Codex", "/codex"]:
        set_agy_mode(chat_id, active=False)
        set_codex_mode(chat_id, active=True, continue_conv=True)
        codex_welcome = (
            "⚡ <b>تم تفعيل محادثة OpenAI Codex (--yolo)!</b>\n\n"
            "📂 <b>المسار النشط:</b> <code>/home/dell/Desktop/My_NetFelix</code>\n"
            "🛡️ <b>الصلاحيات:</b> <code>--yolo</code> (تنفيذ وتعديل كامل وتلقائي بدون حواجز)\n\n"
            "💬 <i>أنت الآن في محادثة مباشرة مع Codex داخل مشروعك.</i>\n"
            "أي رسالة نصية أو تسجيل صوتي ترسله الآن سيُنفذ فوراً بواسطة Codex!\n\n"
            "• اكتب أي سؤال برمجي أو طلب للنظام.\n"
            "• اضغط <b>🆕 جلسة جديدة</b> لبدء محادثة جديدة بدون سياق سابق.\n"
            "• اضغط <b>🔄 متابعة الجلسة</b> للاستمرار في سياق المحادثة الحالية.\n"
            "• اضغط <b>🖥️ فتح في Terminal</b> لفتح أو إظهار نافذة على شاشة اللابتوب.\n"
            "• اضغط <b>❌ إنهاء محادثة Codex</b> للعودة للقائمة الرئيسية."
        )
        send_message(chat_id, codex_welcome, reply_markup=CODEX_KEYBOARD)
        return

    if text.startswith("/codex "):
        prompt = text.split(" ", 1)[1].strip()
        if prompt:
            threading.Thread(target=handle_codex_task, args=(chat_id, prompt, True), daemon=True).start()
        return

    if text in ["❌ إنهاء محادثة Codex", "/exit_codex", "/exit", "خروج", "انهاء", "إنهاء"]:
        if is_codex_mode(chat_id):
            set_codex_mode(chat_id, active=False)
            send_message(
                chat_id,
                "👋 <b>تم إنهاء محادثة Codex بنجاح.</b>\nالعودة إلى قائمة NetFelix الرئيسية.",
                reply_markup=MAIN_KEYBOARD
            )
            return
        elif is_agy_mode(chat_id):
            set_agy_mode(chat_id, active=False)
            send_message(
                chat_id,
                "👋 <b>تم إنهاء محادثة AGY بنجاح.</b>\nالعودة إلى قائمة NetFelix الرئيسية.",
                reply_markup=MAIN_KEYBOARD
            )
            return

    if is_codex_mode(chat_id) and text in ["🆕 جلسة جديدة", "🆕 جلسة جديدة (New Chat)"]:
        set_codex_mode(chat_id, active=True, continue_conv=False)
        send_message(
            chat_id,
            "🆕 <b>تم بدء جلسة Codex جديدة ونظيفة!</b>\nأرسل رسالتك القادمة وسيبدأ Codex محادثة جديدة بدون سياق سابق.",
            reply_markup=CODEX_KEYBOARD
        )
        return

    if is_codex_mode(chat_id) and text in ["🔄 متابعة الجلسة", "🔄 متابعة الجلسة (Continue)"]:
        set_codex_mode(chat_id, active=True, continue_conv=True)
        send_message(
            chat_id,
            "🔄 <b>وضع متابعة جلسة Codex مفعّل!</b>\nسيتذكر Codex سياق الأوامر السابقة في هذا المشروع.",
            reply_markup=CODEX_KEYBOARD
        )
        return

    if text in ["🖥️ فتح في Terminal"]:
        open_codex_terminal(chat_id)
        return

    # System Buttons & Commands Check
    system_buttons = [
        "📱 الأجهزة المتصلة", "📺 ريموت الشاشة", "🍿 شاشات العرض", "🎬 وضع السينما",
        "💡 سهرة اليوم", "🧹 تنظيف المساحة", "📊 حالة السيرفر", "⚡ سرعة التورنت",
        "🔄 فحص المكتبة", "🌐 ريموت Tailscale", "⚡ فتح Codex --yolo", "🤖 محادثة AGY",
        "🖥️ فتح في Terminal", "❌ إنهاء محادثة AGY", "❌ إنهاء محادثة Codex"
    ]
    is_system_cmd = text.startswith("/") and any(text.startswith(c) for c in [
        "/devices", "/tv", "/remote", "/activity", "/inspect",
        "/server", "/health", "/tailscale", "/subtitles", "/subs",
        "/name", "/nowplaying", "/search", "/status", "/history",
        "/refresh", "/recommend", "/match", "/cinema", "/clean",
        "/codex", "/opencodex", "/open_codex", "/codex_yolo"
    ])

    # If in AGY Mode and not an explicit media/utility button, forward prompt to AGY
    if is_agy_mode(chat_id) and not is_system_cmd and text not in system_buttons:
        sessions = load_agy_sessions()
        continue_conv = sessions.get(str(chat_id), {}).get("continue_conv", True)
        if not continue_conv:
            set_agy_mode(chat_id, active=True, continue_conv=True)
        threading.Thread(target=handle_agy_task, args=(chat_id, text, continue_conv), daemon=True).start()
        return

    # If in Codex Mode and not an explicit media/utility button, forward prompt to Codex
    if is_codex_mode(chat_id) and not is_system_cmd and text not in system_buttons:
        sessions = load_codex_sessions()
        continue_conv = sessions.get(str(chat_id), {}).get("continue_conv", True)
        if not continue_conv:
            set_codex_mode(chat_id, active=True, continue_conv=True)
        threading.Thread(target=handle_codex_task, args=(chat_id, text, continue_conv), daemon=True).start()
        return

    # /devices or button
    if text.startswith("/devices") or text == "📱 الأجهزة المتصلة":
        send_message(chat_id, "📡 <b>جاري فحص شبكة الواي فاي وكشف الأجهزة المتصلة...</b>\n<i>(يستغرق 3 إلى 4 ثوانٍ)</i>")
        devs = scan_network_devices()
        report, keyboard = format_devices_report(devs)
        send_message(chat_id, report, reply_markup=keyboard or MAIN_KEYBOARD)
        return

    # /tv or /remote or button
    if text.startswith("/tv") or text.startswith("/remote") or text == "📺 ريموت الشاشة":
        send_samsung_tv_remote(chat_id)
        return

    # /activity or /inspect
    if text.startswith("/activity") or text.startswith("/inspect"):
        parts = text.split()
        if len(parts) > 1:
            target_ip = parts[1].strip()
            rep = get_device_activity(target_ip)
            send_message(chat_id, rep)
        else:
            send_message(
                chat_id,
                "💡 <b>لمعرفة نشاط أي جهاز وماذا يتصفح:</b>\n"
                "اكتب: <code>/activity 192.168.1.X</code>\n"
                "أو اضغط زر <b>📱 الأجهزة المتصلة</b> واضغط على زر فحص النشاط مباشرة!"
            )
        return

    # /screenoff or /screenon or /screen (Physical Laptop Screen Control)
    if text in ["/screenoff", "إطفاء الشاشة", "اطفاء الشاشة"]:
        import subprocess
        subprocess.run(["/home/dell/Desktop/My_NetFelix/scripts/screen_control.sh", "off"])
        send_message(
            chat_id,
            "🌑 <b>تم إطفاء شاشة اللابتوب الفيزيائية بنجاح!</b>\n"
            "تم خفض استهلاك طاقة الشاشة إلى الصفر (0 Watt)، وجلستك عن بُعد مستمرة وتعمل بدون أي تأثير.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if text in ["/screenon", "تشغيل الشاشة"]:
        import subprocess
        subprocess.run(["/home/dell/Desktop/My_NetFelix/scripts/screen_control.sh", "on"])
        send_message(
            chat_id,
            "💡 <b>تم تشغيل شاشة اللابتوب الفيزيائية بنجاح!</b>",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if text in ["/screen", "/display", "شاشة اللابتوب"]:
        import subprocess
        res = subprocess.run(["/home/dell/Desktop/My_NetFelix/scripts/screen_control.sh", "status"], capture_output=True, text=True)
        st = res.stdout.strip()
        state_str = "شغالة 💡" if st == "ON" else "مطفأة 🌑 (وضع توفير الطاقة)"
        inline_kb = {
            "inline_keyboard": [
                [
                    {"text": "🌑 إطفاء شاشة اللابتوب", "callback_data": "screen:off"},
                    {"text": "💡 تشغيل شاشة اللابتوب", "callback_data": "screen:on"}
                ]
            ]
        }
        send_message(
            chat_id,
            f"🖥️ <b>حالة شاشة اللابتوب الفيزيائية:</b> {state_str}\n\n"
            "يمكنك التحكم في تشغيلها أو إطفائها لتوفير استهلاك الكهرباء أثناء اتصالك عن بُعد:",
            reply_markup=inline_kb
        )
        return

    # /server or /health or button
    if text.startswith("/server") or text.startswith("/health") or text == "📊 حالة السيرفر":
        report = format_server_report()
        send_message(chat_id, report, reply_markup=MAIN_KEYBOARD)
        return

    # /tailscale or button
    if text.startswith("/tailscale") or text == "🌐 ريموت Tailscale":
        st = get_tailscale_status()
        send_message(chat_id, st, reply_markup=MAIN_KEYBOARD)
        return

    # /subtitles
    if text.startswith("/subtitles") or text.startswith("/subs") or text == "📝 ترجمة فورية":
        query = text.replace("/subtitles", "").replace("/subs", "").replace("📝 ترجمة فورية", "").strip()
        if not query:
            send_message(
                chat_id,
                "💡 <b>طريقة استخدام الترجمة الفورية:</b>\n"
                "اكتب: <code>/subtitles اسم الفيلم أو المسلسل</code>\n"
                "مثال: <code>/subtitles Inception</code>\n\n"
                "يقوم البوت بالبحث في مكتبتك، استخراج الترجمة وترجمتها للعربية UTF-8 وتحديث Jellyfin فوراً!",
                reply_markup=MAIN_KEYBOARD
            )
            return

        send_message(chat_id, f"📝 <b>جاري فحص وتوليد الترجمة العربية لـ:</b> <i>{query}</i>...")
        count, msg_res = sync_subtitles_for_query(query)
        send_message(chat_id, f"🍿 {msg_res}", reply_markup=MAIN_KEYBOARD)
        return

    # /name <IP/MAC> <Custom Name>
    if text.startswith("/name"):
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            send_message(chat_id, "💡 <b>طريقة تسمية الجهاز:</b>\n<code>/name 192.168.1.5 هاتف إسلام</code>\nأو باستخدام الماك أدرس:\n<code>/name DE:1B:A4:9F:F5:93 هاتف إسلام</code>")
            return

        target = parts[1].strip()
        custom_alias = parts[2].strip()
        known = load_known_devices()

        matched_mac = None
        if target.upper() in known:
            matched_mac = target.upper()
        else:
            for mac, info in known.items():
                if info.get("ip") == target:
                    matched_mac = mac
                    break

        if matched_mac:
            known[matched_mac]["alias"] = custom_alias
            save_known_devices(known)
            send_message(
                chat_id,
                f"✅ <b>تم حفظ اسم الجهاز بنجاح!</b>\n"
                f"🏷️ الجهاز: <code>{matched_mac}</code> ({known[matched_mac].get('ip')})\n"
                f"📱 الاسم الجديد: <b>{custom_alias}</b>\n\n"
                f"سيظهر هذا الاسم في جميع تقارير الشبكة والتنبيهات المستقبلية.",
                reply_markup=MAIN_KEYBOARD
            )
        else:
            send_message(
                chat_id,
                f"❌ لم يتم العثور على جهاز بالمعرف: <code>{target}</code> في السجل.\n"
                f"قم بعمل <code>/devices</code> أولاً للتعرف عليه."
            )
        return

    # /nowplaying with interactive TV Remote Control
    if text.startswith("/nowplaying") or text == "🍿 شاشات العرض":
        sessions = get_now_playing()
        if not sessions:
            send_message(chat_id, "💤 <b>لا يوجد أي شخص يشاهد محتوى على السيرفر حالياً.</b>\nالشاشات في وضع الانتظار.", reply_markup=MAIN_KEYBOARD)
            return

        send_message(chat_id, f"🍿 <b>شاشات العرض النشطة في المنزل ({len(sessions)}):</b>")
        for s in sessions:
            p_icon = "⚡ Direct Play" if "direct" in s["play_method"].lower() else "🔄 Transcoding"
            state_label = "⏸️ متوقف مؤقتاً" if s["is_paused"] else "▶️ قيد التشغيل"
            caption = (
                f"👤 <b>{s['user']}</b> ({s['client']} على {s['device']})\n"
                f"🎬 <b>المحتوى:</b> {s['title']}\n"
                f"📊 <b>التقدم:</b> {s['pct']:.1f}% ({s['pos_min']}/{s['tot_min']} دقيقة) | {state_label}\n"
                f"📡 <b>نوع البث:</b> {p_icon}\n"
                f"🕹️ <i>استخدم الأزرار أدناه للتحكم بالشاشة:</i>"
            )

            # Build Remote Control Buttons
            sess_id = s["id"]
            pos_ticks = s["pos_ticks"]
            # 30 seconds = 300,000,000 ticks
            seek_back = max(0, pos_ticks - 300000000)
            seek_fwd = pos_ticks + 300000000

            toggle_text = "▶️ استئناف" if s["is_paused"] else "⏸️ إيقاف مؤقت"
            toggle_action = "unpause" if s["is_paused"] else "pause"

            remote_buttons = [
                [
                    {"text": toggle_text, "callback_data": f"ctrl:{toggle_action}:{sess_id}"},
                    {"text": "⏹️ إنهاء", "callback_data": f"ctrl:stop:{sess_id}"}
                ],
                [
                    {"text": "⏪ ارجع 30ث", "callback_data": f"ctrl:seek_back:{sess_id}:{seek_back}"},
                    {"text": "⏩ قدم 30ث", "callback_data": f"ctrl:seek_fwd:{sess_id}:{seek_fwd}"}
                ],
                [
                    {"text": "⏮️ الحلقة السابقة", "callback_data": f"ctrl:prev_track:{sess_id}"},
                    {"text": "⏭️ الحلقة التالية", "callback_data": f"ctrl:next_track:{sess_id}"}
                ],
                [
                    {"text": "📺 ريموت التلفزيون الكامل", "callback_data": "open_tv_remote"}
                ]
            ]
            keyboard = {"inline_keyboard": remote_buttons}
            send_message(chat_id, caption, reply_markup=keyboard)
        return

    # /search
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

    # /status or button
    if text.startswith("/status") or text == "⚡ سرعة التورنت":
        st = get_ai_status()
        torrents = get_torrent_downloads()
        active = st.get("active_job") if isinstance(st, dict) else None
        pending = st.get("pending_count", 0) if isinstance(st, dict) else 0

        if not active and pending == 0 and not torrents:
            send_message(chat_id, "💤 <b>لا توجد تحميلات نشطة حالياً.</b>\nالمحرك جاهز وفي انتظار طلباتك!", reply_markup=MAIN_KEYBOARD)
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

        send_message(chat_id, "\n".join(status_lines), reply_markup=MAIN_KEYBOARD)
        return

    # /history
    if text.startswith("/history"):
        hist = get_ai_history()
        items = (hist.get("history") or [])[-5:]
        if not items:
            send_message(chat_id, "📋 لا توجد عمليات سابقة بعد.", reply_markup=MAIN_KEYBOARD)
            return

        lines = ["📋 <b>آخر ما تم تحميله في NetFelix:</b>\n"]
        for it in reversed(items):
            status_icon = "✅" if it.get("status") == "COMPLETED" else "⏳"
            lines.append(f"{status_icon} <b>{it.get('title') or it.get('query')}</b> ({it.get('source', 'AI')})")
        send_message(chat_id, "\n".join(lines), reply_markup=MAIN_KEYBOARD)
        return

    # /refresh or button
    if text.startswith("/refresh") or text == "🔄 فحص المكتبة":
        if refresh_jellyfin():
            send_message(chat_id, "🔄 <b>تم إرسال أمر فحص وتحديث مكتبة Jellyfin بنجاح!</b>", reply_markup=MAIN_KEYBOARD)
        else:
            send_message(chat_id, "❌ تعذر إرسال أمر التحديث.", reply_markup=MAIN_KEYBOARD)
        return

    # /cinema or button
    if text.startswith("/cinema") or text == "🎬 وضع السينما":
        start_cinema_mode(chat_id)
        return

    # /clean or button
    if text.startswith("/clean") or text == "🧹 تنظيف المساحة":
        handle_storage_clean(chat_id)
        return

    # /recommend or /match or button
    if text.startswith("/recommend") or text.startswith("/match") or text == "💡 سهرة اليوم":
        parts = text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 and not text.startswith("💡") else None
        handle_recommendation(chat_id, query=query)
        return

    # Natural Language / Query Request
    is_tv = any(w in text.lower() for w in ["مسلسل", "series", "season", "حلقات", "حلقة", "انمي", "anime", "موسم"])
    media_type = "tv" if is_tv else "movie"

    clean_query = re.sub(r"^(مسلسل|سلسلة|حلقات|فيلم|series|season)\s+", "", text, flags=re.IGNORECASE).strip()
    clean_query = clean_query.replace("بالمصري", "").replace("مدبلج", "").strip()
    dub_mode = "egyptian" if ("بالمصري" in text or "مدبلج" in text) else "auto"

    type_label = "مسلسل" if is_tv else "فيلم"
    send_message(chat_id, f"🔍 <b>جاري البحث والتحميل لـ {type_label}:</b> <i>{clean_query}</i> بالذكاء الاصطناعي...", reply_markup=MAIN_KEYBOARD)

    res = request_download(clean_query, media_type=media_type, dub_mode=dub_mode)
    if "error" in res:
        send_message(chat_id, f"❌ حدث خطأ أثناء إرسال الطلب: {res['error']}", reply_markup=MAIN_KEYBOARD)
    else:
        send_message(
            chat_id,
            f"🚀 <b>{res.get('message', 'تم استلام الطلب بنجاح!')}</b>\n"
            f"سأقوم بإعلامك فور اكتمال التنزيل وأرشفته في Jellyfin.",
            reply_markup=MAIN_KEYBOARD
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

    # Test token & register bot menu
    me = telegram_api("getMe")
    if me and me.get("ok"):
        bot_user = me["result"]["username"]
        logger.info(f"Bot connected successfully as @{bot_user}")
        telegram_api("setMyCommands", {
            "commands": [
                {"command": "start", "description": "بدء استخدام البوت وعرض القائمة والأزرار"},
                {"command": "codex", "description": "محادثة OpenAI Codex الذكية (--yolo)"},
                {"command": "opencodex", "description": "فتح Codex (--yolo) في نافذة Terminal على السيرفر"},
                {"command": "agy", "description": "محادثة Antigravity CLI الذكية في المشروع"},
                {"command": "devices", "description": "فحص الأجهزة المتصلة بالواي فاي"},
                {"command": "nowplaying", "description": "ريموت كنترول للشاشات المعروضة"},
                {"command": "subtitles", "description": "توليد وترجمة الترجمة العربية: /subtitles <الاسم>"},
                {"command": "server", "description": "صحة وحرارة السيرفر ومصدر الطاقة"},
                {"command": "tailscale", "description": "حالة ورابط المشاهدة خارج المنزل"},
                {"command": "name", "description": "تسمية جهاز: /name <IP> <الاسم>"},
                {"command": "search", "description": "بحث تفاعلي بالبوستر وأزرار التحميل"},
                {"command": "status", "description": "حالة التنزيلات والتورنت الحية"},
                {"command": "history", "description": "عرض آخر التحميلات المكتملة"},
                {"command": "recommend", "description": "اقتراح سهرة اليوم بالذكاء الاصطناعي"},
                {"command": "refresh", "description": "تحديث وفحص مكتبة Jellyfin فوراً"}
            ]
        })
    else:
        logger.error("Failed to authenticate bot token. Verify TELEGRAM_BOT_TOKEN in .env.")

    notified_set = load_notified()
    last_completion_check = 0
    last_device_check = 0
    last_power_check = 0
    last_parental_check = 0

    while True:
        try:
            # 1. Long polling for new messages & callbacks
            updates = telegram_api("getUpdates", {"offset": offset, "timeout": 20})
            if updates and updates.get("ok"):
                for u in updates.get("result", []):
                    offset = u["update_id"] + 1
                    if "message" in u:
                        handle_message(u["message"])
                    elif "callback_query" in u:
                        handle_callback_query(u["callback_query"])

            now = time.time()

            # 2. Check AC power & charger status (every 15 seconds)
            if now - last_power_check > 15:
                check_power_status()
                last_power_check = now

            # 3. Check for completed downloads (every 25 seconds)
            if now - last_completion_check > 25:
                check_and_send_completion_notifications(notified_set)
                last_completion_check = now

            # 4. Check for newly connected network devices (every 120 seconds)
            if now - last_device_check > 120:
                check_new_devices()
                last_device_check = now

            # 5. Check for inappropriate / adult site attempts (every 10 seconds)
            if now - last_parental_check > 10:
                check_parental_alerts()
                last_parental_check = now

        except Exception as e:
            logger.error(f"Polling loop exception: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()
