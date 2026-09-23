"""LAN-only, verified-piece HTTP playback for existing qBittorrent downloads."""
import http.cookiejar
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, parse, request
from catalog import CatalogError, resolve
from sources import internet_archive_search

QBT_URL = os.getenv('QBT_URL', 'http://127.0.0.1:8080').rstrip('/')
ROOT = Path(os.getenv('TORRENT_ROOT', '/data/torrents')).resolve()
QBT_ROOT = Path(os.getenv('QBT_TORRENT_ROOT', '/data/torrents'))
BUFFER = int(os.getenv('BUFFER_BYTES', str(16 * 1024 * 1024)))
WAIT_SECONDS = int(os.getenv('STREAM_WAIT_SECONDS', '120'))
VIDEO_EXTENSIONS = {'.mp4', '.m4v', '.webm', '.mkv', '.avi', '.mov', '.ts'}
SUBTITLE_EXTENSIONS = {'.srt', '.vtt'}
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', '/data/media')).resolve()
BAZARR_URL = os.getenv('BAZARR_URL', 'http://127.0.0.1:6767').rstrip('/')
BAZARR_API_KEY = os.getenv('BAZARR_API_KEY', '')
BAD_STATES = {'missingFiles', 'error', 'checkingDL', 'checkingUP', 'checkingResumeData', 'moving'}
PREPARE_LOCK = threading.Lock()

LANG_CODES = {
    'en': ('English', 'en'), 'eng': ('English', 'en'), 'english': ('English', 'en'),
    'ar': ('Arabic', 'ar'), 'ara': ('Arabic', 'ar'), 'arabic': ('Arabic', 'ar'),
    'es': ('Spanish', 'es'), 'spa': ('Spanish', 'es'), 'spanish': ('Spanish', 'es'),
    'fr': ('French', 'fr'), 'fre': ('French', 'fr'), 'fra': ('French', 'fr'), 'french': ('French', 'fr'),
    'de': ('German', 'de'), 'ger': ('German', 'de'), 'deu': ('German', 'de'), 'german': ('German', 'de'),
    'it': ('Italian', 'it'), 'ita': ('Italian', 'it'), 'italian': ('Italian', 'it'),
    'pt': ('Portuguese', 'pt'), 'por': ('Portuguese', 'pt'), 'portuguese': ('Portuguese', 'pt'),
    'ru': ('Russian', 'ru'), 'rus': ('Russian', 'ru'), 'russian': ('Russian', 'ru'),
    'zh': ('Chinese', 'zh'), 'chi': ('Chinese', 'zh'), 'chinese': ('Chinese', 'zh'),
    'ja': ('Japanese', 'ja'), 'jpn': ('Japanese', 'ja'), 'japanese': ('Japanese', 'ja'),
    'ko': ('Korean', 'ko'), 'kor': ('Korean', 'ko'), 'korean': ('Korean', 'ko'),
    'tr': ('Turkish', 'tr'), 'tur': ('Turkish', 'tr'), 'turkish': ('Turkish', 'tr'),
    'hi': ('Hindi', 'hi'), 'hin': ('Hindi', 'hi'), 'hindi': ('Hindi', 'hi'),
    'fa': ('Persian', 'fa'), 'per': ('Persian', 'fa'), 'fas': ('Persian', 'fa'), 'persian': ('Persian', 'fa'),
    'nl': ('Dutch', 'nl'), 'dut': ('Dutch', 'nl'), 'nld': ('Dutch', 'nl'), 'dutch': ('Dutch', 'nl'),
    'pl': ('Polish', 'pl'), 'pol': ('Polish', 'pl'), 'polish': ('Polish', 'pl'),
    'sv': ('Swedish', 'sv'), 'swe': ('Swedish', 'sv'), 'swedish': ('Swedish', 'sv'),
}


def detect_language(filename: str):
    stem = Path(filename).stem.lower()
    is_sdh = any(term in stem for term in ('sdh', '.hi.', '_hi', '-hi', 'hearing impaired'))
    parts = re.split(r'[\s._\-+]+', stem)
    name, code = 'English', 'en'
    for part in parts:
        if part in LANG_CODES:
            name, code = LANG_CODES[part]
            break
    if is_sdh:
        name += ' [SDH]'
    return name, code


def srt_to_vtt(srt_bytes: bytes) -> str:
    for enc in ('utf-8-sig', 'utf-8', 'cp1256', 'cp1252', 'latin-1'):
        try:
            text = srt_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = srt_bytes.decode('utf-8', errors='replace')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2 --> \3.\4', text)
    return 'WEBVTT\n\n' + text.lstrip()


class Problem(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


class Qbit:
    def __init__(self):
        self.opener = request.build_opener(request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.lock = threading.RLock()

    def call(self, endpoint, data=None, raw=False, **params):
        url = QBT_URL + '/api/v2/' + endpoint
        if params:
            url += '?' + parse.urlencode(params)
        payload = parse.urlencode(data).encode() if data is not None else None
        req = request.Request(url, data=payload, headers={'Referer': QBT_URL})
        with self.lock:
            try:
                response = self.opener.open(req, timeout=10)
            except error.HTTPError as exc:
                if exc.code != 403 or not os.getenv('QBT_USERNAME'):
                    raise Problem('Cannot access qBittorrent. Check its connection and credentials.', 502) from exc
                login = request.Request(QBT_URL + '/api/v2/auth/login', data=parse.urlencode({
                    'username': os.environ['QBT_USERNAME'], 'password': os.getenv('QBT_PASSWORD', '')
                }).encode(), headers={'Referer': QBT_URL})
                with self.opener.open(login, timeout=10) as result:
                    if result.read() != b'Ok.':
                        raise Problem('qBittorrent login failed.', 502)
                response = self.opener.open(req, timeout=10)
            with response:
                body = response.read()
        if raw:
            return body
        return json.loads(body) if body else None


qbt = Qbit()


def bdecode(data):
    """Decode torrent metadata only, never pickle/untrusted executable objects."""
    def read(pos, depth=0):
        if depth > 64 or pos >= len(data):
            raise ValueError('Invalid torrent metadata')
        kind = data[pos:pos + 1]
        if kind == b'i':
            end = data.index(b'e', pos)
            return int(data[pos + 1:end]), end + 1
        if kind in (b'l', b'd'):
            result = [] if kind == b'l' else {}
            pos += 1
            while data[pos:pos + 1] != b'e':
                item, pos = read(pos, depth + 1)
                if kind == b'd':
                    value, pos = read(pos, depth + 1)
                    result[item] = value
                else:
                    result.append(item)
            return result, pos + 1
        end = data.index(b':', pos)
        length = int(data[pos:end])
        if length < 0 or end + 1 + length > len(data):
            raise ValueError('Invalid string size')
        return data[end + 1:end + 1 + length], end + 1 + length
    result, end = read(0)
    if end != len(data):
        raise ValueError('Trailing torrent metadata')
    return result


def file_offset(metadata, files, selected):
    info = metadata[b'info']
    # v2 aligns files differently; do not guess and serve unverified bytes.
    if b'meta version' in info:
        raise Problem('This torrent uses v2/hybrid metadata. Early playback currently supports v1 torrents only.')
    entries = info.get(b'files', [{b'length': info.get(b'length', 0)}])
    if any(b'p' in e.get(b'attr', b'') for e in entries):
        raise Problem('Early playback of torrents with padding files is not supported.')
    ordered = sorted(files, key=lambda f: f['index'])
    if len(entries) != len(ordered) or any(e[b'length'] != f['size'] for e, f in zip(entries, ordered)):
        raise Problem('Torrent file layout could not be verified.')
    return sum(f['size'] for f in ordered if f['index'] < selected['index'])


def parse_range(value, size):
    if size <= 0:
        raise Problem('Video is empty.', 416)
    if value is None:
        return 0, size - 1, False
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
    if not match or not any(match.groups()):
        raise Problem('Unsupported byte range.', 416)
    first, last = match.groups()
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    else:
        suffix = int(last)
        if suffix <= 0:
            raise Problem('Invalid suffix range.', 416)
        start, end = max(0, size - suffix), size - 1
    if start >= size or end < start:
        raise Problem('Range is outside this video.', 416)
    return start, end, True


def checked_torrent(h):
    if not re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', h):
        raise Problem('Invalid torrent identifier.', 400)
    items = qbt.call('torrents/info', hashes=h)
    if not items:
        raise Problem('Download no longer exists.', 404)
    torrent = items[0]
    if torrent['state'] in BAD_STATES:
        raise Problem('Download unavailable: ' + torrent['state'] + '. Check the Data drive and qBittorrent.')
    return torrent


def context(h, index):
    torrent = checked_torrent(h)
    files = qbt.call('torrents/files', hash=h)
    selected = next((f for f in files if f['index'] == index), None)
    if not selected or Path(selected['name']).suffix.lower() not in VIDEO_EXTENSIONS:
        raise Problem('Video file not found.', 404)
    properties = qbt.call('torrents/properties', hash=h)
    piece_size = properties.get('piece_size', 0)
    if piece_size <= 0:
        raise Problem('Waiting for torrent metadata.')
    metadata = bdecode(qbt.call('torrents/export', hash=h, raw=True))
    offset = file_offset(metadata, files, selected)
    if metadata[b'info'][b'piece length'] != piece_size:
        raise Problem('Torrent piece size could not be verified.')
    return torrent, selected, properties, offset, piece_size


def available_bytes(states, offset, size, piece_size):
    position = 0
    while position < size:
        piece = (offset + position) // piece_size
        if piece >= len(states) or states[piece] != 2:
            break
        position = min(size, (piece + 1) * piece_size - offset)
    return position


def local_path(torrent, file, properties):
    # Incomplete data can be moved by qBittorrent on completion. Re-resolve on retries.
    locations = [properties.get('download_path'), torrent.get('download_path'), torrent.get('save_path')]
    for location in filter(None, locations):
        try:
            relative = Path(location).relative_to(QBT_ROOT)
        except ValueError:
            continue
        path = ROOT / relative / file['name']
        for candidate in (path, Path(str(path) + '.!qB')):
            resolved = candidate.resolve()
            if not resolved.is_relative_to(ROOT):
                raise Problem('Video path is outside the downloads folder.', 403)
            if resolved.is_file():
                return resolved
    raise Problem('Video file is not on disk yet. Check the mounted drive or wait for downloading to start.')


def get_subtitles(h, torrent, properties):
    subtitles = []
    # 1. External subtitles in torrent
    try:
        files = qbt.call('torrents/files', hash=h)
        for f in files:
            ext = Path(f['name']).suffix.lower()
            if ext in SUBTITLE_EXTENSIONS:
                label, lang = detect_language(f['name'])
                ready = False
                try:
                    local_path(torrent, f, properties)
                    ready = True
                except Problem:
                    ready = f.get('progress', 0) == 1.0
                subtitles.append({
                    'id': f"torrent-{f['index']}",
                    'label': label,
                    'lang': lang,
                    'url': f"/subtitles/torrent/{h}/{f['index']}.vtt",
                    'ready': ready,
                    'source': 'torrent'
                })
    except Exception:
        logging.debug('Could not check torrent files for subtitles', exc_info=True)

    # 2. Subtitles from Bazarr / media library
    if BAZARR_API_KEY:
        try:
            headers = {'X-Api-Key': BAZARR_API_KEY}
            def bazarr_get(path):
                req = request.Request(f"{BAZARR_URL}{path}", headers=headers)
                with request.urlopen(req, timeout=3) as resp:
                    return json.load(resp).get('data', [])

            torrent_name = torrent.get('name', '').lower()
            movies = bazarr_get('/api/movies')
            for movie in movies:
                title = movie.get('title', '').lower()
                scene = (movie.get('sceneName') or '').lower()
                if (title and title in torrent_name) or (scene and scene in torrent_name):
                    subtitles.extend(format_bazarr_subtitles(movie.get('subtitles', [])))
                    break

            # Bazarr exposes TV subtitles per episode, so identify the matching
            # series first and then query its episode list with the required
            # array-style seriesid[] parameter.
            for series in bazarr_get('/api/series'):
                title = (series.get('title') or '').lower()
                scene = (series.get('sceneName') or '').lower()
                if not ((title and title in torrent_name) or (scene and scene in torrent_name)):
                    continue
                series_id = series.get('sonarrSeriesId') or series.get('id')
                if not series_id:
                    continue
                episodes = bazarr_get('/api/episodes?' + parse.urlencode({'seriesid[]': series_id}))
                matched_episode = False
                for episode in episodes:
                    episode_path = (episode.get('path') or '').lower()
                    episode_name = Path(episode_path).name
                    episode_stem = Path(episode_name).stem
                    if episode_path and episode_path not in torrent_name and episode_name not in torrent_name and episode_stem not in torrent_name:
                        continue
                    matched_episode = True
                    subtitles.extend(format_bazarr_subtitles(episode.get('subtitles', [])))
                    missing = {s.get('code2') for s in episode.get('missing_subtitles', []) if s.get('code2')}
                    for lang in sorted(missing):
                        if not any(s.get('missing') and s.get('lang') == lang for s in subtitles):
                            name = LANG_CODES.get(lang, (lang.upper(), lang))[0]
                            subtitles.append({'id': f'bazarr-missing-{lang}', 'label': f'{name} (Bazarr: not found)',
                                              'lang': lang, 'ready': False, 'missing': True, 'source': 'bazarr'})
                    break
                if not matched_episode:
                    # Season-pack torrents usually have only the pack name in
                    # qBittorrent, so report Bazarr's missing-language state
                    # across the series even when no single episode filename
                    # can be matched.
                    missing = {s.get('code2') for episode in episodes for s in episode.get('missing_subtitles', []) if s.get('code2')}
                    for lang in sorted(missing):
                        name = LANG_CODES.get(lang, (lang.upper(), lang))[0]
                        subtitles.append({'id': f'bazarr-missing-{lang}', 'label': f'{name} (Bazarr: not found)',
                                          'lang': lang, 'ready': False, 'missing': True, 'source': 'bazarr'})
                break
        except Exception:
            logging.debug('Could not query Bazarr for subtitles', exc_info=True)
    return subtitles


def format_bazarr_subtitles(items):
    result = []
    for b_sub in items:
        sub_id = b_sub.get('id')
        if not sub_id:
            continue
        sub_name = b_sub.get('name', 'Unknown')
        if b_sub.get('hi'):
            sub_name += ' [SDH]'
        result.append({'id': f"bazarr-{sub_id}", 'label': f"{sub_name} (Bazarr)",
                       'lang': b_sub.get('code2', 'en'), 'url': f"/subtitles/bazarr/{sub_id}.vtt",
                       'ready': True, 'source': 'bazarr'})
    return result


def readiness(h, index):
    torrent, file, properties, offset, piece_size = context(h, index)
    states = qbt.call('torrents/pieceStates', hash=h)
    available = available_bytes(states, offset, file['size'], piece_size)
    last = (offset + file['size'] - 1) // piece_size
    tail_ready = last < len(states) and states[last] == 2
    target = min(BUFFER, file['size'])
    try:
        local_path(torrent, file, properties)
        on_disk = True
    except Problem:
        on_disk = False
    subtitles = get_subtitles(h, torrent, properties)
    missing_languages = sorted({s['lang'] for s in subtitles if s.get('missing')})
    return {'ready': available >= target and tail_ready and on_disk,
            'buffer_bytes': available, 'target_bytes': target, 'tail_ready': tail_ready,
            'progress': file['progress'], 'speed': torrent.get('dlspeed', 0),
            'state': torrent['state'], 'on_disk': on_disk,
            'subtitles': subtitles, 'subtitle_missing_languages': missing_languages}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def reply(self, status, body, content_type='application/json', extra=None):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self.respond(False)

    def do_POST(self):
        self.respond(True)

    def respond(self, mutate):
        try:
            path = parse.urlsplit(self.path).path
            if mutate:
                # Require a same-origin browser request or explicit non-browser header.
                if self.headers.get('X-NetFelix') != '1':
                    raise Problem('Missing request header.', 403)
                origin = self.headers.get('Origin')
                if origin and parse.urlsplit(origin).netloc != self.headers.get('Host'):
                    raise Problem('Cross-origin requests are not allowed.', 403)
                if int(self.headers.get('Content-Length', '0')) != 0:
                    self.close_connection = True
                    raise Problem('Request body is not supported.', 400)
            if path == '/' and not mutate:
                self.reply(200, Path(__file__).with_name('dashboard.html').read_bytes(), 'text/html; charset=utf-8')
            elif path == '/dashboard' and not mutate:
                self.reply(200, Path(__file__).with_name('dashboard.html').read_bytes(), 'text/html; charset=utf-8')
            elif path == '/search' and not mutate:
                self.reply(200, Path(__file__).with_name('search.html').read_bytes(), 'text/html; charset=utf-8')
            elif path == '/manifest.json' and not mutate:
                self.reply(200, Path(__file__).with_name('manifest.json').read_bytes(), 'application/manifest+json')
            elif path == '/sw.js' and not mutate:
                self.reply(200, Path(__file__).with_name('sw.js').read_bytes(), 'application/javascript')
            elif (path == '/downloads' or re.fullmatch(r'/watch/(movie|tv)/[1-9][0-9]*', path)) and not mutate:
                self.reply(200, Path(__file__).with_name('index.html').read_bytes(), 'text/html; charset=utf-8')
            elif re.fullmatch(r'/api/resolve/(movie|tv)/[1-9][0-9]*', path) and not mutate:
                _, _, _, media_type, tmdb_id = path.split('/')
                self.reply(200, resolve(media_type, int(tmdb_id), qbt))
            elif path == '/health' and not mutate:
                self.reply(200, {'status': 'ok'})
            elif path == '/api/sources/internet-archive' and not mutate:
                query = parse.parse_qs(parse.urlsplit(self.path).query).get('q', [''])[0].strip()
                if not query or len(query) > 160:
                    raise Problem('Provide a search query between 1 and 160 characters.', 400)
                self.reply(200, {'source': 'Internet Archive', 'results': internet_archive_search(query)})
            elif path == '/api/downloads' and not mutate:
                result = []
                for t in qbt.call('torrents/info'):
                    files = qbt.call('torrents/files', hash=t['hash'])
                    result.append({k: t.get(k) for k in ('hash', 'name', 'progress', 'state', 'dlspeed', 'num_seeds', 'num_leechs', 'eta')} | {
                        'files': [{'index': f['index'], 'name': f['name'], 'size': f['size'], 'progress': f['progress']}
                                  for f in files if Path(f['name']).suffix.lower() in VIDEO_EXTENSIONS]})
                self.reply(200, result)
            sub_torrent_match = re.fullmatch(r'/subtitles/torrent/([a-fA-F0-9]{40}|[a-fA-F0-9]{64})/(\d+)\.vtt', path)
            sub_bazarr_match = re.fullmatch(r'/subtitles/bazarr/(\d+)\.vtt', path)
            if sub_torrent_match and not mutate:
                h, sub_idx = sub_torrent_match.groups()
                torrent = checked_torrent(h)
                files = qbt.call('torrents/files', hash=h)
                sub_file = next((f for f in files if f['index'] == int(sub_idx)), None)
                if not sub_file or Path(sub_file['name']).suffix.lower() not in SUBTITLE_EXTENSIONS:
                    raise Problem('Subtitle file not found.', 404)
                properties = qbt.call('torrents/properties', hash=h)
                p = local_path(torrent, sub_file, properties)
                raw = p.read_bytes()
                vtt = srt_to_vtt(raw) if p.suffix.lower() == '.srt' else raw.decode('utf-8', errors='replace')
                self.reply(200, vtt.encode('utf-8'), 'text/vtt; charset=utf-8', {
                    'Access-Control-Allow-Origin': '*',
                    'Cache-Control': 'public, max-age=3600'
                })
            elif sub_bazarr_match and not mutate:
                sub_id = int(sub_bazarr_match.group(1))
                if not BAZARR_API_KEY:
                    raise Problem('Bazarr is not configured.', 503)
                target_sub = None
                api_headers = {'X-Api-Key': BAZARR_API_KEY}
                def bazarr_data(path):
                    req = request.Request(f"{BAZARR_URL}{path}", headers=api_headers)
                    with request.urlopen(req, timeout=5) as resp:
                        return json.load(resp).get('data', [])
                for m in bazarr_data('/api/movies'):
                    for s_item in m.get('subtitles', []):
                        if s_item.get('id') == sub_id:
                            target_sub = s_item
                            break
                    if target_sub:
                        break
                if not target_sub:
                    for series in bazarr_data('/api/series'):
                        series_id = series.get('sonarrSeriesId') or series.get('id')
                        if not series_id:
                            continue
                        for episode in bazarr_data('/api/episodes?' + parse.urlencode({'seriesid[]': series_id})):
                            for s_item in episode.get('subtitles', []):
                                if s_item.get('id') == sub_id:
                                    target_sub = s_item
                                    break
                            if target_sub:
                                break
                        if target_sub:
                            break
                if not target_sub or not target_sub.get('path'):
                    raise Problem('Subtitle not found in Bazarr.', 404)
                sub_path_str = target_sub['path']
                candidate_path = Path(sub_path_str)
                if candidate_path.is_file():
                    raw = candidate_path.read_bytes()
                    vtt = srt_to_vtt(raw) if candidate_path.suffix.lower() == '.srt' else raw.decode('utf-8', errors='replace')
                else:
                    params = parse.urlencode({'subtitlePath': sub_path_str})
                    c_req = request.Request(f"{BAZARR_URL}/api/subtitles/contents?{params}", headers={'X-Api-Key': BAZARR_API_KEY})
                    with request.urlopen(c_req, timeout=10) as c_resp:
                        c_data = json.load(c_resp).get('data', [])
                    vtt_lines = ['WEBVTT\n']
                    for cue in c_data:
                        s_cue = cue.get('start', {})
                        e_cue = cue.get('end', {})
                        s_str = f"{s_cue.get('hours', 0):02d}:{s_cue.get('minutes', 0):02d}:{s_cue.get('seconds', 0):02d}.{s_cue.get('microseconds', 0)//1000:03d}"
                        e_str = f"{e_cue.get('hours', 0):02d}:{e_cue.get('minutes', 0):02d}:{e_cue.get('seconds', 0):02d}.{e_cue.get('microseconds', 0)//1000:03d}"
                        vtt_lines.append(f"{cue.get('index', '')}\n{s_str} --> {e_str}\n{cue.get('content', '')}\n")
                    vtt = '\n'.join(vtt_lines)
                self.reply(200, vtt.encode('utf-8'), 'text/vtt; charset=utf-8', {
                    'Access-Control-Allow-Origin': '*',
                    'Cache-Control': 'public, max-age=3600'
                })
            else:
                match = re.fullmatch(r'/(api/prepare|api/status|stream|playlist)/([a-fA-F0-9]{40}|[a-fA-F0-9]{64})/(\d+)', path)
                if not match:
                    raise Problem('Not found.', 404)
                action, h, index = match.groups()
                index = int(index)
                if mutate != (action == 'api/prepare'):
                    raise Problem('Method not allowed.', 405)
                if action == 'api/prepare':
                    with PREPARE_LOCK:
                        torrent, file, _, _, _ = context(h, index)
                        if not torrent.get('seq_dl'):
                            qbt.call('torrents/toggleSequentialDownload', data={'hashes': h}, raw=True)
                        if not torrent.get('f_l_piece_prio'):
                            qbt.call('torrents/toggleFirstLastPiecePrio', data={'hashes': h}, raw=True)
                        files = qbt.call('torrents/files', hash=h)
                        video_files = [f for f in files if Path(f['name']).suffix.lower() in VIDEO_EXTENSIONS]
                        if len(video_files) > 1:
                            other_ids = [str(f['index']) for f in video_files if f['index'] != index]
                            if other_ids:
                                qbt.call('torrents/filePrio', data={'hash': h, 'id': '|'.join(other_ids), 'priority': 1}, raw=True)
                        qbt.call('torrents/filePrio', data={'hash': h, 'id': index, 'priority': 7}, raw=True)
                        for f in files:
                            if Path(f['name']).suffix.lower() in SUBTITLE_EXTENSIONS:
                                qbt.call('torrents/filePrio', data={'hash': h, 'id': f['index'], 'priority': 7}, raw=True)
                        qbt.call('torrents/start', data={'hashes': h}, raw=True)
                    self.reply(200, {'prepared': True})
                elif action == 'api/status':
                    self.reply(200, readiness(h, index))
                elif action == 'playlist':
                    # A relative URL works in browsers but not all VLC builds; use a validated host.
                    host = self.headers.get('Host', '')
                    if not re.fullmatch(r'[a-zA-Z0-9.\-\[\]:]+', host):
                        raise Problem('Invalid host.', 400)
                    checked_torrent(h)
                    body_lines = ['#EXTM3U']
                    try:
                        torrent, file, properties, _, _ = context(h, index)
                        subs = get_subtitles(h, torrent, properties)
                        ready_subs = [s for s in subs if s.get('ready')]
                        if ready_subs:
                            body_lines.append(f"#EXTVLCOPT:sub-file=http://{host}{ready_subs[0]['url']}")
                    except Exception:
                        pass
                    body_lines.append(f'http://{host}/stream/{h}/{index}\n')
                    body = '\n'.join(body_lines).encode()
                    self.reply(200, body, 'audio/x-mpegurl', {'Content-Disposition': 'attachment; filename="NetFelix.m3u"'})
                else:
                    self.stream(h, index)
        except Problem as exc:
            self.reply(exc.status, {'error': str(exc)})
        except CatalogError as exc:
            self.reply(503, {'error': str(exc)})
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            self.close_connection = True
        except Exception:
            logging.exception('Request failed')
            self.reply(502, {'error': 'Cannot read the download. Check qBittorrent and the server logs.'})

    def stream(self, h, index):
        torrent, file, properties, offset, piece_size = context(h, index)
        size = file['size']
        try:
            start, end, partial = parse_range(self.headers.get('Range'), size)
        except Problem as exc:
            self.reply(exc.status, {'error': str(exc)}, extra={'Content-Range': f'bytes */{size}'})
            return
        stream = None
        headers_sent = False
        self.connection.settimeout(15)
        try:
            position = start
            deadline = time.monotonic() + WAIT_SECONDS
            states, last_check = [], 0
            while position <= end:
                now = time.monotonic()
                if now - last_check >= 1 or not states:
                    states = qbt.call('torrents/pieceStates', hash=h)
                    torrent = checked_torrent(h)
                    last_check = now
                piece = (offset + position) // piece_size
                if piece >= len(states) or states[piece] != 2:
                    if now >= deadline:
                        raise Problem('Buffering timed out. Wait for more pieces, then retry.', 503)
                    time.sleep(0.25)
                    continue
                if stream is None and self.command != 'HEAD':
                    try:
                        properties = qbt.call('torrents/properties', hash=h)
                        stream = local_path(torrent, file, properties).open('rb')
                    except (Problem, FileNotFoundError):
                        if now >= deadline:
                            raise Problem('Downloaded file is unavailable.', 503)
                        time.sleep(0.25)
                        continue
                if not headers_sent:
                    self.close_connection = True
                    self.send_response(206 if partial else 200)
                    self.send_header('Content-Type', mimetypes.guess_type(file['name'])[0] or 'application/octet-stream')
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Content-Length', str(end - start + 1))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Connection', 'close')
                    if partial:
                        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                    self.end_headers()
                    headers_sent = True
                    if self.command == 'HEAD':
                        return
                length = min(end - position + 1, (piece + 1) * piece_size - offset - position, 256 * 1024)
                stream.seek(position)
                chunk = stream.read(length)
                if len(chunk) != length:
                    if now >= deadline:
                        raise Problem('Video data has not been flushed to disk.', 503)
                    time.sleep(0.25)
                    continue
                self.wfile.write(chunk)
                position += length
                deadline = time.monotonic() + WAIT_SECONDS
        except Exception:
            if headers_sent:
                # Never append an HTTP error or sparse-file zeros to a video body.
                self.close_connection = True
                logging.info('Stream ended before completion for %s/%s', h, index)
            else:
                raise
        finally:
            if stream:
                stream.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer((os.getenv('BIND_HOST', '0.0.0.0'), int(os.getenv('PORT', '8090'))), Handler)
    logging.info('Watch Now listening on %s', server.server_address)
    server.serve_forever()
