"""Persistence, HTTP validation and multi-device conflict checks for TV settings."""
import base64
import concurrent.futures
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import http.client
import io
from unittest.mock import patch
from PIL import Image
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tv_settings

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNQcEgAAAFEAMELjZZCAAAAAElFTkSuQmCC")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _send_json(self, code, value):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not tv_settings.handle_get(self, self.path.split("?")[0]):
            self._send_json(404, {})

    def do_POST(self):
        if not tv_settings.handle_post(self, self.path):
            self._send_json(404, {})


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_store = tv_settings.STORE
        tv_settings.STORE = self.store = tv_settings.AppearanceStore(self.temp.name)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        tv_settings.STORE = self.old_store
        self.temp.cleanup()

    def request(self, path="/api/tv/appearance", value=None, headers=None):
        request = urllib.request.Request(self.base + path,
            data=None if value is None else json.dumps(value).encode(),
            headers=headers or {"Content-Type": "application/json"})
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read()
            return response.status, json.loads(data) if "json" in response.headers.get("Content-Type", "") else data

    def test_preferences_survive_store_restart(self):
        code, initial = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(len(initial["themes"]), 32)
        code, saved = self.request(value={"patch": {"theme": "ahly", "title": "أهلاً بالعائلة", "motion": False}, "revision": 0})
        self.assertEqual(code, 200)
        reloaded = tv_settings.AppearanceStore(self.temp.name).snapshot()
        self.assertEqual(reloaded["settings"]["theme"], "ahly")
        self.assertEqual(reloaded["settings"]["title"], "أهلاً بالعائلة")
        self.assertEqual(reloaded["revision"], saved["revision"])

    def test_invalid_settings_do_not_mutate_state(self):
        for patch in [{"theme": "unknown"}, {"theme": []}, {"motion": "false"}, {"title": "x"*65},
                      {"accent": "red;url(evil)"}, {"wallpaper": "https://example.com/a.jpg"},
                      {"favorites": ["netflix", "netflix"]}, {"favorites": ["unknown"]}, {"iconStyle": "missing"}, {"secret": "x"}]:
            with self.subTest(patch=patch):
                self.assertEqual(self.request(value={"patch": patch})[0], 400)
        self.assertEqual(self.store.snapshot()["revision"], 0)

    def test_profiles_keep_independent_preferences(self):
        self.store.update({"theme": "ahly", "favorites": ["youtube", "jellyfin"]})
        child = self.store.profile("create", "Kids")
        self.assertEqual(child["settings"]["theme"], "night")
        self.store.update({"theme": "emerald"})
        family = self.store.profile("select", profile_id="family")
        self.assertEqual(family["settings"]["theme"], "ahly")
        self.assertEqual(family["settings"]["favorites"], ["youtube", "jellyfin"])
        for number in range(4):
            self.store.profile("create", str(number))
        with self.assertRaises(ValueError):
            self.store.profile("create", "Seventh")

    def test_concurrent_writes_preserve_unrelated_fields(self):
        with concurrent.futures.ThreadPoolExecutor() as pool:
            list(pool.map(self.store.update, [{"theme": "ahly"}, {"title": "Hello"}, {"glow": False}]))
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot["revision"], 3)
        self.assertEqual(snapshot["settings"]["theme"], "ahly")
        self.assertEqual(snapshot["settings"]["title"], "Hello")
        self.assertFalse(snapshot["settings"]["glow"])

    def test_stale_client_cannot_overwrite_new_settings(self):
        self.request(value={"patch": {"theme": "ahly"}, "revision": 0})
        self.assertEqual(self.request(value={"patch": {"theme": "blue"}, "revision": 0})[0], 409)
        self.assertEqual(self.store.snapshot()["settings"]["theme"], "ahly")

    def test_wallpaper_upload_fetch_and_reset(self):
        code, value = self.request("/api/tv/appearance/upload", {"image": base64.b64encode(PNG).decode(), "revision": 0})
        self.assertEqual(code, 200)
        path = value["settings"]["wallpaper"]
        self.assertEqual(self.request(path), (200, PNG))
        self.store.update({"wallpaper": ""})
        self.assertEqual(self.store.snapshot()["settings"]["wallpaper"], "")
        self.assertEqual(self.request("/api/tv/appearance/upload", {"image": "not base64"})[0], 400)
        self.assertEqual(self.request("/api/tv/appearance/upload", {"image": base64.b64encode(b"<svg/>").decode()})[0], 400)

    def test_bad_json_cross_origin_and_traversal(self):
        self.assertEqual(self.request(value=[], headers={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request(value={"patch": {}}, headers={"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("/api/tv/appearance/wallpaper/../../tv_appearance.json")[0], 404)
        self.assertEqual(self.request("/tv-ui/../../tv_settings.py")[0], 404)

    def test_corrupt_file_is_not_overwritten(self):
        self.store.directory.mkdir(exist_ok=True)
        self.store.path.write_text("broken")
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.request(value={"patch": {"theme": "ahly"}})[0], 400)
        self.assertEqual(self.store.path.read_text(), "broken")

    def test_signature_only_or_truncated_images_are_rejected(self):
        for data in [b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF0000WEBP"]:
            with self.subTest(data=data):
                code, _ = self.request("/api/tv/appearance/upload", {"image": base64.b64encode(data).decode()})
                self.assertEqual(code, 400)
        self.assertEqual(self.store.snapshot()["revision"], 0)

    def test_upload_to_unknown_profile_does_not_store_orphan_image(self):
        self.assertEqual(self.request("/api/tv/appearance/upload", {"image": base64.b64encode(PNG).decode(), "profile": "missing"})[0], 400)
        folder = Path(self.temp.name) / "tv_wallpapers"
        self.assertFalse(folder.exists() and list(folder.iterdir()))

    def test_failed_atomic_save_preserves_previous_state(self):
        self.store.update({"title": "Saved title"})
        previous = self.store.path.read_bytes()
        with patch.object(tv_settings.os, "replace", side_effect=OSError("disk unavailable")):
            self.assertEqual(self.request(value={"patch": {"title": "Lost write"}})[0], 503)
        self.assertEqual(self.store.path.read_bytes(), previous)
        self.assertEqual(list(Path(self.temp.name).glob(".tv-appearance-*")), [])

    def test_invalid_json_length_and_cross_origin_requests(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request("POST", "/api/tv/appearance", body=b"{broken", headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        response.read()
        connection.close()
        for length in ["0", "17000", "-1", "not-a-number"]:
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
            connection.request("POST", "/api/tv/appearance", body=b"", headers={"Content-Length": length})
            response = connection.getresponse()
            self.assertIn(response.status, (400, 413))
            response.read()
            connection.close()
        self.assertEqual(self.request(value={"patch": {}}, headers={"Origin": self.base})[0], 200)
        self.assertEqual(self.request(value={"patch": {}}, headers={"Origin": "null"})[0], 403)

    def test_stale_upload_and_missing_wallpaper_leave_state_unchanged(self):
        self.store.update({"theme": "ahly"})
        self.assertEqual(self.request("/api/tv/appearance/upload", {"image": base64.b64encode(PNG).decode(), "revision": 0})[0], 409)
        self.assertEqual(self.request(value={"patch": {"wallpaper": "/api/tv/appearance/wallpaper/" + "a"*64}})[0], 400)
        self.assertEqual(self.store.snapshot()["revision"], 1)

    def test_profile_errors_leave_current_profile_intact(self):
        for payload in [{"action": "create", "name": ""}, {"action": "create", "name": "x"*25},
                        {"action": "create", "name": "bad\nname"}, {"action": "select", "profile": "missing"},
                        {"action": "delete", "profile": "family"}]:
            self.assertEqual(self.request("/api/tv/appearance/profile", payload)[0], 400)
        self.assertEqual(self.store.snapshot()["activeProfile"], "family")

    def test_editing_inactive_profile_does_not_change_selection(self):
        child = self.store.profile("create", "Kids")["activeProfile"]
        self.store.profile("select", profile_id="family")
        self.store.update({"theme": "emerald"}, profile_id=child)
        self.assertEqual(self.store.snapshot()["activeProfile"], "family")
        self.assertEqual(self.store.profile("select", profile_id=child)["settings"]["theme"], "emerald")

    def test_defaults_are_deep_copied_between_profiles(self):
        snapshot = self.store.snapshot()
        snapshot["settings"]["favorites"].clear()
        self.assertEqual(len(self.store.snapshot()["settings"]["favorites"]), 8)

    def test_image_size_and_dimensions_are_limited(self):
        image = io.BytesIO()
        Image.new("RGB", (8193, 1), (0, 0, 0)).save(image, format="PNG")
        for data in [image.getvalue(), b"\x89PNG\r\n\x1a\n" + b"x"*(4*1024*1024)]:
            self.assertEqual(self.request("/api/tv/appearance/upload", {"image": base64.b64encode(data).decode()})[0], 400)
        self.assertEqual(self.store.snapshot()["revision"], 0)


if __name__ == "__main__":
    unittest.main()
