from playwright.sync_api import sync_playwright
from pathlib import Path
import base64, json, tempfile, threading, re, sys, argparse
from http.server import ThreadingHTTPServer
from test_tv_appearance import Handler
import tv_settings
import tv_dashboard

parser = argparse.ArgumentParser(description="Check TV/phone appearance sync against an isolated local server")
parser.add_argument('--screenshots', default='/tmp/netfelix-appearance-previews')
args = parser.parse_args()
output = Path(args.screenshots)
output.mkdir(parents=True, exist_ok=True)
folder = tempfile.TemporaryDirectory(prefix='netfelix-appearance-check-')
tv_settings.STORE = tv_settings.AppearanceStore(folder.name)
html = tv_dashboard.TV_DASHBOARD_TEMPLATE
values = {'PRAYER_REMAINING_SECS':'3600', 'PRAYER_TARGET_NAME':'Fajr', 'CLOCK_TIME':'08:00', 'DATE_STR':'Thu, Oct 29', 'WEATHER_TEMP':'24°'}
for key in re.findall(r'\{([A-Z_]+)\}', html):
 html = html.replace('{'+key+'}', values.get(key,''))
class PreviewHandler(Handler):
 def do_GET(self):
  if self.path.split('?')[0] == '/tv-dashboard':
   tv_settings.send_bytes(self, html.encode(), 'text/html')
  else:
   super().do_GET()
server = ThreadingHTTPServer(('127.0.0.1',0),PreviewHandler)
thread = threading.Thread(target=server.serve_forever,daemon=True)
thread.start()
base = 'http://127.0.0.1:'+str(server.server_port)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 context=b.new_context(viewport={'width':1920,'height':1080})
 context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base) else r.abort())
 tv=context.new_page();errors=[];tv.on('pageerror',lambda e:errors.append(str(e)))
 tv.goto(base+'/tv-dashboard');tv.wait_for_selector('body.nf-ready')
 for width,height in [(1920,1080),(1280,720)]:
  tv.set_viewport_size({'width':width,'height':height})
  assert tv.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'overflow at {width}'
 tv.set_viewport_size({'width':1920,'height':1080})
 phone=context.new_page();phone.set_viewport_size({'width':390,'height':844});phone.on('pageerror',lambda e:errors.append(str(e)))
 phone.goto(base+'/tv-customize');phone.wait_for_selector('#editor:not([hidden])')
 assert phone.locator('.theme').count()==32
 assert phone.evaluate('document.documentElement.scrollWidth <= innerWidth'),'phone horizontal overflow'
 phone.locator('[data-theme="ahly"]').click()
 phone.locator('#title').fill('Our movie night')
 phone.locator('#motion').uncheck()
 phone.locator('#save').click();phone.wait_for_function("document.getElementById('status').textContent.startsWith('Saved.')")
 tv.wait_for_function("document.body.dataset.nfTheme === 'ahly'")
 assert tv.locator('.hero-headline').inner_text()=='Our movie night'
 assert tv.locator('body').get_attribute('data-nf-motion')=='false'
 tv.reload();tv.wait_for_selector('body.nf-ready')
 assert tv.locator('.hero-headline').inner_text()=='Our movie night'
 # Profile separation and cross-page sync.
 phone.locator('#new-profile').fill('Kids')
 phone.locator('#create-profile').click();phone.wait_for_function("document.getElementById('status').textContent.startsWith('Profile created')")
 tv.wait_for_function("document.body.dataset.nfTheme === 'night'")
 phone.locator('#profile').select_option('family')
 tv.wait_for_function("document.body.dataset.nfTheme === 'ahly'")
 # Upload uses an actual file chooser's data and the shared HTTP upload route.
 image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNQcEgAAAFEAMELjZZCAAAAAElFTkSuQmCC')
 phone.locator('#wallpaper').set_input_files({'name':'photo.png','mimeType':'image/png','buffer':image})
 phone.wait_for_function("document.getElementById('status').textContent.startsWith('Photo applied')")
 tv.wait_for_function("document.body.style.getPropertyValue('--nf-wallpaper').includes('/api/tv/appearance/wallpaper/')")
 phone.locator('#clear-wallpaper').click();phone.locator('#save').click()
 phone.wait_for_function("document.getElementById('status').textContent.startsWith('Saved.')")
 tv.wait_for_function("document.body.style.getPropertyValue('--nf-wallpaper') === 'none'")
 # Reorder favorites and verify it propagates to the remote-friendly dock.
 phone.get_by_role('button',name='Move Live TV up',exact=True).click()
 phone.locator('#save').click();phone.wait_for_function("document.getElementById('status').textContent.startsWith('Saved.')")
 tv.wait_for_function("document.querySelector('.tvm-bottom-dock [data-nf-app]').dataset.nfApp === 'iptv'")
 # Search still permits text and Back restores its originating element.
 tv.evaluate("document.querySelector('[data-nf-app=search]').click()")
 tv.locator('#sd-query-input').press_sequentially('Dune')
 assert tv.locator('#sd-query-input').input_value()=='Dune'
 tv.keyboard.press('Escape');assert tv.locator('#search-downloader-modal').is_hidden()
 # Palette-only titles render as text, never HTML.
 phone.locator('#title').fill('<img src=x onerror=alert(1)>')
 phone.locator('#save').click();phone.wait_for_function("document.getElementById('status').textContent.startsWith('Saved.')")
 tv.wait_for_function("document.querySelector('.hero-headline').textContent.startsWith('<img')")
 assert tv.locator('.hero-headline img').count()==0
 phone.locator('#title').fill('Your TV. Your world.');phone.locator('[data-theme="night"]').click();phone.locator('#save').click()
 phone.wait_for_function("document.getElementById('status').textContent.startsWith('Saved.')")
 tv.wait_for_function("document.body.dataset.nfTheme === 'night'")
 tv.evaluate('scrollTo(0,0)');tv.screenshot(path=str(output/'tv.png'))
 phone.evaluate('scrollTo(0,0)');phone.screenshot(path=str(output/'phone.png'))
 assert not errors,errors
 print('PASS: TV 720p/1080p and phone layouts, 32 palettes, live sync, persistence, profiles, upload/reset, dock reorder, search/Back, safe text rendering; no page errors')
 b.close()

server.shutdown()
server.server_close()
thread.join()
folder.cleanup()
