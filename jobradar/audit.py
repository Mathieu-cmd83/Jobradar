"""Access discovery only. A reachable homepage is never a connected source."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from urllib.parse import urljoin, urlsplit

from .connectors import StructuredPage, job_nodes
from .models import UTC, plain_text
from .network import PublicClient, SourceError, USER_AGENT, safe_url


def audit_source(source, client_factory=PublicClient):
    result = {'source_id': source.id, 'name': source.name, 'domain': source.domains[-1],
              'checked_at': datetime.now(UTC).isoformat(), 'connected': False,
              'probed_url': 'https://' + urlsplit(source.url).netloc + '/robots.txt',
              'rss_candidates': [], 'api_candidates': [], 'jobposting_nodes': 0,
              'terms_candidates': [], 'sitemaps': []}
    try:
        client = client_factory(source)
        policy = client.robots(source.url)
        result['sitemaps'] = policy.site_maps() or []
        home_url = source.url if source.id == 'adecco' else 'https://' + urlsplit(source.url).netloc + '/'
        result['robots_allowed_homepage'] = policy.can_fetch(USER_AGENT, home_url)
        data, final_url = client.get(home_url)
        result['homepage_url'] = final_url
        page = StructuredPage()
        page.feed(data.decode('utf-8', errors='replace'))
        for script in page.scripts:
            try:
                result['jobposting_nodes'] += len(list(job_nodes(json.loads(script))))
            except (ValueError, RecursionError):
                pass
        for link in page.links:
            url = urljoin(final_url, link['href'])
            if not safe_url(url, source):
                continue
            if link['type'] in ('application/rss+xml', 'application/atom+xml'):
                result['rss_candidates'].append(url)
            if any(term in url.lower() for term in ('conditions', '/cgu', 'terms')):
                result['terms_candidates'].append(url)
        result['terms_candidates'] = sorted(set(result['terms_candidates']))[:3]
        result['terms_evidence'] = []
        for url in result['terms_candidates']:
            try:
                terms_data, terms_url = client.get(url)
                result['terms_evidence'].append({'url': terms_url, 'excerpt': plain_text(terms_data.decode('utf-8', errors='replace'))[:5000]})
            except SourceError as exc:
                result['terms_evidence'].append({'url': url, 'status': exc.status})
        result['status'] = 'review_pending'
        result['message'] = ('Site accessible. Conditions et endpoint d’annonces à examiner avant activation ; '
                             'aucune API/RSS d’annonces confirmée par cette seule découverte.')
        if source.access_review == 'restricted':
            result.update(status='terms_restricted', message=source.review_note, terms_url=source.terms_url)
        elif source.enabled:
            result.update(status='connector_implemented', message=source.review_note,
                          terms_url=source.terms_url, connector=source.kind, endpoint=source.url)
    except SourceError as exc:
        result.update(status=exc.status, message=str(exc))
    return result


def audit_agencies(sources):
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(audit_source, (s for s in sources if s.id != 'territorial')))
