#!/usr/bin/env python3
"""Check the local NetFelix services and optionally notify a webhook."""
import json
import os
from pathlib import Path
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
    'watch-now': 'http://127.0.0.1:8090/health',
    'jellyfin': 'http://127.0.0.1:8096/health',
    'jellyseerr': 'http://127.0.0.1:5055/api/v1/status',
    'radarr': 'http://127.0.0.1:7878/api/v3/system/status',
    'sonarr': 'http://127.0.0.1:8989/api/v3/system/status',
    'prowlarr': 'http://127.0.0.1:9696/api/v1/system/status',
    'bazarr': 'http://127.0.0.1:6767/api/providers',
    'qbittorrent': 'http://127.0.0.1:8080/api/v2/app/version',
}


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


def notify(message):
    url = os.getenv('NETFELIX_NOTIFY_URL')
    if not url:
        return
    body = json.dumps({'content': message, 'message': message}).encode()
    req = request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        request.urlopen(req, timeout=8).close()
    except OSError:
        pass


load_env()
if not os.getenv('PROWLARR_API_KEY'):
    config_root = Path(os.getenv('CONFIG_ROOT', './config'))
    config_file = config_root / 'prowlarr' / 'config.xml'
    try:
        os.environ['PROWLARR_API_KEY'] = ET.parse(config_file).getroot().findtext('ApiKey', '')
    except (OSError, ET.ParseError):
        pass
failed = [name for name, url in SERVICES.items() if not check(name, url)]
if failed:
    message = 'NetFelix unhealthy services: ' + ', '.join(failed)
    print(message, file=sys.stderr)
    notify(message)
    raise SystemExit(1)
print('NetFelix services healthy')
