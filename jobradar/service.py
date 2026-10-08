from datetime import datetime, timedelta
from hashlib import sha256
import threading

from .connectors import collect
from .models import NEAR, PARIS, UTC, canonical_url, normalize
from .network import SourceError

REFRESH_LOCK = threading.Lock()


def in_var(job):
    if job.department == '83':
        return True
    # Agency jobLocation must explicitly name a recognized municipality or postal code.
    cities = {normalize(x.strip()) for x in job.location.split(',') if x.strip()}
    return job.location_verified and bool(cities.intersection(NEAR))


def refresh(sources, store, *, force=False, now=None, collector=collect):
    now = now or datetime.now(UTC)
    with REFRESH_LOCK:
        states = store.states()
        for source in sources:
            if not source.enabled:
                continue
            state = states.get(source.id)
            # Errors use a 15-minute backoff; the refresh button is subject to it too.
            interval = timedelta(hours=1) if state and state['status'] in ('ok', 'empty', 'partial') else timedelta(minutes=15)
            if state:
                age = now - datetime.fromisoformat(state['checked_at'])
                if age < interval and (not force or state['status'] not in ('ok', 'empty', 'partial')):
                    continue
                if force and age < timedelta(minutes=1):
                    continue
            try:
                jobs = collector(source)
                local = [job for job in jobs if in_var(job)]
                store.record_success(source, local, fetched=getattr(jobs, 'fetched', len(jobs)), now=now,
                                     partial=getattr(jobs, 'partial', False), note=getattr(jobs, 'note', ''))
            except SourceError as exc:
                store.record_error(source.id, exc.status, str(exc), now)


def deduplicate(records):
    """Conservative cross-source grouping with all origins retained.

    Same canonical URL, or identical title+employer+verified location+date+
    contract+description. Title-only matches are deliberately insufficient.
    """
    parents = list(range(len(records)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    fingerprints = {}
    for i, job in enumerate(records):
        keys = [('url', canonical_url(job['url']))]
        if job.get('employer') and job.get('location_verified') and job.get('location') and job.get('published_at') and job.get('description'):
            keys.append(('content', sha256('|'.join([
                normalize(job['title']), normalize(job['employer']), normalize(job['location']),
                job['published_at'], job.get('contract', ''), normalize(job['description'])]).encode()).hexdigest()))
        for key in keys:
            if key in fingerprints:
                parents[find(i)] = find(fingerprints[key])
            else:
                fingerprints[key] = i
    groups = {}
    for i, job in enumerate(records):
        groups.setdefault(find(i), []).append(job)
    result = []
    for entries in groups.values():
        # No agency ranking: the freshest observation supplies display fields.
        entries.sort(key=lambda j: (j.get('last_seen', ''), j['source_id']), reverse=True)
        row = dict(entries[0])
        row['origins'] = [{'source_id': j['source_id'], 'source_name': j['source_name'], 'url': j['url'],
                           'last_seen': j.get('last_seen', '')} for j in entries]
        row['first_seen'] = min(j.get('first_seen', '') for j in entries)
        row['last_seen'] = max(j.get('last_seen', '') for j in entries)
        result.append(row)
    return result


def filter_jobs(jobs, *, selected_sources=None, keywords='', title_only=False, category_terms=(),
                zone='var', location='', hours='any', contracts=(), start=None, end=None,
                since=None, include_expired=False, now=None, sort='recent'):
    now = now or datetime.now(UTC)
    results, unknown = [], 0
    for job in jobs:
        row = dict(job)
        if selected_sources is not None:
            row['origins'] = [o for o in row['origins'] if o['source_id'] in selected_sources]
            if not row['origins']:
                continue
        expiry = datetime.fromisoformat(row['expires_at']) if row.get('expires_at') else None
        row['expired'] = bool(expiry and expiry <= now)
        row['stale'] = bool(row.get('last_seen') and datetime.fromisoformat(row['last_seen']) < now - timedelta(days=7))
        if row['expired'] and not include_expired:
            continue
        full_text = normalize(row['title'] + ' ' + row.get('description', ''))
        text = normalize(row['title']) if title_only else full_text
        if category_terms and not any(term in text for term in category_terms):
            continue
        if not all(term in text for term in normalize(keywords).split()):
            continue
        local = normalize(row.get('location', ''))
        if zone == 'near':
            if row.get('location'):
                if not any(normalize(p.strip()) in NEAR for p in row['location'].split(',')):
                    continue
            elif not any(city in full_text for city in NEAR):
                continue
        if location and normalize(location) not in (local if local else full_text):
            continue
        if hours == 'full' and row.get('full_time') is not True:
            continue
        if hours == 'part' and row.get('full_time') is not False:
            continue
        if hours == 'unknown' and row.get('full_time') is not None:
            continue
        if contracts and row.get('contract') not in contracts:
            continue
        published = datetime.fromisoformat(row['published_at']) if row.get('published_at') else None
        if start or end or since:
            if published is None:
                unknown += 1
                continue
            local_date = published.astimezone(PARIS).date()
            if (start and local_date < start) or (end and local_date > end) or (since and published < since):
                continue
        results.append(row)
    minimum = datetime.min.replace(tzinfo=UTC)
    if sort == 'title':
        results.sort(key=lambda j: normalize(j['title']))
    else:
        dated = [j for j in results if j.get('published_at')]
        undated = [j for j in results if not j.get('published_at')]
        dated.sort(key=lambda j: datetime.fromisoformat(j['published_at']) if j.get('published_at') else minimum,
                   reverse=sort != 'oldest')
        results = dated + undated
    return results, unknown
