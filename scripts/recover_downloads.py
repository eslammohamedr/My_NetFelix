#!/usr/bin/env python3
"""Reannounce stalled qBittorrent jobs without deleting data."""
import json
import os
import sys
from urllib import error, parse, request


def call(endpoint, data=None):
    base = os.getenv('QBT_URL', 'http://127.0.0.1:8080').rstrip('/')
    body = parse.urlencode(data).encode() if data else None
    req = request.Request(base + '/api/v2/' + endpoint, data=body, headers={'Referer': base})
    with request.urlopen(req, timeout=10) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def main():
    try:
        stalled = [t for t in call('torrents/info') if t.get('state') == 'stalledDL']
        for torrent in stalled:
            call('torrents/reannounce', {'hashes': torrent['hash']})
            print(f"Reannounced: {torrent['name']}")
        if not stalled:
            print('No stalled downloads found.')
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f'qBittorrent recovery unavailable: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
