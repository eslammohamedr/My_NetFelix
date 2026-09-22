"""Resolve a Jellyseerr title to exact download IDs; never guess by title text."""
import json
import os
from pathlib import Path
import re
from urllib import parse, request

VIDEO_EXTENSIONS = {'.mp4', '.m4v', '.webm', '.mkv', '.avi', '.mov', '.ts'}


class CatalogError(Exception):
    pass


def api(service, route, **params):
    defaults = {'JELLYSEERR': ('5055', 'v1'), 'RADARR': ('7878', 'v3'), 'SONARR': ('8989', 'v3')}
    port, version = defaults[service]
    key = os.getenv(service + '_API_KEY', '')
    if not key:
        raise CatalogError(f'{service.title()} connection is not configured on the streaming server.')
    base = os.getenv(service + '_URL', f'http://127.0.0.1:{port}').rstrip('/')
    url = f'{base}/api/{version}/{route}'
    if params:
        url += '?' + parse.urlencode(params)
    req = request.Request(url, headers={'X-Api-Key': key})
    with request.urlopen(req, timeout=15) as response:
        return json.load(response)


def download_ids(records, field, media_id):
    return {
        str(record.get('downloadId', '')).lower()
        for record in records
        if record.get(field) == media_id
        and re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', str(record.get('downloadId', '')))
    }


def resolve(media_type, tmdb_id, qbt):
    detail = api('JELLYSEERR', f'{media_type}/{tmdb_id}')
    media = detail.get('mediaInfo') or {}
    result = {'title': detail.get('title') or detail.get('name') or 'Watch now',
              'media_type': media_type, 'tmdb_id': tmdb_id, 'downloads': [],
              'state': 'waiting', 'message': 'Waiting for a download to be selected. This page will update automatically.',
              'library_path': None, 'arr_id': None, 'dates': {}}
    # Construct the library URL in the browser using its server hostname, not a query-supplied URL.
    if media.get('jellyfinMediaId') and re.fullmatch(r'[a-fA-F0-9-]+', media['jellyfinMediaId']):
        result['library_path'] = '/web/index.html#!/details?id=' + media['jellyfinMediaId']
    status = media.get('status', 1)
    if status == 6:
        result.update(state='blocked', message='This title is blocked in Jellyseerr.')
        return result
    requests = media.get('requests') or []
    if status == 2:
        result.update(state='approval', message='Your request is waiting for approval in Jellyseerr.')
        return result
    if status in (1, 7) and not requests:
        result.update(state='request', message='Request this title in Jellyseerr to start downloading.')
        return result

    service, route, field = ('RADARR', 'movie', 'movieId') if media_type == 'movie' else ('SONARR', 'series', 'seriesId')
    identity = 'tmdbId' if media_type == 'movie' else 'tvdbId'
    external_id = tmdb_id if media_type == 'movie' else (detail.get('externalIds') or {}).get('tvdbId')
    if not external_id:
        result['message'] = 'The series identifier is not available yet. Check the request in Jellyseerr.'
        return result
    matches = api(service, route, **{identity: external_id})
    title = next((m for m in matches if m.get(identity) == external_id), None)
    if title is None:
        if result['library_path']:
            result.update(state='library', message='This title is available in Jellyfin.')
        return result
    media_id = title['id']
    result['arr_id'] = media_id
    result['quality_profile_id'] = title.get('qualityProfileId')
    req_tags = set(title.get('tags') or [])
    for r in requests:
        req_tags.update(r.get('tags') or [])
    is_arabic_dub = (title.get('qualityProfileId') == 7) or any(r.get('profileId') == 7 for r in requests) or (1 in req_tags)
    result['is_arabic_dub'] = is_arabic_dub
    result['dates'] = {
        'inCinemas': (title.get('inCinemas') or '').split('T')[0],
        'digitalRelease': (title.get('digitalRelease') or '').split('T')[0],
        'physicalRelease': (title.get('physicalRelease') or '').split('T')[0],
        'status': title.get('status', '')
    }
    hashes = set()
    # Include queue and history: imports can remove queue entries before the torrent disappears.
    for page in range(1, 101):
        queue = api(service, 'queue', page=page, pageSize=100)
        records = queue.get('records', [])
        hashes.update(download_ids(records, field, media_id))
        if page * 100 >= queue.get('totalRecords', len(records)):
            break
    history = api(service, f'history/{route}', **{field: media_id})
    hashes.update(download_ids(history, field, media_id))
    for torrent in qbt.call('torrents/info'):
        if torrent['hash'].lower() not in hashes:
            continue
        files = qbt.call('torrents/files', hash=torrent['hash'])
        videos = [{'index': f['index'], 'name': f['name'], 'size': f['size'], 'progress': f['progress']}
                  for f in files if Path(f['name']).suffix.lower() in VIDEO_EXTENSIONS]
        # Prefer the actual feature over a sample/trailer when opening a movie automatically.
        if media_type == 'movie' and videos:
            videos = [max(videos, key=lambda f: f['size'])]
        result['downloads'].append({k: torrent.get(k) for k in ('hash', 'name', 'progress', 'state', 'dlspeed')} | {'files': videos})
    arabic_pat = re.compile(r'\b(arabic|ara|ar[-_.]?dub|dubbed[-_.]?ar|ar[-_.]?audio|مدبلج|دبلجة|الدبلجة|مدبلجة)\b', re.IGNORECASE)
    has_arabic = any(
        bool(arabic_pat.search(t.get('name', '')) or any(arabic_pat.search(f.get('name', '')) for f in t.get('files', [])))
        for t in result['downloads']
    )
    result['has_arabic_dub'] = has_arabic
    result['arabic_dub_missing'] = bool(result['is_arabic_dub'] and not has_arabic)
    playable = [t for t in result['downloads'] if t['files'] and t['state'] not in {
        'missingFiles', 'error', 'moving', 'checkingDL', 'checkingUP', 'checkingResumeData'}]
    if playable:
        result.update(state='download', message='Preparing your video…')
    elif result['downloads']:
        result['message'] = 'Waiting for download metadata or files. Check the download state below.'
    elif result['library_path']:
        result.update(state='library', message='This title is available in Jellyfin.')
    elif any(r.get('status') in (3, 4) for r in requests):
        result.update(state='failed', message='The request was declined or failed. Check it in Jellyseerr.')
    elif not result['downloads']:
        title_status = title.get('status', '')
        digital_date = result['dates'].get('digitalRelease', '')
        cinema_date = result['dates'].get('inCinemas', '')
        service_name = 'Radarr' if media_type == 'movie' else 'Sonarr'
        if title_status == 'inCinemas' or (cinema_date and digital_date and not result['downloads'] and title_status != 'released'):
            result['state'] = 'in_cinemas'
            date_info = f' (digital release expected around {digital_date})' if digital_date else ''
            result['message'] = f'This movie is currently in theaters{date_info}. No HD digital releases exist yet on indexers (only low-quality theater recordings, which are filtered out by your HD profile).'
        elif title_status == 'announced':
            result['state'] = 'announced'
            result['message'] = f'This title has not been released yet. {service_name} will automatically download it once a release becomes available.'
        else:
            result['state'] = 'not_found'
            if result.get('is_arabic_dub'):
                result['message'] = f'No Arabic-dubbed (مدبلج) release was found on indexers for {result["title"]}. You can check Prowlarr or try searching in {service_name}.'
            else:
                result['message'] = f'No active download found for {result["title"]}. {service_name} searched indexers but no matching releases were grabbed yet.'
    return result
