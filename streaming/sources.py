"""Legal, public-domain source discovery helpers."""
import json
from urllib import parse, request


def internet_archive_search(query, limit=12):
    params = parse.urlencode({
        'q': f'({query}) AND mediatype:movies',
        'fl[]': ['identifier', 'title', 'description', 'year'],
        'rows': max(1, min(int(limit), 50)),
        'output': 'json',
    }, doseq=True)
    req = request.Request('https://archive.org/advancedsearch.php?' + params, headers={'User-Agent': 'NetFelix/1.0'})
    with request.urlopen(req, timeout=12) as response:
        docs = json.load(response).get('response', {}).get('docs', [])
    results = []
    for doc in docs:
        identifier = doc.get('identifier')
        if not identifier:
            continue
        results.append({
            'identifier': identifier,
            'title': doc.get('title') or identifier,
            'year': doc.get('year'),
            'description': doc.get('description'),
            'url': f'https://archive.org/details/{parse.quote(identifier)}',
        })
    return results
