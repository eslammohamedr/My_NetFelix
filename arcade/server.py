#!/usr/bin/env python3
"""
NetFelix Retro Arcade & Virtual Controller Gateway
High-performance aiohttp WebSocket & Static Server
Connects Samsung Smart TV to Mobile Web Controllers with sub-15ms latency.
"""

import os
import json
import logging
from pathlib import Path
from aiohttp import web, WSMsgType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RetroArcade")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
GAMES_DIR = BASE_DIR / "games"
COVERS_DIR = BASE_DIR / "covers"

# In-memory session tracking
# Room structure: { room_id: { "tv": ws, "p1": ws, "p2": ws } }
ROOMS = {}

GAMES_METADATA = [
    {
        "id": "mario",
        "title": "Super Mario Bros",
        "system": "NES",
        "core": "fceumm",
        "file": "mario.nes",
        "cover": "mario.png",
        "desc": "اللعبة الأسطورية الأشهر في تاريخ الألعاب؛ ساعد ماريو في إنقاذ الأميرة بيتش!",
        "players": 2
    },
    {
        "id": "topgear",
        "title": "Top Gear (Car Racing)",
        "system": "SNES",
        "core": "snes9x",
        "file": "top_gear.sfc",
        "cover": "top_gear.png",
        "desc": "أعظم وأشهر لعبة سباق سيارات كلاسيكية مع الموسيقى الحماسية الخالدة وإمكانية اللعب الثنائي.",
        "players": 2
    },
    {
        "id": "pepsiman",
        "title": "Pepsiman (PlayStation 1)",
        "system": "PS1",
        "core": "pcsx_rearmed",
        "file": "pepsiman.chd",
        "cover": "pepsiman.png",
        "desc": "لعبة الجري والمطاردات الكوميدية الشهيرة لبلايستيشن 1؛ اركض وتفادى العوائق لتوصيل البيبسي!",
        "players": 1
    },
    {
        "id": "mario3",
        "title": "Super Mario Bros 3",
        "system": "NES",
        "core": "fceumm",
        "file": "mario3.nes",
        "cover": "mario3.png",
        "desc": "الجزء الثالث الأسطوري مع بدلة الراكون الطائرة وعوالم نينتندو الساحرة المليئة بالمفاجآت.",
        "players": 2
    },
    {
        "id": "31in1",
        "title": "31-in-1 Arcade Multicart",
        "system": "NES",
        "core": "fceumm",
        "file": "31in1realgame-multicart.nes",
        "cover": "31in1realgame-multicart.png",
        "desc": "مجموعة تضم 31 لعبة كلاسيكية متنوعة (أكشن، مغامرات، أركيد) وممتعة لجميع أفراد العائلة.",
        "players": 2
    },
    {
        "id": "driar",
        "title": "Driar Platformer",
        "system": "NES",
        "core": "fceumm",
        "file": "driar.nes",
        "cover": "driar.png",
        "desc": "لعبة مغامرات وقفز منصات شهيرة ومتقنة؛ اجمع النجوم وتغلب على العقبات للوصول للباب.",
        "players": 2
    },
    {
        "id": "babelblox",
        "title": "Babel Blox (Tetris)",
        "system": "NES",
        "core": "fceumm",
        "file": "babelblox.nes",
        "cover": "babelblox.png",
        "desc": "لعبة ألغاز بناء وترتيب القوالب المستوحاة من تيترس التنافسية الكلاسيكية.",
        "players": 2
    },
    {
        "id": "pong",
        "title": "Retro Pong Duo",
        "system": "NES",
        "core": "fceumm",
        "file": "pong.nes",
        "cover": "pong.png",
        "desc": "لعبة البونج التنافسية الأسطورية؛ مثالية لتحدي بين لاعبين (Player 1 vs Player 2).",
        "players": 2
    },
    {
        "id": "flappy",
        "title": "Flappy Bird Retro",
        "system": "NES",
        "core": "fceumm",
        "file": "flappybird.nes",
        "cover": "flappybird.png",
        "desc": "النسخة التراثية الكلاسيكية من فلابي بيرد بأسلوب رسومات وأصوات نينتندو 8-بت.",
        "players": 1
    },
    {
        "id": "blaster",
        "title": "Blaster Galaxy Shooter",
        "system": "NES",
        "core": "fceumm",
        "file": "blaster.nes",
        "cover": "blaster.png",
        "desc": "لعبة إطلاق نار وحروب فضاء فضائية كلاسيكية سريعة تعتمد على سرعة رد الفعل والمراوغة.",
        "players": 1
    },
    {
        "id": "falling",
        "title": "Falling Arcade",
        "system": "NES",
        "core": "fceumm",
        "file": "falling.nes",
        "cover": "falling.png",
        "desc": "لعبة نزول ومنصات سريعة؛ اهرب من السقف قبل أن يسحقك وواصل الهبوط بأمان.",
        "players": 1
    },
    {
        "id": "2048",
        "title": "2048 Puzzle",
        "system": "NES",
        "core": "fceumm",
        "file": "2048.nes",
        "cover": "2048.png",
        "desc": "لعبة الأرقام والذكاء الشهيرة محولة لتعمل على معالجات نينتندو الكلاسيكية.",
        "players": 1
    }
]


async def handle_index(request):
    """Direct TV interface."""
    resp = web.FileResponse(STATIC_DIR / "tv.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


async def handle_pad(request):
    """Mobile gamepad interface."""
    resp = web.FileResponse(STATIC_DIR / "pad.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


async def handle_games_api(request):
    """Returns games catalog and custom uploaded roms."""
    catalog = list(GAMES_METADATA)
    # Check for any extra ROMs dropped in games folder
    known_files = {g["file"] for g in catalog}
    for f in GAMES_DIR.glob("*.*"):
        if f.name not in known_files and f.suffix.lower() in (".nes", ".sfc", ".smc", ".bin", ".gb", ".gba"):
            core = "fceumm"
            system = "NES"
            if f.suffix.lower() in (".sfc", ".smc"):
                core = "snes9x"
                system = "SNES"
            elif f.suffix.lower() in (".gb", ".gbc"):
                core = "gambatte"
                system = "Game Boy"
            elif f.suffix.lower() == ".bin":
                core = "genesis_plus_gx"
                system = "Sega Genesis"
            catalog.append({
                "id": f.stem,
                "title": f.stem.replace("_", " ").title(),
                "system": system,
                "core": core,
                "file": f.name,
                "cover": "",
                "desc": f"لعبة إضافية ({system}) من مجلد الألعاب المحلي.",
                "players": 2
            })
    return web.json_response({"status": "success", "games": catalog})


async def broadcast_to_tvs(room, msg_data):
    """Safely broadcasts a JSON message to all active TV instances in the room."""
    dead = []
    for tv_ws in list(room.get("tvs", set())):
        if tv_ws is None or tv_ws.closed:
            dead.append(tv_ws)
        else:
            try:
                await tv_ws.send_json(msg_data)
            except Exception as e:
                logger.warning(f"Failed sending to TV websocket: {e}")
                dead.append(tv_ws)
    for d in dead:
        room["tvs"].discard(d)


async def handle_ws(request):
    """High-speed WebSocket connection handler for TV and Mobile controllers."""
    ws = web.WebSocketResponse(heartbeat=10.0, max_msg_size=4096)
    await ws.prepare(request)

    role = request.query.get("role", "controller")
    room_id = request.query.get("room", "main")
    player_num = int(request.query.get("player", "1"))

    if room_id not in ROOMS:
        ROOMS[room_id] = {"tvs": set(), "p1": None, "p2": None}
    room = ROOMS[room_id]

    client_id = f"P{player_num}" if role == "controller" else "TV"
    logger.info(f"[{room_id}] {client_id} connected via WebSocket")

    if role == "tv":
        room["tvs"].add(ws)
        # Notify TV of current controller states
        await ws.send_json({
            "type": "state",
            "p1": room["p1"] is not None and not room["p1"].closed,
            "p2": room["p2"] is not None and not room["p2"].closed
        })
    else:
        slot = f"p{player_num}"
        room[slot] = ws
        # Notify all active TVs that controller connected
        await broadcast_to_tvs(room, {
            "type": "player_connected",
            "player": player_num
        })
        # Acknowledge to phone
        has_tv = any(t is not None and not t.closed for t in room["tvs"])
        await ws.send_json({
            "type": "connected",
            "player": player_num,
            "tv_active": has_tv
        })

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")

                    if role == "controller":
                        # Fast-path: forward input events directly to TV
                        if msg_type in ("down", "up", "press"):
                            await broadcast_to_tvs(room, {
                                "type": "input",
                                "action": msg_type,
                                "button": data.get("btn"),
                                "player": player_num
                            })
                        elif msg_type == "tv_cmd":
                            cmd = data.get("command")
                            logger.info(f"[{room_id}] Controller requested TV command: {cmd}")
                            await broadcast_to_tvs(room, {
                                "type": "tv_cmd",
                                "command": cmd
                            })
                        elif msg_type == "ping":
                            await ws.send_json({"type": "pong"})

                    elif role == "tv":
                        # TV broadcasts to controllers (e.g. game loaded, rumble/vibrate)
                        if msg_type == "vibrate":
                            target_p = data.get("player", 1)
                            target_ws = room.get(f"p{target_p}")
                            if target_ws is not None and not target_ws.closed:
                                await target_ws.send_json({"type": "vibrate", "duration": data.get("duration", 50)})
                        elif msg_type == "tv_log":
                            logger.info(f"[TV LOG] {data.get('msg')}")

                except Exception as e:
                    logger.error(f"Error processing WS message: {e}")
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error on {client_id}: {ws.exception()}")

    finally:
        logger.info(f"[{room_id}] {client_id} disconnected")
        if role == "tv":
            room["tvs"].discard(ws)
        else:
            slot = f"p{player_num}"
            if room.get(slot) == ws:
                room[slot] = None
            await broadcast_to_tvs(room, {
                "type": "player_disconnected",
                "player": player_num
            })

    return ws


def make_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/tv", handle_index)
    app.router.add_get("/pad", handle_pad)
    app.router.add_get("/controller", handle_pad)
    app.router.add_get("/ws", handle_ws)
    app.router.add_get("/api/games", handle_games_api)

    # Static file routes
    app.router.add_static("/static/", STATIC_DIR)
    app.router.add_static("/games/", GAMES_DIR)
    app.router.add_static("/covers/", COVERS_DIR)
    app.router.add_static("/bios/", BASE_DIR / "bios")

    return app


if __name__ == "__main__":
    app = make_app()
    port = int(os.environ.get("ARCADE_PORT", 8095))
    logger.info(f"🎮 Retro Arcade Gateway starting on http://0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port)
