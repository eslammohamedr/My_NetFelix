#!/usr/bin/env python3
"""Check local NetFelix services, monitor disk space, and alert via Telegram."""
import json
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
from urllib import error, request


def load_env():
    path = Path('.env')
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key, value)


SERVICES = {
    'jellyfin': 'http://127.0.0.1:8096/health',
    'jellyseerr': 'http://127.0.0.1:5055/api/v1/status',
    'radarr': 'http://127.0.0.1:7878/api/v3/system/status',
    'sonarr': 'http://127.0.0.1:8989/api/v3/system/status',
    'prowlarr': 'http://127.0.0.1:9696/api/v1/system/status',
    'bazarr': 'http://127.0.0.1:6767/api/providers',
    'qbittorrent': 'http://127.0.0.1:8080/api/v2/app/version',
    'immich': 'http://127.0.0.1:2283/api/server/version',
    'adguard': 'http://127.0.0.1:8085',
    'audiobookshelf': 'http://127.0.0.1:13378/healthcheck',
    'filebrowser': 'http://127.0.0.1:8082',
    'watch-now': 'http://127.0.0.1:8090/health',
}


def send_telegram(message):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_ALLOWED_USER_ID')
    if not token or not chat_id:
        return
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    body = json.dumps({'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}).encode('utf-8')
    req = request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        with request.urlopen(req, timeout=10) as resp:
            pass
    except OSError:
        pass


def check_disk(path_str, label, min_percent=10):
    try:
        usage = shutil.disk_usage(path_str)
        percent_free = (usage.free / usage.total) * 100
        free_gb = usage.free / (1024 ** 3)
        if percent_free < min_percent:
            send_telegram(f"⚠️ *Disk Warning: {label} is low on space!*\nOnly `{free_gb:.1f} GB` ({percent_free:.1f}%) remaining.")
    except Exception:
        pass


def check(name, url):
    try:
        headers = {'Accept': 'application/json'}
        key_name = {'jellyseerr': 'JELLYSEERR_API_KEY', 'radarr': 'RADARR_API_KEY',
                    'sonarr': 'SONARR_API_KEY', 'prowlarr': 'PROWLARR_API_KEY',
                    'bazarr': 'BAZARR_API_KEY'}.get(name)
        if key_name and os.getenv(key_name):
            headers['X-Api-Key'] = os.environ[key_name]
            headers['X-API-KEY'] = os.environ[key_name]
        req = request.Request(url, headers=headers)
        with request.urlopen(req, timeout=5) as response:
            return response.status < 500
    except (OSError, error.HTTPError):
        return False


def main():
    load_env()
    if not os.getenv('PROWLARR_API_KEY'):
        config_root = Path(os.getenv('CONFIG_ROOT', './config'))
        config_file = config_root / 'prowlarr' / 'config.xml'
        try:
            os.environ['PROWLARR_API_KEY'] = ET.parse(config_file).getroot().findtext('ApiKey', '')
        except (OSError, ET.ParseError):
            pass

    # 1. Check services
    failed = [name for name, url in SERVICES.items() if not check(name, url)]
    if failed:
        msg = f"🔴 *NetFelix Alert: Unhealthy Service(s)*\nServices down: `{', '.join(failed)}`"
        print(msg, file=sys.stderr)
        send_telegram(msg)
        sys.exit(1)

    # 2. Check disk space
    check_disk('/media/dell/Data1', 'Data1 Storage', min_percent=10)
    check_disk('/', 'Root System Disk', min_percent=10)

    print('NetFelix services healthy')


if __name__ == '__main__':
    main()
