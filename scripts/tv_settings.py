"""Shared appearance preferences for the TV, browser and Android companion."""

import base64
import copy
import hashlib
import io
import json
import os
import re
import tempfile
import threading
import uuid
import time
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import tv_companion
from PIL import Image, UnidentifiedImageError

UI_DIR = Path(__file__).resolve().parent / "tv_ui"
THEMES = json.loads((UI_DIR / "themes.json").read_text())
THEME_IDS = {theme["id"] for theme in THEMES}
DEFAULTS = {
    "theme": "night", "title": "Your TV. Your world.",
    "subtitle": "Movies, live matches and your favorite places. Together in NetFelix.",
    "tileSize": "normal", "menuPosition": "left",
    "accent": "", "textSize": "normal", "iconStyle": "theme", "motion": True, "blur": True,
    "glow": True, "clock24": False, "showPrayer": True, "showWeather": True,
    "wallpaper": "", "favorites": ["jellyfin", "iptv", "youtube", "netflix", "prayer", "radio", "matches", "search"],
}
APPS = {"jellyfin": "Jellyfin", "iptv": "Live TV", "youtube": "YouTube", "netflix": "Netflix",
        "prayer": "Prayer", "radio": "Quran Radio", "matches": "Matches", "search": "Search"}


class RevisionConflict(ValueError):
    pass


class AppearanceStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "tv_appearance.json"
        self.lock = threading.RLock()
        self.trial = None

    def _load(self):
        if not self.path.exists():
            return {"revision": 0, "activeProfile": "family", "profiles": [
                {"id": "family", "name": "Family", "settings": copy.deepcopy(DEFAULTS)}]}
        # Do not silently overwrite a corrupt or unreadable preference file.
        state = json.loads(self.path.read_text())
        for profile in state["profiles"]:
            profile["settings"] = {**copy.deepcopy(DEFAULTS), **profile["settings"]}
        state.setdefault("presets", [])
        state.setdefault("schedules", [])
        return state

    def _save(self, state):
        self.directory.mkdir(parents=True, exist_ok=True)
        state["revision"] += 1
        fd, filename = tempfile.mkstemp(dir=self.directory, prefix=".tv-appearance-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(state, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(filename, self.path)
        finally:
            if os.path.exists(filename):
                os.unlink(filename)

    def snapshot(self):
        with self.lock:
            state = self._load()
            active = next(p for p in state["profiles"] if p["id"] == state["activeProfile"])
            trial = self.trial
            if trial and trial["expires"] <= time.time():
                self.trial = trial = None
            display = copy.deepcopy(active["settings"])
            active_schedule = None
            for rule in state.get("schedules", []):
                now = datetime.now(ZoneInfo(rule["timezone"]))
                minute = now.strftime("%H:%M")
                # Overnight ranges belong to the day on which they start.
                overnight = rule["start"] > rule["end"]
                day = (now.weekday() - (1 if overnight and minute < rule["end"] else 0)) % 7
                in_range = (minute >= rule["start"] or minute < rule["end"]) if overnight else rule["start"] <= minute < rule["end"]
                start_day = now.date() - timedelta(days=1 if overnight and minute < rule["end"] else 0)
                in_dates = (not rule.get("startsOn") or start_day.isoformat() >= rule["startsOn"]) and (not rule.get("endsOn") or start_day.isoformat() <= rule["endsOn"])
                if in_dates and rule["enabled"] and rule["profile"] == active["id"] and day in rule["days"] and in_range:
                    preset = next((p for p in state.get("presets", []) if p["id"] == rule["preset"]), None)
                    if preset:
                        display = copy.deepcopy(preset["settings"])
                        active_schedule = rule["id"]
            if trial:
                display = copy.deepcopy(trial["settings"])
            display_revision = hashlib.sha256(json.dumps([state["revision"], display, trial["id"] if trial else None, active_schedule], sort_keys=True).encode()).hexdigest()
            return {"displaySettings": display, "displayRevision": display_revision,
                    "trial": {"id":trial["id"], "expires":trial["expires"]} if trial else None,
                    "activeSchedule": active_schedule,
                    "presets": copy.deepcopy(state.get("presets", [])),
                    "schedules": copy.deepcopy(state.get("schedules", [])),
                    "revision": state["revision"], "activeProfile": active["id"],
                    "profiles": [{"id": p["id"], "name": p["name"]} for p in state["profiles"]],
                    "settings": copy.deepcopy(active["settings"]), "themes": THEMES, "apps": APPS,
                    "defaults": copy.deepcopy(DEFAULTS)}

    @staticmethod
    def validate(patch):
        if not isinstance(patch, dict) or set(patch) - set(DEFAULTS):
            raise ValueError("Unknown appearance setting")
        for key, value in patch.items():
            if isinstance(DEFAULTS[key], bool):
                if type(value) is not bool:
                    raise ValueError(key + " must be true or false")
            elif key in ("title", "subtitle"):
                limit = 64 if key == "title" else 180
                if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
                    raise ValueError(key + " is too long or contains control characters")
            elif key == "theme" and (not isinstance(value, str) or value not in THEME_IDS):
                raise ValueError("Unknown theme")
            elif key == "textSize" and value not in ("small", "normal", "large"):
                raise ValueError("Unknown text size")
            elif key == "tileSize" and value not in ("small", "normal", "large"):
                raise ValueError("Unknown tile size")
            elif key == "menuPosition" and value not in ("left", "right", "hidden"):
                raise ValueError("Unknown menu position")
            elif key == "iconStyle" and value not in ("theme", "glass", "solid", "outline"):
                raise ValueError("Unknown icon style")
            elif key == "accent" and (not isinstance(value, str) or value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value)):
                raise ValueError("Accent must be a hex color")
            elif key == "wallpaper" and (not isinstance(value, str) or value and not re.fullmatch(r"/api/tv/appearance/wallpaper/[0-9a-f]{64}", value)):
                raise ValueError("Use an uploaded wallpaper")
            elif key == "favorites":
                if not isinstance(value, list) or any(not isinstance(item, str) or item not in APPS for item in value) or len(set(value)) != len(value):
                    raise ValueError("Favorites must contain unique supported apps")
        return patch

    def update(self, patch, profile_id=None, revision=None):
        self.validate(patch)
        with self.lock:
            state = self._load()
            if revision is not None and (type(revision) is not int or revision != state["revision"]):
                raise RevisionConflict("Settings changed on another device. Load latest before applying.")
            profile = next((p for p in state["profiles"] if p["id"] == (profile_id or state["activeProfile"])), None)
            if profile is None:
                raise ValueError("Unknown profile")
            if patch.get("wallpaper") and not (self.directory / "tv_wallpapers" / patch["wallpaper"].rsplit("/", 1)[-1]).is_file():
                raise ValueError("Wallpaper is no longer available")
            self.trial = None
            profile["settings"].update(copy.deepcopy(patch))
            self._save(state)
            return self.snapshot()

    def profile(self, action, name=None, profile_id=None):
        with self.lock:
            state = self._load()
            if action == "create":
                if not isinstance(name, str) or not name.strip() or len(name) > 24 or any(ord(c) < 32 for c in name):
                    raise ValueError("Enter a profile name, up to 24 characters")
                if len(state["profiles"]) >= 6:
                    raise ValueError("Maximum six profiles")
                profile_id = uuid.uuid4().hex
                state["profiles"].append({"id": profile_id, "name": name.strip(), "settings": copy.deepcopy(DEFAULTS)})
            elif action != "select":
                raise ValueError("Unknown profile action")
            if not any(p["id"] == profile_id for p in state["profiles"]):
                raise ValueError("Unknown profile")
            self.trial = None
            state["activeProfile"] = profile_id
            self._save(state)
            return self.snapshot()

    def manage(self, kind, body):
        """Transactional presets, schedules and expiring previews; every write checks revision."""
        with self.lock:
            state = self._load()
            if body.get("revision") != state["revision"] or type(body.get("revision")) is not int:
                raise RevisionConflict("Settings changed. Load latest before continuing.")
            action = body.get("action")
            active = next(p for p in state["profiles"] if p["id"] == state["activeProfile"])
            if kind == "trial":
                if action == "start":
                    if self.trial and self.trial["expires"] > time.time():
                        raise ValueError("A TV preview is already running. Keep or restore it first.")
                    settings = {**copy.deepcopy(DEFAULTS), **self.validate(body.get("settings"))}
                    self._check_wallpaper(settings)
                    self.trial = {"id":uuid.uuid4().hex, "settings":settings,
                                  "profile":active["id"], "expires":time.time() + 30}
                elif action in ("keep", "restore"):
                    if not self.trial or self.trial["expires"] <= time.time():
                        self.trial = None
                        raise ValueError("This TV preview has expired or ended")
                    if body.get("id") != self.trial["id"]:
                        raise ValueError("This preview belongs to another session")
                    if action == "keep":
                        active["settings"] = self.trial["settings"]
                        self._save(state)
                    self.trial = None
                else:
                    raise ValueError("Unknown preview action")
                return self.snapshot()
            collection = state.setdefault(kind, [])
            if kind == "presets":
                if action in ("save", "duplicate", "import"):
                    if len(collection) >= 30:
                        raise ValueError("Maximum 30 presets")
                    name = body.get("name")
                    if not isinstance(name, str) or not name.strip() or len(name) > 40 or any(ord(c) < 32 for c in name):
                        raise ValueError("Enter a preset name, up to 40 characters")
                    settings = body.get("settings")
                    if action == "duplicate":
                        original = next((p for p in collection if p["id"] == body.get("id")), None)
                        if not original:
                            raise ValueError("Unknown preset")
                        settings = original["settings"]
                    settings = {**copy.deepcopy(DEFAULTS), **self.validate(settings)}
                    if action == "import" and body.get("wallpaperImage") is not None:
                        image = self._decode_wallpaper(body["wallpaperImage"])
                        expected = "/api/tv/appearance/wallpaper/" + hashlib.sha256(image).hexdigest()
                        if settings.get("wallpaper") != expected:
                            raise ValueError("Design photo does not match its wallpaper")
                        settings["wallpaper"] = self._write_wallpaper(image)
                    self._check_wallpaper(settings)
                    collection.append({"id":uuid.uuid4().hex, "name":name.strip(), "settings":copy.deepcopy(settings)})
                elif action == "delete":
                    if not any(p["id"] == body.get("id") for p in collection):
                        raise ValueError("Unknown preset")
                    if any(r["preset"] == body["id"] for r in state.get("schedules", [])):
                        raise ValueError("Remove schedules using this preset first")
                    state[kind] = [p for p in collection if p["id"] != body["id"]]
                elif action == "restore":
                    preset = next((p for p in collection if p["id"] == body.get("id")), None)
                    if not preset:
                        raise ValueError("Unknown preset")
                    self._check_wallpaper(preset["settings"])
                    active["settings"] = copy.deepcopy(preset["settings"])
                    self.trial = None
                else:
                    raise ValueError("Unknown preset action")
            elif kind == "schedules":
                if action == "delete":
                    if not any(r["id"] == body.get("id") for r in collection):
                        raise ValueError("Unknown schedule")
                    state[kind] = [r for r in collection if r["id"] != body["id"]]
                elif action == "save":
                    if len(collection) >= 20:
                        raise ValueError("Maximum 20 schedules")
                    if not any(p["id"] == body.get("preset") for p in state.get("presets", [])):
                        raise ValueError("Choose a saved preset")
                    for key in ("start", "end"):
                        if not isinstance(body.get(key), str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", body[key]):
                            raise ValueError("Choose a valid start and end time")
                    if body["start"] == body["end"]:
                        raise ValueError("Start and end must differ")
                    days = body.get("days")
                    if not isinstance(days, list) or not days or any(type(d) is not int or d not in range(7) for d in days):
                        raise ValueError("Choose weekdays from Monday (0) to Sunday (6)")
                    for key in ("startsOn", "endsOn"):
                        value = body.get(key, "")
                        if not isinstance(value, str):
                            raise ValueError("Choose valid schedule dates")
                        if value:
                            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                                raise ValueError("Choose valid schedule dates")
                            try:
                                date.fromisoformat(value)
                            except ValueError:
                                raise ValueError("Choose valid schedule dates")
                    if body.get("startsOn") and body.get("endsOn") and body["startsOn"] > body["endsOn"]:
                        raise ValueError("Schedule end date must follow its start date")
                    zone = body.get("timezone", "Africa/Cairo")
                    try:
                        ZoneInfo(zone)
                    except (ZoneInfoNotFoundError, ValueError, TypeError):
                        raise ValueError("Unknown timezone")
                    collection.append({"id":uuid.uuid4().hex, "preset":body["preset"], "profile":active["id"],
                                       "start":body["start"], "end":body["end"], "days":sorted(set(days)),
                                       "timezone":zone, "enabled":True, "startsOn":body.get("startsOn", ""), "endsOn":body.get("endsOn", "")})
                else:
                    raise ValueError("Unknown schedule action")
            else:
                raise ValueError("Unknown collection")
            self._save(state)
            return self.snapshot()

    def _check_wallpaper(self, settings):
        if settings.get("wallpaper") and not (self.directory / "tv_wallpapers" / settings["wallpaper"].rsplit("/", 1)[-1]).is_file():
            raise ValueError("Wallpaper is unavailable on this server; upload the photo first")

    @staticmethod
    def _decode_wallpaper(encoded):
        if not isinstance(encoded, str) or len(encoded) > 5600000:
            raise ValueError("Choose a JPEG, PNG or WebP smaller than 4 MB")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid image data") from exc
        if len(data) > 4 * 1024 * 1024 or not image_type(data):
            raise ValueError("Choose a JPEG, PNG or WebP smaller than 4 MB")
        try:
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
                if image.width * image.height > 25000000 or max(image.size) > 8192:
                    raise ValueError("Wallpaper must be at most 25 megapixels and 8192 pixels per side")
                image.verify()
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
                image.load()
        except (OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise ValueError("The image is damaged or incomplete. Choose another photo.") from exc
        return data

    def _write_wallpaper(self, data):
        digest = hashlib.sha256(data).hexdigest()
        folder = self.directory / "tv_wallpapers"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / digest
        if not path.exists():
            fd, temporary = tempfile.mkstemp(dir=folder)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return "/api/tv/appearance/wallpaper/" + digest

    def wallpaper(self, encoded, profile_id=None, revision=None):
        data = self._decode_wallpaper(encoded)
        with self.lock:
            state = self._load()
            if revision is not None and (type(revision) is not int or revision != state["revision"]):
                raise RevisionConflict("Settings changed on another device. Load latest before uploading.")
            if not any(p["id"] == (profile_id or state["activeProfile"]) for p in state["profiles"]):
                raise ValueError("Unknown profile")
            return self.update({"wallpaper":self._write_wallpaper(data)}, profile_id, revision)


def image_type(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


STORE = AppearanceStore(Path(__file__).resolve().parent.parent / "config")


def send_bytes(handler, data, mime):
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(data)


def handle_get(handler, path):
    files = {"/tv-customize": ("customize.html", "text/html; charset=utf-8"),
             "/tv-ui/appearance.css": ("appearance.css", "text/css"),
             "/tv-ui/appearance.js": ("appearance.js", "text/javascript"),
             "/tv-ui/customize.js": ("customize.js", "text/javascript")}
    files.update({"/tv-ui/remote.js": ("remote.js", "text/javascript"),
                  "/tv-ui/visuals.js": ("visuals.js", "text/javascript"),
                  "/tv-ui/icons.css": ("icons.css", "text/css")})
    if path.startswith("/api/tv/appearance/export/"):
        preset_id = path.rsplit("/",1)[-1]
        preset = next((p for p in STORE.snapshot()["presets"] if p["id"] == preset_id), None)
        if not preset:
            handler._send_json(404, {"error":"Preset not found"})
        else:
            design = {"format":"netfelix-design", "version":1, "name":preset["name"], "settings":preset["settings"]}
            if preset["settings"].get("wallpaper"):
                photo = STORE.directory / "tv_wallpapers" / preset["settings"]["wallpaper"].rsplit("/",1)[-1]
                if not photo.is_file():
                    handler._send_json(404, {"error":"Design photo is unavailable"})
                    return True
                design["wallpaperImage"] = base64.b64encode(photo.read_bytes()).decode("ascii")
            data = json.dumps(design, ensure_ascii=False, indent=2).encode()
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Disposition", 'attachment; filename="netfelix-design.json"')
            handler.send_header("Content-Length", str(len(data)))
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            handler.wfile.write(data)
    elif path == "/api/tv/companion/commands":
        query = parse_qs(urlsplit(handler.path).query)
        try:
            after = int(query.get("after", ["0"])[0])
            handler._send_json(200, tv_companion.BUS.poll(after, query.get("epoch", [None])[0]))
        except (ValueError, TypeError):
            handler._send_json(400, {"error":"Invalid command cursor"})
    elif path == "/api/tv/companion/info":
        handler._send_json(200, {"service":"netfelix-companion", "version":1, "dashboardOnline":tv_companion.BUS.online()})
    elif path == "/tv-preview":
        import tv_dashboard
        markup = tv_dashboard.TV_DASHBOARD_TEMPLATE
        markup = markup.replace('<head>', '<head><script>window.NetFelixPreviewMode=true;</script>', 1)
        markup = markup.replace('<script src="/api/hls.min.js"></script>', '')
        values = {"WEATHER_TEMP": "24°", "CLOCK_TIME": "20:30", "DATE_STR": "Preview",
                  "PRAYER_TARGET_NAME": "Isha", "PRAYER_COUNTDOWN": "00:42:18", "PRAYER_REMAINING_SECS": "2538"}
        for key in re.findall(r"\{([A-Z_]+)\}", markup):
            markup = markup.replace("{" + key + "}", values.get(key, ""))
        send_bytes(handler, markup.encode(), "text/html; charset=utf-8")
    elif path.startswith("/tv-ui/scenes/"):
        name = path.rsplit("/", 1)[-1]
        if path != "/tv-ui/scenes/" + name or name.removesuffix(".svg") not in THEME_IDS or not name.endswith(".svg"):
            handler._send_json(404, {"error": "Scene not found"})
        else:
            send_bytes(handler, (UI_DIR / "scenes" / name).read_bytes(), "image/svg+xml")
    elif path == "/downloads/netfelix-companion.apk":
        apk = UI_DIR.parent.parent / "watch-remote/phone/build/outputs/apk/debug/phone-debug.apk"
        if not apk.is_file():
            handler._send_json(404, {"error": "Android companion has not been built on this server"})
        else:
            send_bytes(handler, apk.read_bytes(), "application/vnd.android.package-archive")
    elif path in files:
        name, mime = files[path]
        send_bytes(handler, (UI_DIR / name).read_bytes(), mime)
    elif path == "/api/tv/appearance":
        try:
            handler._send_json(200, STORE.snapshot())
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            handler._send_json(503, {"error": "Appearance settings could not be read"})
    elif path.startswith("/api/tv/appearance/wallpaper/"):
        digest = path.rsplit("/", 1)[-1]
        file = STORE.directory / "tv_wallpapers" / digest
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or not file.is_file():
            handler._send_json(404, {"error": "Wallpaper not found"})
        else:
            data = file.read_bytes()
            send_bytes(handler, data, image_type(data) or "application/octet-stream")
    else:
        return False
    return True


def handle_post(handler, path):
    if path not in ("/api/tv/appearance", "/api/tv/appearance/profile", "/api/tv/appearance/upload",
                    "/api/tv/appearance/trial", "/api/tv/appearance/presets", "/api/tv/appearance/schedules", "/api/tv/companion/control"):
        return False
    origin = handler.headers.get("Origin")
    if origin and urlsplit(origin).netloc != handler.headers.get("Host"):
        handler._send_json(403, {"error": "Use the NetFelix app or server page"})
        return True
    try:
        length = int(handler.headers.get("Content-Length", "0"))
        limit = 5700000 if path.endswith(("/upload", "/presets")) else 16384
        if not 0 < length <= limit:
            handler._send_json(413, {"error": "Request is too large or empty"})
            return True
        body = json.loads(handler.rfile.read(length))
        if not isinstance(body, dict):
            raise ValueError("Expected a settings object")
        if path == "/api/tv/companion/control":
            if body.get("target") == "dashboard":
                result = tv_companion.BUS.send(body)
            elif body.get("target") == "samsung":
                import samsung_tv
                if body.get("kind") == "text":
                    result = samsung_tv.send_text(body.get("text"))
                elif body.get("kind") == "key" and body.get("key") in tv_companion.NATIVE_KEYS:
                    result = samsung_tv.send_key(body["key"])
                else:
                    raise ValueError("Unsupported TV command")
            else:
                raise ValueError("Choose a control target")
        elif path.rsplit("/", 1)[-1] in ("trial", "presets", "schedules"):
            result = STORE.manage(path.rsplit("/", 1)[-1], body)
        elif path.endswith("/profile"):
            result = STORE.profile(body.get("action"), body.get("name"), body.get("profile"))
        elif path.endswith("/upload"):
            result = STORE.wallpaper(body.get("image"), body.get("profile"), body.get("revision"))
        else:
            result = STORE.update(body.get("patch"), body.get("profile"), body.get("revision"))
        handler._send_json(200, result)
    except RevisionConflict as exc:
        handler._send_json(409, {"error": str(exc)})
    except (ValueError, TypeError, UnicodeError) as exc:
        handler._send_json(400, {"error": str(exc)})
    except (OSError, KeyError, StopIteration):
        handler._send_json(503, {"error": "Appearance settings could not be saved"})
    return True
