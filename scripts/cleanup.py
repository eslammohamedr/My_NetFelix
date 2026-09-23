#!/usr/bin/env python3
"""Report old completed downloads; --apply removes torrent jobs, never files."""
import argparse
import json
import os
from datetime import datetime, timezone
from urllib import parse, request


def call(endpoint, data=None):
    base = os.getenv('QBT_URL', 'http://127.0.0.1:8080').rstrip('/')
    body = parse.urlencode(data).encode() if data else None
    req = request.Request(base + '/api/v2/' + endpoint, data=body, headers={'Referer': base})
    with request.urlopen(req, timeout=10) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--days', type=float, default=14, help='minimum age since last activity')
parser.add_argument('--apply', action='store_true', help='remove old torrent jobs but keep downloaded files')
args = parser.parse_args()
now = datetime.now(timezone.utc).timestamp()
old = []
for torrent in call('torrents/info'):
    if torrent.get('progress', 0) < 1 or torrent.get('state') not in {'uploading', 'stalledUP', 'pausedUP'}:
        continue
    if now - torrent.get('last_activity', now) < args.days * 86400:
        continue
    old.append(torrent)
for torrent in old:
    print(f"{torrent['hash']}  {torrent['name']}  last activity {torrent.get('last_activity')}")
if args.apply and old:
    call('torrents/delete', {'hashes': '|'.join(t['hash'] for t in old), 'deleteFiles': 'false'})
    print(f'Removed {len(old)} torrent jobs; downloaded files were kept.')
elif not old:
    print('No old completed torrent jobs found.')
else:
    print(f'{len(old)} jobs eligible. Re-run with --apply to remove torrent jobs only.')
