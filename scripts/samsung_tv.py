#!/usr/bin/env python3
"""
NetFelix Samsung Smart TV Remote Control Module
Supports Samsung Tizen OS (2016-2026+) via WebSocket API (Port 8002 SSL)
Includes Wake-on-LAN, Key Emulation, Token Management, and App Launchers.
"""

import ssl
import json
import time
import socket
import base64
import logging
from pathlib import Path

logger = logging.getLogger("SamsungTV")

CONFIG_DIR = Path("/home/dell/Desktop/My_NetFelix/config")
TOKEN_FILE = CONFIG_DIR / "samsung_tv_token.json"

TV_IP = "192.168.1.2"
TV_MAC = "E0:9D:13:67:68:70"
TV_NAME = "Eslam (Samsung UA50AU7000 4K)"
TV_PORT = 8002


def load_token():
    """Loads saved authentication token from file."""
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("token")
        except Exception:
            return None
    return None


def save_token(token):
    """Saves authentication token to file."""
    try:
        data = {
            "token": token,
            "ip": TV_IP,
            "mac": TV_MAC,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved Samsung TV token successfully: {token}")
        return True
    except Exception as e:
        logger.error(f"Failed to save TV token: {e}")
        return False


def wake_tv():
    """Sends Wake-on-LAN magic packet to wake Samsung TV from standby."""
    try:
        mac_bytes = bytes.fromhex(TV_MAC.replace(":", ""))
        magic = b"\xff" * 6 + mac_bytes * 16
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(magic, ("192.168.1.255", 9))
            s.sendto(magic, ("255.255.255.255", 9))
            s.sendto(magic, (TV_IP, 9))
        logger.info("Sent Wake-on-LAN magic packet to Samsung TV")
        return True
    except Exception as e:
        logger.error(f"Failed to send WOL: {e}")
        return False


def get_tv_info():
    """Queries Samsung TV REST API on port 8001 for device specs and power state."""
    import urllib.request
    try:
        url = f"http://{TV_IP}:8001/api/v2/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.load(r)
            device = data.get("device", {})
            return {
                "online": True,
                "power_state": device.get("PowerState", "on"),
                "model": device.get("modelName", "UA50AU7000UXEG"),
                "name": device.get("name", "Eslam"),
                "os": device.get("OS", "Tizen"),
                "resolution": device.get("resolution", "3840x2160"),
                "token_paired": load_token() is not None,
                "ip": TV_IP,
                "mac": TV_MAC
            }
    except Exception:
        return {
            "online": False,
            "power_state": "offline",
            "model": "UA50AU7000UXEG",
            "name": "Eslam (Samsung TV)",
            "os": "Tizen",
            "resolution": "4K UHD",
            "token_paired": load_token() is not None,
            "ip": TV_IP,
            "mac": TV_MAC
        }


def connect_tv_ws(timeout=5):
    """Establishes a WebSocket connection to the Samsung TV."""
    import websocket
    token = load_token()
    app_name = base64.b64encode(b"NetFelix Remote").decode("utf-8")

    url = f"wss://{TV_IP}:{TV_PORT}/api/v2/channels/samsung.remote.control?name={app_name}"
    if token:
        url += f"&token={token}"

    ws = websocket.create_connection(
        url,
        timeout=timeout,
        sslopt={"cert_reqs": ssl.CERT_NONE}
    )
    return ws


def pair_tv(timeout=30):
    """Initiates pairing handshake with Samsung TV and waits for token approval."""
    import websocket
    app_name = base64.b64encode(b"NetFelix Remote").decode("utf-8")
    url = f"wss://{TV_IP}:{TV_PORT}/api/v2/channels/samsung.remote.control?name={app_name}"

    try:
        ws = websocket.create_connection(
            url,
            timeout=timeout,
            sslopt={"cert_reqs": ssl.CERT_NONE}
        )

        start = time.time()
        while time.time() - start < timeout:
            try:
                msg = ws.recv()
                data = json.loads(msg)
                event = data.get("event")
                if event == "ms.channel.connect":
                    token = data.get("data", {}).get("token")
                    if token:
                        save_token(token)
                        ws.close()
                        return {"success": True, "token": token, "message": "تم الاقتران بنجاح مع شاشة سامسونج!"}
                elif event == "ms.channel.timeOut":
                    ws.close()
                    return {"success": False, "error": "انتهت مهلة التأكيد على الشاشة دون ضغط سماح (Allow)."}
                elif event == "ms.channel.unauthorized":
                    ws.close()
                    return {"success": False, "error": "تم رفض الاتصال من خلال الشاشة."}
            except Exception as e:
                break
        ws.close()
        return {"success": False, "error": "انتهت المهلة بانتظار الموافقة على الشاشة."}
    except Exception as e:
        return {"success": False, "error": f"تعذر الاتصال بالشاشة: {e}"}


def send_key(key):
    """Sends a remote control key command to the Samsung TV."""
    # Ensure key has KEY_ prefix
    key_name = key.upper()
    if not key_name.startswith("KEY_"):
        key_name = f"KEY_{key_name}"

    # Handle special case: Power on when in standby via Wake-on-LAN
    if key_name in ("KEY_POWER", "KEY_POWERON"):
        wake_tv()

    payload = {
        "method": "ms.remote.control",
        "params": {
            "Cmd": "Click",
            "DataOfCmd": key_name,
            "Option": "false",
            "TypeOfRemote": "SendRemoteKey"
        }
    }

    try:
        ws = connect_tv_ws(timeout=3)
        # Check initial message for token if we don't have one
        try:
            ws.settimeout(0.5)
            init_msg = ws.recv()
            init_data = json.loads(init_msg)
            if init_data.get("event") == "ms.channel.connect":
                new_token = init_data.get("data", {}).get("token")
                if new_token and not load_token():
                    save_token(new_token)
        except Exception:
            pass

        ws.settimeout(3)
        ws.send(json.dumps(payload))
        ws.close()
        return {"success": True, "key": key_name}
    except Exception as e:
        logger.error(f"Error sending key {key_name} to Samsung TV: {e}")
        return {"success": False, "error": str(e), "key": key_name}


# Match the installed names so shortcuts use this TV's own application IDs.
TV_APPS = {
    "youtube": ("YouTube", "youtube"),
    "netflix": ("Netflix", "netflix"),
    "shahid": ("Shahid", "shahid", "شاهد"),
    "jellyfin": ("Jellyfin", "jellyfin"),
    "tod": ("TOD", "tod"),
    "watchit": ("WATCH IT", "watchit", "واتشات"),
    "osn": ("OSN+", "osn", "osnplus"),
    "disney": ("Disney+", "disney", "disneyplus"),
}


def launch_app(app):
    """Resolve an installed app and submit its Samsung launch command."""
    if not isinstance(app, str) or app not in TV_APPS:
        return {"success": False, "error": "تطبيق غير معروف"}
    normalize = lambda value: "".join(c for c in str(value).casefold() if c.isalnum())
    aliases = {normalize(name) for name in TV_APPS[app]}
    ws = None
    try:
        ws = connect_tv_ws(timeout=3)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            ws.settimeout(max(.1, deadline - time.monotonic()))
            message = json.loads(ws.recv())
            event = message.get("event")
            if event in ("ms.channel.unauthorized", "ms.channel.timeOut"):
                return {"success": False, "error": "اسمح باتصال الريموت من شاشة التلفزيون"}
            if event == "ms.channel.connect":
                token = message.get("data", {}).get("token")
                if token:
                    save_token(token)
                break
        else:
            raise TimeoutError("TV handshake timed out")
        ws.send(json.dumps({"method": "ms.channel.emit", "params": {
            "event": "ed.installedApp.get", "to": "host"}}))
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            ws.settimeout(max(.1, deadline - time.monotonic()))
            message = json.loads(ws.recv())
            if message.get("event") != "ed.installedApp.get":
                continue
            data = message.get("data", {})
            if isinstance(data, str):
                data = json.loads(data)
            apps = data.get("data", []) if isinstance(data, dict) else data
            if not isinstance(apps, list):
                raise ValueError("Invalid installed app list")
            installed = next((item for item in apps if isinstance(item, dict)
                              and normalize(item.get("name", "")) in aliases), None)
            if not installed or not installed.get("appId"):
                return {"success": False, "error": f"لم يتم العثور على {TV_APPS[app][0]} ضمن تطبيقات التلفزيون المثبتة"}
            ws.send(json.dumps({"method": "ms.channel.emit", "params": {
                "event": "ed.apps.launch", "to": "host", "data": {
                    "appId": installed["appId"],
                    "action_type": "DEEP_LINK" if str(installed.get("app_type")) == "2" else "NATIVE_LAUNCH",
                    "metaTag": ""}}}))
            return {"success": True, "app": app, "message": f"تم إرسال طلب فتح {TV_APPS[app][0]}"}
        raise TimeoutError("Installed apps unavailable")
    except Exception as exc:
        logger.warning("TV app launch failed for %s: %s", app, type(exc).__name__)
        return {"success": False, "error": "تعذر فتح التطبيق. تأكد أن التلفزيون يعمل ومتصل وأنك سمحت باتصال الريموت."}
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


TV_REMOTE_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>NetFelix | ريموت سامسونج</title>
    <meta name="theme-color" content="#1b2131">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220%22%20%22100%22%20%22100%22><text y=%22.9em%22 font-size=%2290%22>📺</text></svg>">
    <style>
        :root { color-scheme: dark; --st-blue: #a4b8ff; --st-text-muted: #9da8bd; --st-green: #74dfb0; }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #f2f4ff; background: #0b0e16; background-image: radial-gradient(ellipse at 50% 0, #242b47 0, transparent 65%); min-height: 100svh; padding: max(24px, env(safe-area-inset-top)) max(16px, env(safe-area-inset-right)) max(24px, env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left)); }
        button, a { touch-action: manipulation; }
        button { font: inherit; color: inherit; cursor: pointer; -webkit-user-select: none; user-select: none; transition: background .18s, border-color .18s, box-shadow .18s; }
        button:focus-visible, a:focus-visible { outline: 2px solid #c2ceff; outline-offset: 4px; }
        button:active { background-color: #344160; box-shadow: inset 0 0 0 1px #9bafff; }
        .icon { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; flex-shrink: 0; }
        .remote-frame { width: 100%; max-width: 420px; margin: auto; padding: 24px; border: 1px solid #ffffff12; border-radius: 36px; background: linear-gradient(155deg, #1b2131, #111620 65%); box-shadow: 0 24px 80px #0005; display: flex; flex-direction: column; gap: 18px; }
        /* Decorative lettering stays behind the controls and never captures taps. */
        .remote-frame { position: relative; isolation: isolate; }
        .remote-frame::before { content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none; border-radius: inherit; opacity: .15; background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22250%22%20height%3D%22180%22%20viewBox%3D%220%200%20250%20180%22%3E%3Cg%20transform%3D%22rotate%28-16%20125%2090%29%22%3E%3Ctext%20x%3D%2230%22%20y%3D%22105%22%20fill%3D%22%23c4b5fd%22%20font-family%3D%22Georgia%2Cserif%22%20font-style%3D%22italic%22%20font-size%3D%2246%22%3EMero%3C%2Ftext%3E%3Cpath%20d%3D%22M174%2079c-9-14-26-3-16%2010l16%2016%2016-16c10-13-7-24-16-10z%22%20fill%3D%22%23f5a0bd%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E"); background-repeat: repeat; background-size: 125px 90px; background-position: center 12px; }
        .brand-row { display: flex; align-items: center; justify-content: space-between; direction: ltr; color: #9da8bd; font-size: 10px; letter-spacing: 2.5px; font-weight: 650; }
        .brand-row span:last-child { letter-spacing: 1px; color: #bdcaff; background: #a4b8ff12; border: 1px solid #a4b8ff20; padding: 5px 9px; border-radius: 20px; }
        .st-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
        .st-device-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
        .st-tv-icon { display: none; }
        .st-name { font-size: 19px; font-weight: 700; letter-spacing: -.6px; }
        .st-status-row { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #aab4c7; margin-top: 7px; }
        .st-dot { width: 6px; height: 6px; flex-shrink: 0; background: #8994aa; border-radius: 50%; }
        .st-dot.online { background: #74dfb0; box-shadow: 0 0 10px #74dfb044; }
        .st-header-actions { display: flex; gap: 8px; }
        .btn-circle { width: 44px; height: 44px; border-radius: 16px; border: 1px solid #ffffff10; background: #ffffff06; display: grid; place-items: center; }
        .btn-power { color: #ffa6ad; background: #ff788512; border-color: #ff788525; font-size: 26px; }
        .mode-switch { display: flex; gap: 4px; padding: 4px; background: #0a0e1780; border: 1px solid #ffffff08; border-radius: 16px; }
        .mode-tab { flex: 1; min-height: 44px; border: 0; background: transparent; border-radius: 12px; color: #9da8bd; font-size: 13px; }
        .mode-tab.active { color: #dce3ff; background: #2a334a; box-shadow: 0 2px 6px #0003; }
        .shortcuts-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .btn-pill-sub { min-height: 44px; display: flex; align-items: center; justify-content: center; gap: 7px; border: 1px solid #ffffff0d; border-radius: 14px; background: #ffffff04; color: #bbc5d8; font-size: 12px; }
        .btn-pill-sub .icon { width: 17px; height: 17px; }
        .nav-card { width: min(100%, 252px); aspect-ratio: 1; align-self: center; position: relative; border: 1px solid #ffffff14; border-radius: 50%; background: radial-gradient(circle, #131925 29%, #232b3c 30%, #1d2534 65%, #2a3346); box-shadow: 0 12px 28px #0004, inset 0 1px 0 #ffffff0d; margin: 2px 0; }
        .dpad-arrow { position: absolute; width: 64px; height: 64px; display: grid; place-items: center; border: 0; border-radius: 50%; color: #bbc7df; background: transparent; }
        .dpad-u { top: 1px; left: 50%; transform: translateX(-50%); }
        .dpad-d { bottom: 1px; left: 50%; transform: translateX(-50%); }
        .dpad-l { left: 1px; top: 50%; transform: translateY(-50%); }
        .dpad-r { right: 1px; top: 50%; transform: translateY(-50%); }
        .dpad-center { width: 86px; height: 86px; border-radius: 50%; border: 1px solid #cbd5ff50; color: #19233d; background: linear-gradient(140deg, #c7d3ff, #93a9f4); font-size: 18px; font-weight: 750; letter-spacing: 1px; box-shadow: 0 5px 20px #0005, inset 0 1px 0 #fff6; }
        .dpad-center:active { background: #d6dfff; }
        .touchpad-surface { display: none; width: 100%; height: 100%; border-radius: inherit; align-items: center; justify-content: center; touch-action: none; background: radial-gradient(#7182a43d 1px, transparent 1px) 0 0 / 14px 14px, #182031; }
        .touchpad-hint { font-size: 12px; color: #c1cbe0; pointer-events: none; background: #182031d9; padding: 12px; border-radius: 12px; }
        .rocker-section { display: flex; align-items: center; justify-content: space-between; gap: 12px; direction: ltr; }
        .st-rocker { width: 64px; height: 146px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 4px; background: #ffffff05; border: 1px solid #ffffff10; border-radius: 25px; }
        .rocker-btn { width: 54px; height: 46px; border: 0; border-radius: 20px; background: transparent; font-size: 25px; }
        .rocker-label { color: #9da8bd; font-size: 9px; letter-spacing: 1.5px; display: flex; align-items: center; flex-direction: column; gap: 4px; }
        .rocker-label .icon { width: 17px; height: 17px; }
        .center-cluster { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
        .cluster-btn { width: 56px; height: 56px; display: grid; place-items: center; background: #242c3d; border: 1px solid #ffffff0b; border-radius: 20px; }
        .section-label { font-size: 11px; color: #8f9bb1; margin-bottom: -7px; }
        .app-dock { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; direction: ltr; }
        .app-tile { padding: 12px 2px; min-height: 68px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; background: #ffffff04; border: 1px solid #ffffff0d; border-radius: 16px; }
        .app-icon { display: grid; place-items: center; color: #b8c7ff; }
        .app-brand { font-size: 15px; font-weight: 800; min-height: 24px; letter-spacing: -.5px; }
        .app-tile:disabled { opacity: .5; cursor: wait; }
        .app-label { font-size: 10px; color: #aebad0; }
        .keypad-drawer { display: none; position: fixed; bottom: 0; left: 50%; transform: translateX(-50%); width: min(100%, 420px); padding: 22px 24px max(24px, env(safe-area-inset-bottom)); background: #1b2334; border: 1px solid #485575; border-radius: 28px 28px 0 0; box-shadow: 0 -20px 80px #000a; z-index: 50; max-height: 90svh; overflow-y: auto; }
        .keypad-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 16px; direction: ltr; }
        .num-btn { min-height: 52px; border: 1px solid #ffffff10; border-radius: 15px; background: #2a344b; font-size: 22px; }
        .toast { display: none; position: fixed; top: max(16px, env(safe-area-inset-top)); left: 50%; transform: translateX(-50%); width: max-content; max-width: calc(100% - 32px); padding: 14px 20px; border-radius: 16px; border: 1px solid #66779f; background: #25314a; box-shadow: 0 8px 30px #0007; z-index: 100; font-size: 13px; }
        .footer-bar { display: flex; justify-content: center; flex-wrap: wrap; align-items: center; gap: 10px; color: #67728a; font-size: 10px; }
        .footer-bar a { color: #9aa8c2; text-decoration: none; min-height: 44px; display: inline-flex; align-items: center; }
        @media (max-width: 480px) { body { padding: max(14px, env(safe-area-inset-top)) max(18px, env(safe-area-inset-right)) max(8px, env(safe-area-inset-bottom)) max(18px, env(safe-area-inset-left)); background: linear-gradient(155deg, #1b2131, #0e131d 70%); } .remote-frame { padding: 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; gap: 14px; } }
        @media (max-width: 360px) { .st-name { font-size: 16px; } .st-header-actions { gap: 4px; } .center-cluster { gap: 8px; } .cluster-btn { width: 50px; height: 50px; } .nav-card { width: 232px; } }
        @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
    </style>
</head>
<body>
    <div class="toast" id="toast" role="status" aria-live="polite"></div>

    <main class="remote-frame">
        <div class="brand-row"><span>NETFELIX / REMOTE</span><span>SAMSUNG</span></div>
        <!-- SmartThings Device Header -->
        <div class="st-header">
            <div class="st-device-title">
                <div class="st-tv-icon"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="3"/><path d="M8 21h8m-4-4v4"/></svg></div>
                <div>
                    <div class="st-name" id="tvName">تلفزيون Eslam</div>
                    <div class="st-status-row">
                        <span class="st-dot"></span>
                        <span id="tvStatus">جارٍ التحقق من الاتصال…</span>
                    </div>
                </div>
            </div>
            <div class="st-header-actions">
                <button class="btn-circle" onclick="sendCmd('KEY_SOURCE')" title="المصدر / HDMI">
                    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h16v12H4zM8 4v4m8-4v4M9 12h6"/></svg>
                </button>
                <button class="btn-circle btn-power" onclick="sendCmd('KEY_POWER')" title="تشغيل / إيقاف">
                    ⏻
                </button>
            </div>
        </div>

        <!-- Mode Toggle: Directional D-Pad vs Touchpad -->
        <div class="mode-switch">
            <button class="mode-tab active" id="tabDpad" onclick="setMode('dpad')">أزرار التوجيه</button>
            <button class="mode-tab" id="tabTouch" onclick="setMode('touch')">لوحة اللمس</button>
        </div>

        <!-- Quick Shortcut Bar -->
        <div class="shortcuts-row">
            <button class="btn-pill-sub" id="keypadToggle" aria-expanded="false" aria-controls="keypadDrawer" onclick="toggleKeypad()">123</button>
            <button class="btn-pill-sub" onclick="sendCmd('KEY_GUIDE')"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="4" width="14" height="17" rx="3"/><path d="M9 9h6m-6 4h6m-6 4h4"/></svg> الدليل</button>
            <button class="btn-pill-sub" onclick="sendCmd('KEY_MENU')"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/></svg> القائمة</button>
        </div>

        <!-- Center Navigation (D-Pad or Touchpad) -->
        <div class="nav-card">
            <!-- 4-Way D-Pad -->
            <div id="dpadView" style="width: 100%; height: 100%; position: relative;">
                <button class="dpad-arrow dpad-u" onclick="sendCmd('KEY_UP')"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 14 4-4 4 4"/></svg></button>
                <button class="dpad-arrow dpad-l" onclick="sendCmd('KEY_LEFT')"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m14 8-4 4 4 4"/></svg></button>
                <button class="dpad-arrow dpad-r" onclick="sendCmd('KEY_RIGHT')"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m10 8 4 4-4 4"/></svg></button>
                <button class="dpad-arrow dpad-d" onclick="sendCmd('KEY_DOWN')"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 10 4 4 4-4"/></svg></button>
                <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);">
                    <button class="dpad-center" onclick="sendCmd('KEY_ENTER')">OK</button>
                </div>
            </div>

            <!-- Swipe Touchpad Surface -->
            <div id="touchView" class="touchpad-surface">
                <div class="touchpad-hint">
                    <span>اسحب للتنقل • اضغط لـ OK</span>
                </div>
            </div>
        </div>

        <!-- Samsung SmartThings Iconic Rockers Section -->
        <div class="rocker-section">
            <!-- Left Rocker: Volume -->
            <div class="st-rocker">
                <button class="rocker-btn" onclick="sendCmd('KEY_VOLUP')">+</button>
                <div class="rocker-label">
                    <span><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M11 4 6 8H3v8h3l5 4zM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/></svg></span>
                    <span>VOL</span>
                </div>
                <button class="rocker-btn" onclick="sendCmd('KEY_VOLDOWN')">−</button>
            </div>

            <!-- Center Cluster (Back, Home, Mute, Play/Pause) -->
            <div class="center-cluster">
                <button class="cluster-btn" onclick="sendCmd('KEY_RETURN')" title="رجوع">
                    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5-5 5 5 5M4 10h10a5 5 0 0 1 0 10"/></svg>
                </button>
                <button class="cluster-btn" style="color: var(--st-blue);" onclick="sendCmd('KEY_HOME')" title="الرئيسية">
                    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9"/></svg>
                </button>
                <button class="cluster-btn" onclick="sendCmd('KEY_MUTE')" title="كتم الصوت">
                    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M11 4 6 8H3v8h3l5 4zM16 9l6 6m0-6-6 6"/></svg>
                </button>
                <button class="cluster-btn" onclick="sendCmd('KEY_PLAY')" title="تشغيل">
                    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 4 10 8-10 8zM19 5v14"/></svg>
                </button>
            </div>

            <!-- Right Rocker: Channel -->
            <div class="st-rocker">
                <button class="rocker-btn" onclick="sendCmd('KEY_CHUP')">∧</button>
                <div class="rocker-label">
                    <span><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="3"/><path d="M8 21h8m-4-4v4"/></svg></span>
                    <span>CH</span>
                </div>
                <button class="rocker-btn" onclick="sendCmd('KEY_CHDOWN')">∨</button>
            </div>
        </div>

        <div class="section-label">وصول سريع</div>
        <div class="app-dock">
            <button class="app-tile" onclick="launchApp('youtube', this)" aria-label="فتح YouTube"><span class="app-icon app-brand" style="color: #ff6b73">▶</span><span class="app-label">YouTube</span></button>
            <button class="app-tile" onclick="launchApp('netflix', this)" aria-label="فتح Netflix"><span class="app-icon app-brand" style="color: #ff5365">N</span><span class="app-label">Netflix</span></button>
            <button class="app-tile" onclick="launchApp('shahid', this)" aria-label="فتح Shahid"><span class="app-icon app-brand" style="color: #58e4ba">شاهد</span><span class="app-label">Shahid</span></button>
            <button class="app-tile" onclick="launchApp('jellyfin', this)" aria-label="فتح Jellyfin"><span class="app-icon app-brand" style="color: #b5a0ff">△</span><span class="app-label">Jellyfin</span></button>
            <button class="app-tile" onclick="launchApp('tod', this)" aria-label="فتح TOD"><span class="app-icon app-brand" style="color: #f4ff5d">TOD</span><span class="app-label">TOD</span></button>
            <button class="app-tile" onclick="launchApp('watchit', this)" aria-label="فتح WATCH IT"><span class="app-icon app-brand" style="color: #ffb96e">WATCH IT</span><span class="app-label">WATCH IT</span></button>
            <button class="app-tile" onclick="launchApp('osn', this)" aria-label="فتح OSN+"><span class="app-icon app-brand" style="color: #ff80bc">osn+</span><span class="app-label">OSN+</span></button>
            <button class="app-tile" onclick="launchApp('disney', this)" aria-label="فتح Disney+"><span class="app-icon app-brand" style="color: #8ab9ff">Disney+</span><span class="app-label">Disney+</span></button>
        </div>

        <!-- SmartThings 123 Slide-up Number Pad Drawer -->
        <div class="keypad-drawer" id="keypadDrawer">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.9rem; font-weight: 700;">لوحة الأرقام (123)</span>
                <button aria-label="إغلاق لوحة الأرقام" onclick="toggleKeypad()" style="min-width:44px; min-height:44px; background: none; border: none; color: var(--st-text-muted); font-size: 1.2rem; cursor: pointer;">✕</button>
            </div>
            <div class="keypad-grid">
                <button class="num-btn" onclick="sendCmd('KEY_1')">1</button>
                <button class="num-btn" onclick="sendCmd('KEY_2')">2</button>
                <button class="num-btn" onclick="sendCmd('KEY_3')">3</button>
                <button class="num-btn" onclick="sendCmd('KEY_4')">4</button>
                <button class="num-btn" onclick="sendCmd('KEY_5')">5</button>
                <button class="num-btn" onclick="sendCmd('KEY_6')">6</button>
                <button class="num-btn" onclick="sendCmd('KEY_7')">7</button>
                <button class="num-btn" onclick="sendCmd('KEY_8')">8</button>
                <button class="num-btn" onclick="sendCmd('KEY_9')">9</button>
                <button class="num-btn" onclick="sendCmd('KEY_MINUS')">-</button>
                <button class="num-btn" onclick="sendCmd('KEY_0')">0</button>
                <button class="num-btn" onclick="sendCmd('KEY_RETURN')">⌫</button>
            </div>
        </div>

        <div class="footer-bar">
            <a href="http://192.168.1.15:3000">لوحة NetFelix الرئيسية</a>
            <span>•</span>
            <a href="http://192.168.1.15:8092/devices">راصد الأجهزة</a>
        </div>
    </main>

    <script>
        let toastTimer;
        function showToast(text, duration = 2500) {
            clearTimeout(toastTimer);
            const t = document.getElementById('toast');
            t.innerText = text;
            t.style.display = 'block';
            toastTimer = setTimeout(() => { t.style.display = 'none'; }, duration);
        }

        async function launchApp(app, button) {
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            if (navigator.vibrate) navigator.vibrate(22);
            showToast('جارٍ الاتصال بالتلفزيون…');
            try {
                const response = await fetch('/api/tv/launch_app', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({app})
                });
                const data = await response.json();
                showToast(data.success ? data.message : (data.error || 'تعذر فتح التطبيق'), 4000);
            } catch (error) {
                showToast('تعذر الاتصال بالتلفزيون', 4000);
            } finally {
                button.disabled = false;
                button.removeAttribute('aria-busy');
            }
        }

        async function sendCmd(key) {
            if (navigator.vibrate) navigator.vibrate(22);
            try {
                const res = await fetch('/api/tv/send_key', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({key: key})
                });
                const data = await res.json();
                if (!data.success) {
                    showToast('⚠️ اضغط سماح (Allow) على شاشة التلفزيون!');
                }
            } catch (err) {
                showToast('❌ تعذر إرسال الأمر للشاشة');
            }
        }

        function setMode(mode) {
            const tabDpad = document.getElementById('tabDpad');
            const tabTouch = document.getElementById('tabTouch');
            const dpadView = document.getElementById('dpadView');
            const touchView = document.getElementById('touchView');

            tabDpad.setAttribute('aria-pressed', mode === 'dpad');
            tabTouch.setAttribute('aria-pressed', mode === 'touch');
            if (mode === 'dpad') {
                tabDpad.classList.add('active');
                tabTouch.classList.remove('active');
                dpadView.style.display = 'block';
                touchView.style.display = 'none';
            } else {
                tabTouch.classList.add('active');
                tabDpad.classList.remove('active');
                dpadView.style.display = 'none';
                touchView.style.display = 'flex';
            }
        }

        function toggleKeypad() {
            const drawer = document.getElementById('keypadDrawer');
            const open = drawer.style.display !== 'block';
            drawer.style.display = open ? 'block' : 'none';
            document.getElementById('keypadToggle').setAttribute('aria-expanded', open);
            if (open) drawer.querySelector('button').focus();
            else document.getElementById('keypadToggle').focus();
        }

        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && document.getElementById('keypadDrawer').style.display === 'block') toggleKeypad();
        });

        // Swipe Gesture Handler for Touchpad Mode
        const touchArea = document.getElementById('touchView');
        let touchStartX = 0;
        let touchStartY = 0;
        let touchStartTime = 0;

        touchArea.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
            touchStartY = e.changedTouches[0].screenY;
            touchStartTime = Date.now();
        }, {passive: true});

        touchArea.addEventListener('touchend', (e) => {
            const diffX = e.changedTouches[0].screenX - touchStartX;
            const diffY = e.changedTouches[0].screenY - touchStartY;
            const duration = Date.now() - touchStartTime;

            // Tap check (< 200ms and < 15px movement)
            if (duration < 250 && Math.abs(diffX) < 15 && Math.abs(diffY) < 15) {
                sendCmd('KEY_ENTER');
                return;
            }

            // Swipe check
            const threshold = 35;
            if (Math.abs(diffX) > Math.abs(diffY)) {
                if (diffX > threshold) {
                    sendCmd('KEY_RIGHT');
                } else if (diffX < -threshold) {
                    sendCmd('KEY_LEFT');
                }
            } else {
                if (diffY > threshold) {
                    sendCmd('KEY_DOWN');
                } else if (diffY < -threshold) {
                    sendCmd('KEY_UP');
                }
            }
        }, {passive: true});

        // Real-time TV status
        async function updateStatus() {
            try {
                const res = await fetch('/api/tv/status');
                const data = await res.json();
                document.querySelector('.st-dot').classList.toggle('online', Boolean(data.online));
                if (data.online) {
                    document.getElementById('tvStatus').innerText = (data.model || 'Samsung TV') + ' • ' + (data.power_state === 'standby' ? 'وضع الاستعداد' : 'تعمل الآن');
                } else {
                    document.getElementById('tvStatus').innerText = 'غير متصلة';
                }
            } catch(e) {
                document.querySelector('.st-dot').classList.remove('online');
                document.getElementById('tvStatus').innerText = 'تعذر التحقق من الاتصال';
            }
        }
        const keyLabels = {KEY_UP: 'أعلى', KEY_DOWN: 'أسفل', KEY_LEFT: 'يسار', KEY_RIGHT: 'يمين', KEY_ENTER: 'اختيار', KEY_VOLUP: 'رفع الصوت', KEY_VOLDOWN: 'خفض الصوت', KEY_CHUP: 'القناة التالية', KEY_CHDOWN: 'القناة السابقة'};
        document.querySelectorAll('button').forEach(button => {
            const command = (button.getAttribute('onclick') || '').match(/KEY_[A-Z0-9]+/);
            const label = button.title || (command && keyLabels[command[0]]);
            if (label) button.setAttribute('aria-label', label);
        });
        setMode('dpad');
        updateStatus();
        setInterval(updateStatus, 8000);
    </script>
</body>
</html>
"""
