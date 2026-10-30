"""End-to-end appearance checks using an isolated HTTP server and real Chromium.

Run: python3 -m unittest discover -s tests -p test_tv_appearance_browser.py -v
No household settings, TV keys, downloads or real media services are changed.
"""
import base64
import io
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer

from playwright.sync_api import sync_playwright, expect
from PIL import Image
from test_tv_appearance import Handler
import tv_settings
import tv_dashboard


class BrowserFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = tv_settings.STORE
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        template = tv_dashboard.TV_DASHBOARD_TEMPLATE
        values = {"PRAYER_REMAINING_SECS": "3600", "PRAYER_TARGET_NAME": "Fajr", "CLOCK_TIME": "08:00",
                  "DATE_STR": "Thu, Oct 29", "WEATHER_TEMP": "24°"}
        for key in re.findall(r"\{([A-Z_]+)\}", template):
            template = template.replace("{" + key + "}", values.get(key, ""))

        class PreviewHandler(Handler):
            def do_GET(self):
                path = self.path.split("?")[0]
                if path == "/tv-dashboard":
                    tv_settings.send_bytes(self, template.encode(), "text/html")
                elif path == "/tv-customize":
                    tv_settings.handle_get(self, path)
                else:
                    super().do_GET()

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), PreviewHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.browser.close()
        cls.playwright.stop()
        tv_settings.STORE = cls.original

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="nf-feature-test-")
        tv_settings.STORE = tv_settings.AppearanceStore(self.folder.name)
        self.context = self.browser.new_context(viewport={"width": 1920, "height": 1080})
        self.context.set_default_timeout(8000)
        self.context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(self.base) else route.abort())
        self.errors = []
        self.context.on("page", lambda page: page.on("pageerror", lambda error: self.errors.append(str(error))))
        self.tv = self.context.new_page()
        self.tv.goto(self.base + "/tv-dashboard")
        self.tv.wait_for_selector("body.nf-ready")
        self.phone = self.context.new_page()
        self.phone.set_viewport_size({"width": 390, "height": 844})
        self.phone.goto(self.base + "/tv-customize")
        self.phone.wait_for_selector("#editor:not([hidden])")
        self.preview = self.phone.frame_locator('#tv-preview')
        self.preview.locator('body.nf-ready').wait_for()

    def tearDown(self):
        self.context.close()
        self.folder.cleanup()
        self.assertEqual(self.errors, [], "Uncaught browser errors")

    def save(self):
        with self.phone.expect_response(lambda response: response.url.endswith("/api/tv/appearance") and response.request.method == "POST") as response:
            self.phone.locator("#save").click()
        self.assertEqual(response.value.status, 200)
        expect(self.phone.locator("#status")).to_contain_text("Saved.")
        self.tv.evaluate("document.dispatchEvent(new Event('visibilitychange'))")

    def update(self, patch):
        snapshot = tv_settings.STORE.update(patch)
        self.tv.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        self.tv.wait_for_function("(s)=>JSON.stringify(window.NetFelixAppearance)===JSON.stringify(s)", arg=snapshot["settings"])

    def test_all_32_palettes_apply_preview_and_persist(self):
        for theme in tv_settings.THEMES:
            with self.subTest(theme=theme["id"]):
                self.phone.locator('[data-theme="' + theme["id"] + '"]').click()
                expect(self.phone.locator('#preview')).to_have_attribute('data-rendered-theme',theme['id'])
                self.assertIn(theme['artwork'],self.preview.locator('body').evaluate("e=>e.style.getPropertyValue('--nf-artwork')"))
                self.assertEqual(self.preview.locator('.tvm-bottom-dock svg').count(),9)
                self.assertEqual(self.phone.locator("#preview").evaluate("e=>getComputedStyle(e).backgroundColor"),
                                 self.phone.evaluate("color=>{let e=document.createElement('i');e.style.color=color;document.body.append(e);let c=getComputedStyle(e).color;e.remove();return c}", theme["secondary"]))
                self.save()
                self.tv.wait_for_function("id=>document.body.dataset.nfTheme===id", arg=theme["id"])
                self.assertEqual(self.tv.locator("body").evaluate("e=>e.style.getPropertyValue('--nf-accent')"), theme["primary"])
                self.assertEqual(tv_settings.AppearanceStore(self.folder.name).snapshot()["settings"]["theme"], theme["id"])

    def test_category_filters_cover_every_theme_exactly_once(self):
        seen = []
        filters = self.phone.locator(".theme-filter").all_text_contents()
        for name in filters[1:]:
            self.phone.get_by_role("button", name=name, exact=True).click()
            seen.extend(self.phone.locator(".theme").evaluate_all("es=>es.map(e=>e.dataset.theme)"))
        self.assertEqual(len(seen), 32)
        self.assertEqual(set(seen), tv_settings.THEME_IDS)

    def test_every_setting_toggle_and_clock_format(self):
        for field, attribute in [("motion", "motion"), ("blur", "blur"), ("glow", "glow"),
                                 ("showPrayer", "prayer"), ("showWeather", "weather")]:
            for value in [False, True]:
                with self.subTest(field=field, value=value):
                    self.phone.locator("#" + field).set_checked(value)
                    self.save()
                    expect(self.tv.locator("body")).to_have_attribute("data-nf-" + attribute, str(value).lower())
                    if field == "showPrayer":
                        self.assertEqual(self.tv.locator(".hero-prayer-widget").is_visible(), value)
                    if field == "showWeather":
                        self.assertEqual(self.tv.locator(".tvm-status-pills > :first-child").is_visible(), value)
                    if field == "blur" and not value:
                        self.assertEqual(self.tv.locator(".tvm-logo-badge").evaluate("e=>getComputedStyle(e).backdropFilter"), "none")
                    if field == "glow" and not value:
                        self.tv.wait_for_function("getComputedStyle(document.querySelector('.hero-cta-btn')).boxShadow==='none'")
                    if field == "motion" and not value:
                        self.assertEqual(self.tv.locator(".focusable").first.evaluate("e=>getComputedStyle(e).transitionDuration"), "0s")
        for value in [True, False]:
            self.phone.locator("#clock24").set_checked(value)
            self.save()
            self.tv.wait_for_function("v=>window.NetFelixAppearance.clock24===v", arg=value)
            self.tv.evaluate("updateTimers()")
            clock = self.tv.locator("#live-clock-time").inner_text()
            self.assertEqual(bool(re.search(r"AM|PM", clock)), not value)

    def test_accent_override_and_restore_theme_color(self):
        self.phone.locator("#accent").fill("#ab34de")
        self.save()
        self.tv.wait_for_function("document.body.style.getPropertyValue('--nf-accent')==='#ab34de'")
        self.phone.locator('[data-theme="ahly"]').click()
        self.save()
        self.assertEqual(tv_settings.STORE.snapshot()["settings"]["accent"], "#ab34de")
        self.phone.locator("#theme-accent").check()
        self.save()
        self.tv.wait_for_function("document.body.style.getPropertyValue('--nf-accent')==='#ff5470'")

    def test_text_sizes_change_both_preview_and_tv(self):
        sizes = []
        for size in ["small", "normal", "large"]:
            self.phone.locator("#textSize").select_option(size)
            self.preview.locator('body').evaluate("(e,value)=>new Promise(resolve=>{const check=()=>window.NetFelixAppearance.textSize===value?resolve():setTimeout(check,20);check()})",size)
            preview_size = self.preview.locator(".hero-headline").evaluate("e=>parseFloat(getComputedStyle(e).fontSize)")
            self.save()
            self.tv.wait_for_function("v=>window.NetFelixAppearance.textSize===v", arg=size)
            tv_size = self.tv.locator(".hero-headline").evaluate("e=>parseFloat(getComputedStyle(e).fontSize)")
            sizes.append((preview_size, tv_size))
        self.assertTrue(sizes[0][1] < sizes[1][1] < sizes[2][1], sizes)
        self.assertTrue(sizes[0][0] < sizes[1][0] < sizes[2][0], sizes)
        self.assertEqual(sizes[0][0],sizes[0][1])
        self.assertEqual(sizes[2][0],sizes[2][1])

    def test_preview_does_not_save_and_shares_actual_tv_icons(self):
        initial = tv_settings.STORE.snapshot()
        self.phone.locator('[data-theme="ahly"]').click()
        self.phone.locator('#title').fill('See it before applying')
        expect(self.preview.locator('.hero-headline')).to_have_text('See it before applying')
        self.assertEqual(self.phone.evaluate('document.activeElement.id'),'title','Preview must not steal editor focus')
        self.assertEqual(tv_settings.STORE.snapshot()['revision'],initial['revision'])
        self.assertEqual(self.tv.locator('body').get_attribute('data-nf-theme'),'night')
        self.phone.locator('#iconStyle').select_option('solid')
        expect(self.preview.locator('body')).to_have_attribute('data-nf-icons','solid')
        self.save()
        expect(self.tv.locator('body')).to_have_attribute('data-nf-icons','solid')
        for id in ['jellyfin','iptv','youtube','netflix','prayer','radio','matches','search']:
            selector = '[data-nf-app="'+id+'"] svg'
            self.assertEqual(self.tv.locator(selector).evaluate('e=>e.outerHTML'),self.preview.locator(selector).evaluate('e=>e.outerHTML'))
        self.assertEqual(self.tv.locator('.hero-headline').inner_text(),self.preview.locator('.hero-headline').inner_text())

    def test_all_icon_styles_preview_apply_and_survive_reload(self):
        treatments=[]
        for style in ['glass','solid','outline','theme']:
            self.phone.locator('#iconStyle').select_option(style)
            expected = 'glass' if style=='theme' else style
            expect(self.preview.locator('body')).to_have_attribute('data-nf-icons',expected)
            self.assertEqual(self.phone.locator('#icon-samples svg').count(),5)
            self.save()
            expect(self.tv.locator('body')).to_have_attribute('data-nf-icons',expected)
            computed="""e=>{
                const tile=getComputedStyle(e),icon=getComputedStyle(e.querySelector('.nf-app-icon'));
                return [tile.backgroundImage,tile.backgroundColor,tile.borderRadius,icon.backgroundColor,icon.color];
            }"""
            expected_treatment=self.preview.locator('[data-nf-app="iptv"]').evaluate(computed)
            self.tv.wait_for_function("""expected=>{
                const e=document.querySelector('[data-nf-app="iptv"]'), tile=getComputedStyle(e), icon=getComputedStyle(e.querySelector('.nf-app-icon'));
                return JSON.stringify([tile.backgroundImage,tile.backgroundColor,tile.borderRadius,icon.backgroundColor,icon.color])===JSON.stringify(expected);
            }""",arg=expected_treatment)
            tv_treatment=self.tv.locator('[data-nf-app="iptv"]').evaluate(computed)
            self.assertEqual(tv_treatment,self.preview.locator('[data-nf-app="iptv"]').evaluate(computed))
            treatments.append(json.dumps(tv_treatment))
            self.assertEqual(tv_settings.AppearanceStore(self.folder.name).snapshot()['settings']['iconStyle'],style)
        self.assertEqual(len(set(treatments[:3])),3,'Glass, Colorful and Outline must look different')
        self.assertEqual(treatments[0],treatments[3],'Midnight theme default should be Glass')
        self.tv.reload();self.tv.wait_for_selector('body.nf-ready')
        expect(self.tv.locator('body')).to_have_attribute('data-nf-icons','glass')

    def test_expand_preview_scales_real_screen_and_escape_closes_only_preview(self):
        before = self.phone.locator('#tv-preview').evaluate('e=>e.getBoundingClientRect().width')
        self.phone.locator('#expand-preview').click()
        expect(self.phone.locator('#expand-preview')).to_have_attribute('aria-expanded','true')
        self.assertTrue(self.phone.locator('#tv-preview').evaluate('e=>e.getBoundingClientRect().width')>0)
        self.phone.keyboard.press('Escape')
        expect(self.phone.locator('#expand-preview')).to_have_attribute('aria-expanded','false')
        self.assertTrue(self.phone.url.endswith('/tv-customize'))

    def test_scene_assets_are_unique_and_thumbnails_have_styled_icons(self):
        self.assertEqual(len({theme['artwork'] for theme in tv_settings.THEMES}),32)
        artwork=[]
        for theme in tv_settings.THEMES:
            response=self.context.request.get(self.base+theme['artwork'])
            self.assertEqual(response.status,200)
            self.assertEqual(response.headers['content-type'],'image/svg+xml')
            artwork.append(response.body())
        self.assertEqual(len(set(artwork)),32)
        self.assertEqual(self.phone.locator('.theme-shot').count(),32)
        self.assertEqual(self.phone.locator('.theme-shot svg').count(),128)

    def test_arabic_long_text_and_phone_tv_layouts(self):
        self.update({"title": "عائلتنا تشاهد معاً", "subtitle": "س" * 180, "textSize": "large"})
        self.assertEqual(self.tv.locator(".hero-headline").get_attribute("dir"), "auto")
        for width, height in [(1280,720), (1920,1080), (3840,2160)]:
            self.tv.set_viewport_size({"width":width,"height":height})
            self.assertTrue(self.tv.evaluate("document.documentElement.scrollWidth <= innerWidth"), str(width))
        for width in [320,390,768]:
            self.phone.set_viewport_size({"width":width,"height":844})
            self.assertTrue(self.phone.evaluate("document.documentElement.scrollWidth <= innerWidth"), str(width))

    def test_long_custom_text_does_not_overlap_dock(self):
        self.tv.set_viewport_size({"width":1280,"height":720})
        self.update({"title":"W"*64,"subtitle":"W"*180,"textSize":"large"})
        positions = self.tv.evaluate("""() => ({
            buttons:document.querySelector('.hero-btn-row').getBoundingClientRect().bottom,
            dock:document.querySelector('.tvm-bottom-dock').getBoundingClientRect().top
        })""")
        self.assertLessEqual(positions["buttons"],positions["dock"],positions)

    def test_upload_all_formats_and_reject_invalid_or_oversized_files(self):
        for fmt, mime in [("PNG","image/png"), ("JPEG","image/jpeg"), ("WEBP","image/webp")]:
            image = io.BytesIO()
            Image.new("RGB", (20,20), (30,50,90)).save(image,format=fmt)
            data = image.getvalue()
            self.phone.locator("#wallpaper").set_input_files({"name":"photo."+fmt.lower(),"mimeType":mime,"buffer":data})
            expect(self.phone.locator("#status")).to_contain_text("Photo applied")
            snapshot = tv_settings.STORE.snapshot()
            response = self.context.request.get(self.base+snapshot["settings"]["wallpaper"])
            self.assertEqual(response.headers["content-type"],mime)
            self.assertEqual(response.body(),data)
            self.assertTrue(self.phone.evaluate("url=>new Promise(resolve=>{let i=new Image();i.onload=()=>resolve(true);i.onerror=()=>resolve(false);i.src=url})",snapshot["settings"]["wallpaper"]))
        revision = tv_settings.STORE.snapshot()["revision"]
        for name,mime,data in [("bad.svg","image/svg+xml",b"<svg/>"), ("big.png","image/png", b"x"*(4*1024*1024+1))]:
            self.phone.locator("#wallpaper").set_input_files({"name":name,"mimeType":mime,"buffer":data})
            expect(self.phone.locator("#status")).to_contain_text("Choose a JPEG")
        self.assertEqual(tv_settings.STORE.snapshot()["revision"],revision)
        self.phone.locator("#clear-wallpaper").click()
        self.save()
        self.tv.wait_for_function("document.body.style.getPropertyValue('--nf-wallpaper')==='none'")

    def test_empty_and_reordered_dock_keeps_appearance_accessible(self):
        for label in tv_settings.APPS.values():
            self.phone.get_by_role("checkbox",name="Show " + label + " in dock").uncheck()
        self.save()
        self.tv.wait_for_function("document.querySelectorAll('[data-nf-app]').length===0")
        expect(self.tv.get_by_role("button",name="✦ Appearance",exact=True)).to_be_visible()
        self.phone.get_by_role("checkbox",name="Show YouTube in dock").check()
        self.phone.get_by_role("checkbox",name="Show Netflix in dock").check()
        self.phone.get_by_role("button",name="Move Netflix up",exact=True).click()
        self.save()
        self.tv.wait_for_function("document.querySelector('[data-nf-app]') && document.querySelector('[data-nf-app]').dataset.nfApp==='netflix'")

    def test_dirty_draft_conflict_and_recovery(self):
        self.phone.locator("#title").fill("My unsaved draft")
        tv_settings.STORE.update({"title":"Another device", "theme":"emerald"})
        self.phone.locator("#save").click()
        expect(self.phone.locator("#status")).to_contain_text("Settings changed")
        self.assertEqual(self.phone.locator("#title").input_value(),"My unsaved draft")
        self.assertEqual(tv_settings.STORE.snapshot()["settings"]["title"],"Another device")
        self.phone.once("dialog",lambda dialog:dialog.accept())
        self.phone.locator("#reload").click()
        expect(self.phone.locator("#title")).to_have_value("Another device")

    def test_offline_save_retains_draft_then_recovers(self):
        self.phone.locator("#title").fill("Keep this draft")
        self.phone.route("**/api/tv/appearance", lambda route:route.abort())
        self.phone.locator("#save").click()
        expect(self.phone.locator("#status")).to_have_class("error")
        self.assertEqual(self.phone.locator("#title").input_value(),"Keep this draft")
        expect(self.phone.locator("#save")).to_be_enabled()
        self.phone.unroute("**/api/tv/appearance")
        self.save()
        self.assertEqual(tv_settings.STORE.snapshot()["settings"]["title"],"Keep this draft")

    def test_slow_save_unlocks_controls_without_losing_draft(self):
        self.phone.evaluate("""() => {
            const schedule = window.setTimeout.bind(window);
            window.setTimeout = (fn,delay,...args) => schedule(fn,delay===12000 ? 250 : delay,...args);
        }""")
        waiting = []
        self.phone.route("**/api/tv/appearance",lambda route:waiting.append(route) if route.request.method == "POST" else route.continue_())
        self.phone.locator("#title").fill("Keep my slow request")
        self.phone.locator("#save").click()
        expect(self.phone.locator("#save")).to_be_disabled()
        expect(self.phone.locator("#save")).to_be_enabled()
        expect(self.phone.locator("#status")).to_contain_text("timed out")
        self.assertEqual(self.phone.locator("#title").input_value(),"Keep my slow request")
        for route in waiting:
            route.fulfill(status=503,content_type="application/json",body='{"error":"unavailable"}')

    def test_profiles_and_reset_are_isolated(self):
        self.phone.locator('[data-theme="ahly"]').click()
        self.save()
        self.phone.locator("#new-profile").fill("Kids")
        self.phone.locator("#create-profile").click()
        expect(self.phone.locator("#status")).to_contain_text("Profile created")
        self.phone.locator('[data-theme="emerald"]').click()
        self.save()
        self.phone.locator("#reset").click()
        self.save()
        self.assertEqual(tv_settings.STORE.snapshot()["settings"],tv_settings.DEFAULTS)
        self.phone.locator("#profile").select_option("family")
        expect(self.phone.locator("#status")).to_contain_text("Profile selected")
        self.assertEqual(tv_settings.STORE.snapshot()["settings"]["theme"],"ahly")

    def test_tv_remote_can_toggle_checkbox_and_return(self):
        self.phone.goto(self.base+"/tv-customize?tv=1")
        self.phone.wait_for_selector("#editor:not([hidden])")
        motion = self.phone.locator("#motion")
        motion.focus()
        self.phone.keyboard.press("Enter")
        expect(motion).not_to_be_checked()
        self.phone.once("dialog",lambda dialog:dialog.accept())
        self.phone.keyboard.press("Escape")
        self.phone.wait_for_url("**/tv-dashboard")

    def test_controls_keep_focus_after_filtering_or_reordering(self):
        self.phone.get_by_role("button",name="Simple",exact=True).click()
        self.assertEqual(self.phone.evaluate("document.activeElement.textContent"),"Simple")
        self.phone.get_by_role("button",name="Move Live TV up",exact=True).click()
        self.assertIn("Live TV",self.phone.evaluate("document.activeElement.getAttribute('aria-label') || ''"))

    def test_clean_editor_clears_connection_error_after_recovery(self):
        self.phone.route("**/api/tv/appearance", lambda route:route.abort())
        expect(self.phone.locator("#status")).to_have_class("error", timeout=7000)
        self.phone.unroute("**/api/tv/appearance")
        expect(self.phone.locator("#status")).not_to_have_class("error", timeout=7000)

    def test_existing_dashboard_actions_and_error_feedback(self):
        launches = []
        def launch(route):
            launches.append(route.request.post_data_json["app"])
            route.fulfill(status=200,content_type="application/json",body=json.dumps({"success":True}))
        self.tv.route("**/api/tv/launch_app", launch)
        for app in ["jellyfin","iptv","youtube","netflix"]:
            with self.tv.expect_response("**/api/tv/launch_app"):
                self.tv.locator('[data-nf-app="'+app+'"]').click()
        self.assertEqual(launches,["jellyfin","iptv","youtube","netflix"])
        self.tv.unroute("**/api/tv/launch_app")
        self.tv.route("**/api/tv/launch_app",lambda route:route.fulfill(status=200,content_type="application/json",body=json.dumps({"success":False,"error":"TV is offline"})))
        self.tv.locator('[data-nf-app="youtube"]').click()
        expect(self.tv.locator("#toast-text")).to_contain_text("TV is offline")

    def test_prayer_search_request_and_screensaver(self):
        self.tv.locator('[data-nf-app="prayer"]').click()
        expect(self.tv.locator("#prayer-hub-modal")).to_be_visible()
        self.tv.keyboard.press("Escape")
        expect(self.tv.locator("#prayer-hub-modal")).not_to_be_visible()
        self.tv.locator('[data-nf-app="search"]').click()
        self.tv.locator("#sd-query-input").press_sequentially("Dune")
        captured = []
        def requested(route):
            captured.append(route.request.post_data_json)
            route.fulfill(status=200,content_type="application/json",body='{"success":true}')
        self.tv.route("**/api/request",requested)
        with self.tv.expect_response("**/api/request"):
            self.tv.locator("#sd-query-input").press("Enter")
        self.assertEqual(captured,[{"query":"Dune"}])
        self.tv.wait_for_function("getComputedStyle(document.getElementById('search-downloader-modal')).display==='none'")
        self.tv.evaluate("triggerScreensaver()")
        expect(self.tv.locator("#screensaver-overlay")).to_be_visible()
        self.tv.keyboard.press("ArrowRight")
        expect(self.tv.locator("#screensaver-overlay")).not_to_be_visible()

    def test_failed_media_request_keeps_search_and_title(self):
        self.tv.locator('[data-nf-app="search"]').click()
        self.tv.locator("#sd-query-input").fill("My title")
        self.tv.route("**/api/request",lambda route:route.fulfill(status=503,content_type="application/json",body='{"error":"Request service unavailable"}'))
        self.tv.locator("#sd-query-input").press("Enter")
        expect(self.tv.locator("#toast-text")).to_contain_text("Request service unavailable")
        expect(self.tv.locator("#search-downloader-modal")).to_be_visible()
        self.assertEqual(self.tv.locator("#sd-query-input").input_value(),"My title")

    def test_player_modal_and_radio_controls_without_external_streams(self):
        self.tv.evaluate("playChannel('/fixture-video.mp4','Test channel')")
        expect(self.tv.locator("#player-modal")).to_be_visible()
        self.assertEqual(self.tv.locator("#player-title").inner_text(),"Test channel")
        self.tv.keyboard.press("Escape")
        expect(self.tv.locator("#player-modal")).not_to_be_visible()
        self.assertIsNone(self.tv.locator("#tv-video-player").get_attribute("src"))
        # Emulate audio success without sending any third-party network request.
        self.tv.evaluate("""() => {
            const audio=document.getElementById('quran-audio-player'); let stopped=true;
            Object.defineProperty(audio,'paused',{get:()=>stopped});
            audio.play=()=>{stopped=false;return Promise.resolve()};audio.pause=()=>{stopped=true};
        }""")
        self.tv.locator('[data-nf-app="radio"]').click()
        expect(self.tv.locator("#audio-bar")).to_be_visible()
        self.tv.locator('[data-nf-app="radio"]').click()
        expect(self.tv.locator("#audio-bar")).not_to_be_visible()

    def test_temporary_preview_keep_restore_and_unsaved_layout(self):
        self.phone.locator('#tileSize').select_option('large')
        self.phone.locator('#menuPosition').select_option('right')
        self.phone.locator('[data-theme="ahly"]').click()
        expect(self.preview.locator('body')).to_have_attribute('data-nf-menu','right')
        self.assertEqual(tv_settings.STORE.snapshot()['settings']['theme'],'night')
        self.phone.locator('#try-tv').click()
        expect(self.tv.locator('body')).to_have_attribute('data-nf-theme','ahly')
        expect(self.tv.locator('body')).to_have_attribute('data-nf-tiles','large')
        self.phone.locator('#restore-trial').click()
        expect(self.tv.locator('body')).to_have_attribute('data-nf-theme','night')
        self.phone.locator('#try-tv').click()
        self.phone.locator('#keep-trial').click()
        expect(self.phone.locator('#status')).to_have_text('Done.')
        self.assertEqual(tv_settings.STORE.snapshot()['settings']['theme'],'ahly')
        self.assertIsNone(tv_settings.STORE.snapshot()['trial'])

    def test_preset_export_duplicate_import_and_scheduled_design(self):
        self.phone.locator('[data-theme="ahly"]').click()
        self.phone.locator('#preset-name').fill('Match night')
        self.phone.locator('#save-preset').click()
        expect(self.phone.locator('#preset-list option')).to_have_count(1)
        self.phone.locator('#preset-name').fill('Match copy')
        self.phone.locator('#duplicate-preset').click()
        expect(self.phone.locator('#preset-list option')).to_have_count(2)
        with self.phone.expect_download() as info:
            self.phone.locator('#export-preset').click()
        design = json.loads(Path(info.value.path()).read_text())
        self.assertEqual(design['settings']['theme'],'ahly')
        self.phone.locator('#import-preset').set_input_files({'name':'design.json','mimeType':'application/json','buffer':json.dumps(design).encode()})
        expect(self.phone.locator('#preset-list option')).to_have_count(3)
        self.phone.locator('#schedule-start').fill('18:00')
        self.phone.locator('#schedule-end').fill('06:00')
        self.phone.locator('#add-schedule').click()
        expect(self.phone.locator('#schedule-list')).to_contain_text('18:00–06:00')
        self.phone.locator('#schedule-list button').click()
        expect(self.phone.locator('#schedule-list')).to_be_empty()
        self.assertEqual(tv_settings.STORE.snapshot()['settings']['theme'],'night')

    def test_phone_keyboard_and_remote_back_on_dashboard(self):
        # Polling starts the command session before phone input can be accepted.
        self.tv.wait_for_function("() => document.body.classList.contains('nf-ready')")
        self.phone.locator('#remote-text').fill('فيلم من الهاتف')
        self.phone.locator('#send-text').click()
        expect(self.tv.locator('#sd-query-input')).to_have_value('فيلم من الهاتف')
        expect(self.tv.locator('#search-downloader-modal')).to_be_visible()
        self.phone.get_by_role('button',name='Remote RETURN',exact=True).click()
        expect(self.tv.locator('#search-downloader-modal')).not_to_be_visible()
        self.assertEqual(tv_settings.STORE.snapshot()['revision'],0)


    def test_preview_timeout_restores_visible_tv_without_phone(self):
        self.phone.locator('[data-theme="ahly"]').click()
        self.phone.locator('#try-tv').click()
        expect(self.tv.locator('body')).to_have_attribute('data-nf-theme','ahly')
        expect(self.tv.locator('#nf-trial-badge')).to_be_visible()
        self.phone.close()
        expect(self.tv.locator('body')).to_have_attribute('data-nf-theme','night',timeout=35000)
        expect(self.tv.locator('#nf-trial-badge')).not_to_be_visible()
        self.assertEqual(tv_settings.STORE.snapshot()['settings']['theme'],'night')

    def test_remote_media_and_navigation_commands(self):
        self.tv.evaluate("""() => {
            const media=document.getElementById('tv-video-player'); window.remotePaused=true;
            Object.defineProperty(media,'paused',{get:()=>window.remotePaused});
            Object.defineProperty(media,'duration',{get:()=>100}); media.currentTime=30;
            media.play=()=>{window.remotePaused=false;return Promise.resolve()};
            media.pause=()=>{window.remotePaused=true};
            document.getElementById('player-modal').style.display='flex';
        }""")
        self.phone.get_by_role('button',name='Remote PLAY',exact=True).click()
        self.tv.wait_for_function('() => window.remotePaused === false')
        self.phone.get_by_role('button',name='Remote FF',exact=True).click()
        self.tv.wait_for_function("() => document.getElementById('tv-video-player').currentTime === 40")
        self.phone.get_by_role('button',name='Remote REWIND',exact=True).click()
        self.tv.wait_for_function("() => document.getElementById('tv-video-player').currentTime === 30")
        self.phone.get_by_role('button',name='Remote PAUSE',exact=True).click()
        self.tv.wait_for_function('() => window.remotePaused === true')
        self.phone.get_by_role('button',name='Remote STOP',exact=True).click()
        self.tv.wait_for_function("() => document.getElementById('tv-video-player').currentTime === 0")
        self.phone.get_by_role('button',name='Remote HOME',exact=True).click()
        expect(self.tv.locator('#player-modal')).not_to_be_visible()
        self.phone.get_by_role('button',name='Remote DOWN',exact=True).click()
        self.tv.wait_for_timeout(600)
        self.phone.get_by_role('button',name='Remote ENTER',exact=True).click()

    def test_side_menu_layout_and_focus_follow_position(self):
        self.phone.locator('#menuPosition').select_option('right')
        self.save()
        expect(self.tv.locator('body')).to_have_attribute('data-nf-menu','right')
        sidebar = self.tv.locator('.left-vertical-dock').bounding_box()
        main = self.tv.locator('.main-content').bounding_box()
        self.assertGreater(sidebar['x'],main['x']+main['width']-1)
        self.tv.locator('.left-vertical-dock .focusable').first.focus()
        self.tv.keyboard.press('ArrowLeft')
        self.assertTrue(self.tv.evaluate("() => !!document.activeElement.closest('.main-content')"))
        self.phone.locator('#menuPosition').select_option('hidden')
        self.save()
        expect(self.tv.locator('.left-vertical-dock')).not_to_be_visible()
        self.assertTrue(self.tv.evaluate("() => focusableElements.every(el => !el.closest('.left-vertical-dock'))"))
        self.phone.locator('#menuPosition').select_option('left')
        self.save()
        expect(self.tv.locator('body')).to_have_attribute('data-nf-menu','left')
        sidebar = self.tv.locator('.left-vertical-dock').bounding_box()
        main = self.tv.locator('.main-content').bounding_box()
        self.assertLess(sidebar['x'],main['x'])

    def test_legacy_tv_font_fallback_without_modern_math(self):
        # Tizen 6 / Chromium 76 cannot evaluate clamp() or max(). Remove the
        # feature-query enhancements to exercise the same legacy declarations.
        self.tv.evaluate("""() => {
            const sheet=Array.from(document.styleSheets).find(s=>s.href && s.href.endsWith('/tv-ui/appearance.css'));
            for(let i=sheet.cssRules.length-1;i>=0;i--) if(sheet.cssRules[i].type===12) sheet.deleteRule(i);
        }""")
        sizes=[]
        for size in ['small','normal','large']:
            self.phone.locator('#textSize').select_option(size)
            self.save()
            self.tv.wait_for_function("value => window.NetFelixAppearance.textSize===value",arg=size)
            sizes.append(self.tv.locator('.hero-headline').evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)'))
        self.assertGreater(sizes[0],60)
        self.assertGreater(sizes[1],sizes[0])
        self.assertGreater(sizes[2],sizes[1])
        self.assertGreater(self.tv.locator('.tvm-hero-card').evaluate('(el)=>parseFloat(getComputedStyle(el).minHeight)'),490)


if __name__ == "__main__":
    unittest.main()
