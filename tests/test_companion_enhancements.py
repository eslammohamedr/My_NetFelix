"""Rollback, timezone boundaries, preset transactions and remote delivery semantics."""
import base64
import json
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import tv_settings
import tv_companion
import samsung_tv


class Designs(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = tv_settings.AppearanceStore(self.folder.name)

    def manage(self, kind, **body):
        body.setdefault('revision', self.store.snapshot()['revision'])
        return self.store.manage(kind, body)

    def test_preview_expires_without_persisting_and_does_not_survive_restart(self):
        with patch('tv_settings.time.time', return_value=100):
            trial = self.manage('trial', action='start', settings={'theme':'ahly'})
            self.assertEqual(trial['settings']['theme'], 'night')
            self.assertEqual(trial['displaySettings']['theme'], 'ahly')
            self.assertEqual(trial['trial']['expires'], 130)
            self.assertEqual(tv_settings.AppearanceStore(self.folder.name).snapshot()['displaySettings']['theme'], 'night')
        with patch('tv_settings.time.time', return_value=131):
            restored = self.store.snapshot()
            self.assertEqual(restored['displaySettings']['theme'], 'night')
            self.assertNotEqual(restored['displayRevision'], trial['displayRevision'])
            self.assertIsNone(restored['trial'])
            with self.assertRaises(ValueError):
                self.manage('trial', action='keep', id=trial['trial']['id'])

    def test_keep_restore_ownership_and_conflict(self):
        trial = self.manage('trial', action='start', settings={'theme':'ahly'})
        with self.assertRaises(ValueError):
            self.manage('trial', action='keep', id='wrong')
        with self.assertRaises(ValueError):
            self.manage('trial', action='start', settings={'theme':'blue'})
        kept = self.manage('trial', action='keep', id=trial['trial']['id'])
        self.assertEqual(kept['settings']['theme'], 'ahly')
        self.assertIsNone(kept['trial'])
        trial = self.manage('trial', action='start', settings={'theme':'blue'})
        restored = self.manage('trial', action='restore', id=trial['trial']['id'])
        self.assertEqual(restored['displaySettings']['theme'], 'ahly')
        with self.assertRaises(tv_settings.RevisionConflict):
            self.manage('presets', action='save', name='stale', settings={}, revision=0)

    def test_presets_duplicate_restore_persist_and_validate(self):
        value = self.manage('presets', action='save', name='Match night', settings={'theme':'ahly','tileSize':'large','menuPosition':'right'})
        first = value['presets'][0]['id']
        value = self.manage('presets', action='duplicate', id=first, name='Copy')
        self.assertEqual(len(value['presets']),2)
        value = self.manage('presets', action='restore', id=first)
        self.assertEqual(value['settings']['menuPosition'],'right')
        self.assertEqual(tv_settings.AppearanceStore(self.folder.name).snapshot()['settings']['tileSize'],'large')
        for settings in ({'tileSize':'huge'},{'menuPosition':'top'},{'wallpaper':'/api/tv/appearance/wallpaper/'+'0'*64}):
            with self.assertRaises(ValueError):
                self.manage('presets', action='import', name='Invalid', settings=settings)
        self.manage('presets', action='delete', id=first)
        self.assertEqual(len(self.store.snapshot()['presets']),1)

    def setup_schedule(self):
        value = self.manage('presets', action='save', name='Ramadan evening', settings={'theme':'islamic-makkah'})
        preset = value['presets'][0]['id']
        value = self.manage('schedules', action='save', preset=preset, start='18:00', end='06:00', days=[0], timezone='Africa/Cairo')
        return preset, value['schedules'][0]['id']

    def at(self, stamp):
        fake = Mock()
        fake.now.side_effect = lambda zone: datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo('Africa/Cairo')).astimezone(zone)
        return patch('tv_settings.datetime', fake)

    def test_overnight_weekday_boundaries_and_restore(self):
        preset, rule = self.setup_schedule()
        for stamp, expected in [('2026-10-26T17:59:00','night'),('2026-10-26T18:00:00','islamic-makkah'),('2026-10-27T05:59:00','islamic-makkah'),('2026-10-27T06:00:00','night'),('2026-10-27T19:00:00','night')]:
            with self.subTest(stamp=stamp), self.at(stamp):
                value = self.store.snapshot()
                self.assertEqual(value['displaySettings']['theme'],expected)
                self.assertEqual(value['settings']['theme'],'night')
        with self.assertRaises(ValueError):
            self.manage('presets', action='delete', id=preset)
        self.manage('schedules', action='delete', id=rule)
        self.manage('presets', action='delete', id=preset)

    def test_schedule_profile_isolation_and_preview_priority(self):
        self.setup_schedule()
        with self.at('2026-10-26T19:00:00'):
            trial = self.manage('trial', action='start', settings={'theme':'gta6'})
            self.assertEqual(trial['displaySettings']['theme'],'gta6')
            self.manage('trial', action='restore', id=trial['trial']['id'])
            self.assertEqual(self.store.snapshot()['displaySettings']['theme'],'islamic-makkah')
            self.store.profile('create', name='Other')
            self.assertEqual(self.store.snapshot()['displaySettings']['theme'],'night')

    def test_invalid_rules_never_persist(self):
        value = self.manage('presets', action='save', name='Base', settings={})
        rule = dict(action='save',preset=value['presets'][0]['id'],start='18:00',end='06:00',days=[0],timezone='Africa/Cairo')
        for patch_values in ({'start':'25:00'},{'end':'18:00'},{'days':[]},{'days':[True]},{'timezone':'missing/zone'},{'preset':'missing'}):
            with self.subTest(patch=patch_values), self.assertRaises(ValueError):
                self.manage('schedules', **{**rule,**patch_values})
        self.assertEqual(self.store.snapshot()['schedules'],[])

    def test_portable_photo_import_and_date_limited_schedule(self):
        from test_tv_appearance import PNG
        encoded = base64.b64encode(PNG).decode()
        image = self.store.wallpaper(encoded)
        value = self.manage('presets',action='save',name='My photo',settings=image['settings'])
        settings = value['presets'][0]['settings']
        other_dir = tempfile.TemporaryDirectory()
        self.addCleanup(other_dir.cleanup)
        other = tv_settings.AppearanceStore(other_dir.name)
        imported = other.manage('presets',{'action':'import','name':'Photo design','settings':settings,'wallpaperImage':encoded,'revision':0})
        restored = other.manage('presets',{'action':'restore','id':imported['presets'][0]['id'],'revision':imported['revision']})
        digest = restored['settings']['wallpaper'].rsplit('/',1)[-1]
        self.assertEqual((Path(other_dir.name)/'tv_wallpapers'/digest).read_bytes(),PNG)
        value = self.manage('schedules',action='save',preset=value['presets'][0]['id'],start='18:00',end='06:00',days=list(range(7)),timezone='Africa/Cairo',startsOn='2026-10-26',endsOn='2026-10-26')
        for stamp, active in [('2026-10-25T19:00:00',False),('2026-10-26T19:00:00',True),('2026-10-27T05:00:00',True),('2026-10-27T19:00:00',False)]:
            with self.at(stamp):
                self.assertEqual(bool(self.store.snapshot()['activeSchedule']),active)


class Remote(unittest.TestCase):
    def test_delivery_expiry_restart_and_offline(self):
        bus = tv_companion.CommandBus()
        with self.assertRaises(ValueError):
            bus.send({'kind':'key','key':'ENTER'})
        cursor = bus.poll()
        bus.send({'kind':'text','text':'أهلاً'})
        delivered = bus.poll(cursor['sequence'],cursor['epoch'])
        self.assertEqual(delivered['commands'][0]['text'],'أهلاً')
        self.assertEqual(bus.poll(delivered['sequence'],delivered['epoch'])['commands'],[])
        self.assertEqual(bus.poll(0,'other-process')['commands'],[])
        bus.send({'kind':'key','key':'UP'})
        with patch('tv_companion.time.monotonic', return_value=10**12):
            self.assertEqual(bus.poll(0,cursor['epoch'])['commands'],[])
        for body in ({'kind':'key','key':'POWER'},{'kind':'text','text':'x'*501},{'kind':'text','text':'\n'}):
            with self.assertRaises(ValueError):
                bus.send(body)

    def test_nonce_bound_discovery_and_malformed_packets(self):
        nonce = 'a'*32
        value = json.loads(tv_companion.discovery_response(json.dumps({'service':'netfelix-discover','nonce':nonce}).encode()))
        self.assertEqual(value['nonce'],nonce)
        self.assertEqual(value['port'],8092)
        for data in (b'[]',b'null',b'bad',b'{}',b'x'*201,b'\xff'):
            self.assertIsNone(tv_companion.discovery_response(data))

    def test_native_unicode_keyboard_packet_and_failure_no_retry(self):
        ws = Mock()
        with patch('samsung_tv.get_tv_ws', return_value=ws):
            self.assertTrue(samsung_tv.send_text('عربي')['success'])
        payload = json.loads(ws.send.call_args.args[0])
        self.assertEqual(base64.b64decode(payload['params']['Cmd']).decode(),'عربي')
        self.assertEqual(payload['params']['TypeOfRemote'],'SendInputString')
        with patch('samsung_tv.get_tv_ws', side_effect=OSError()) as connect:
            self.assertFalse(samsung_tv.send_text('abc')['success'])
            self.assertEqual(connect.call_count,1)
        with self.assertRaises(ValueError):
            samsung_tv.send_text(None)

class HttpContract(unittest.TestCase):
    def setUp(self):
        import threading
        from http.server import ThreadingHTTPServer
        from test_tv_appearance import Handler
        self.old_store = tv_settings.STORE
        self.folder = tempfile.TemporaryDirectory()
        tv_settings.STORE = tv_settings.AppearanceStore(self.folder.name)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        tv_settings.STORE = self.old_store
        self.folder.cleanup()

    def request(self, path, body=None, origin=None):
        import urllib.request, urllib.error
        headers = {'Content-Type':'application/json'}
        if origin: headers['Origin'] = origin
        request = urllib.request.Request(self.base+path, data=None if body is None else json.dumps(body).encode(),headers=headers)
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers

    def test_portable_export_import_and_revision_guard(self):
        from test_tv_appearance import PNG
        encoded = base64.b64encode(PNG).decode()
        code,photo,_ = self.request('/api/tv/appearance/upload',{'image':encoded,'revision':0})
        self.assertEqual(code,200)
        code,saved,_ = self.request('/api/tv/appearance/presets',{'action':'save','name':'My scene','settings':photo['settings'],'revision':photo['revision']})
        self.assertEqual(code,200)
        code,design,headers = self.request('/api/tv/appearance/export/'+saved['presets'][0]['id'])
        self.assertEqual(code,200)
        self.assertIn('attachment',headers['Content-Disposition'])
        self.assertEqual(base64.b64decode(design['wallpaperImage']),PNG)
        code,imported,_ = self.request('/api/tv/appearance/presets',{'action':'import',**design,'revision':saved['revision']})
        self.assertEqual(code,200)
        self.assertEqual(len(imported['presets']),2)
        code,_,_ = self.request('/api/tv/appearance/trial',{'action':'start','settings':{},'revision':0})
        self.assertEqual(code,409)

    def test_remote_validation_origin_and_identity(self):
        code,info,_ = self.request('/api/tv/companion/info')
        self.assertEqual(code,200)
        self.assertEqual(info['service'],'netfelix-companion')
        code,_,_ = self.request('/api/tv/companion/control',{'target':'dashboard','kind':'text','text':'hello'},'https://other.example')
        self.assertEqual(code,403)
        for body in ({'target':'samsung','kind':'key','key':'POWER'},{'target':'samsung','kind':'text','text':None},{'target':'invalid'}):
            self.assertEqual(self.request('/api/tv/companion/control',body)[0],400)
        self.assertEqual(self.request('/api/tv/companion/commands?after=bad')[0],400)
        self.assertEqual(self.request('/api/tv/companion/commands?after=0')[0],200)
