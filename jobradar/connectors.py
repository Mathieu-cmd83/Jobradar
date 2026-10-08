"""Public RSS and schema.org JobPosting parsers; no guessed agency endpoints."""
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin

import feedparser

from .models import Job, canonical_url, employment_details, parse_datetime, plain_text, description_text, date_precision
from .network import PublicClient, SourceError, safe_url


class TerritorialFields(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}
        self.field = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            if self.field:
                self.depth += 1
            else:
                classes = dict(attrs).get('class', '').split()
                field = next((c for c in classes if c in ('lieutravail', 'employeur', 'datecand')), None)
                if field:
                    self.field, self.depth = field, 1
                    self.fields.setdefault(field, [])

    def handle_endtag(self, tag):
        if tag == 'div' and self.field:
            self.depth -= 1
            if self.depth == 0:
                self.field = None

    def handle_data(self, data):
        if self.field:
            self.fields[self.field].append(data)

    def value(self, field):
        return plain_text(''.join(self.fields.get(field, []))).partition(':')[2].strip()


def parse_rss(data, source):
    parsed = feedparser.parse(data)
    if not parsed.version or (parsed.bozo and not parsed.entries):
        raise SourceError('format_error', 'Flux RSS/Atom illisible ou remplacé par une page HTML.')
    jobs, seen = [], set()
    for entry in parsed.entries:
        title = plain_text(entry.get('title', ''))
        url = canonical_url(entry.get('link', ''))
        if not title or not safe_url(url, source) or url in seen:
            continue
        seen.add(url)
        contents = [c.get('value', '') for c in entry.get('content', []) if isinstance(c, dict)]
        html = max(contents + [str(entry.get('summary', ''))], key=lambda x: len(plain_text(x)))
        description = description_text(html)
        full_time, contract = employment_details(description)
        published = parse_datetime(entry.get('published'))
        updated = parse_datetime(entry.get('updated')) if 'updated' in entry else None
        fields = TerritorialFields()
        if source.id == 'territorial':
            fields.feed(str(entry.get('summary', '')) or html)
        expiry = fields.value('datecand')
        match = re.search(r'\b(\d{2})/(\d{2})/(\d{4})\b', expiry)
        expires_at = parse_datetime(f'{match[3]}-{match[2]}-{match[1]}', end_of_day=True) if match else None
        location = fields.value('lieutravail')
        jobs.append(Job(source.id, source.name, title, url, description[:10000],
                        # Canonical URL survives inconsistent RSS GUIDs or campaign parameters.
                        remote_id=url, employer=fields.value('employeur'), location=location,
                        department='83' if source.var_scope else '',
                        location_verified=bool(source.var_scope or location),
                        rss_published_at=published, rss_updated_at=updated,
                        date_kind='publication RSS' if published else 'mise à jour RSS' if updated else '',
                        expires_at=expires_at, full_time=full_time, contract=contract))
    if parsed.entries and not jobs:
        raise SourceError('format_error', 'Flux reçu, mais aucune annonce avec titre et lien HTTPS approuvé.')
    return jobs


class StructuredPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts, self.links, self.buffer = [], [], []
        self.in_json = False
        self.active_anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('type', '').lower().split(';')[0] == 'application/ld+json':
            self.in_json, self.buffer = True, []
        if tag in ('a', 'link') and attrs.get('href'):
            self.links.append({'href': attrs['href'], 'type': attrs.get('type', ''),
                               'rel': attrs.get('rel', ''), 'text': attrs.get('title', '')})
            if tag == 'a':
                self.active_anchor = self.links[-1]

    def handle_data(self, data):
        if self.in_json:
            self.buffer.append(data)
        elif self.active_anchor is not None:
            self.active_anchor['text'] += data

    def handle_endtag(self, tag):
        if tag == 'a':
            self.active_anchor = None
        if tag == 'script' and self.in_json:
            self.scripts.append(''.join(self.buffer))
            self.in_json = False


def job_nodes(node):
    if isinstance(node, list):
        for item in node:
            yield from job_nodes(item)
    elif isinstance(node, dict):
        types = node.get('@type', [])
        if isinstance(types, str):
            types = [types]
        elif not isinstance(types, list):
            types = []
        if any(t in ('JobPosting', 'https://schema.org/JobPosting', 'http://schema.org/JobPosting') for t in types):
            yield node
        # Supports @graph and ItemList/listItem nesting, not just the root object.
        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from job_nodes(value)


def parse_jobposting(data, source, page_url):
    page = StructuredPage()
    page.feed(data.decode('utf-8', errors='replace') if isinstance(data, bytes) else data)
    jobs, seen, node_count = [], set(), 0
    for script in page.scripts:
        try:
            root = json.loads(script)
            nodes = list(job_nodes(root))
        except (ValueError, RecursionError):
            continue
        for node in nodes:
            node_count += 1
            title = plain_text(node.get('title'))
            # A listing URL is not an individual offer URL. Never synthesize one.
            url = canonical_url(urljoin(page_url, str(node.get('url') or '')))
            if not node.get('url') or not title or not safe_url(url, source) or url in seen:
                continue
            seen.add(url)
            description = description_text(node.get('description'))
            full_time, contract = employment_details(description, node.get('employmentType'))
            places = node.get('jobLocation', [])
            places = places if isinstance(places, list) else [places]
            addresses = [p.get('address', {}) for p in places if isinstance(p, dict)]
            addresses = [a for a in addresses if isinstance(a, dict)]
            locations = [plain_text(a.get('addressLocality')) for a in addresses]
            postal_codes = [str(a.get('postalCode', '')) for a in addresses]
            location = ', '.join(dict.fromkeys(x for x in locations if x))
            postal = ', '.join(dict.fromkeys(x for x in postal_codes if x))
            in_var = any(re.fullmatch(r'83\d{3}', code) for code in postal_codes)
            organization = node.get('hiringOrganization', {})
            identifier = node.get('identifier', {})
            remote_id = str(identifier.get('value', '')) if isinstance(identifier, dict) else str(identifier or '')
            jobs.append(Job(source.id, source.name, title, url, description[:10000],
                            remote_id=remote_id or url,
                            employer=plain_text(organization.get('name')) if isinstance(organization, dict) else '',
                            location=location, postal_code=postal, department='83' if in_var else '',
                            location_verified=bool(addresses and (location or postal)),
                            published_at=parse_datetime(node.get('datePosted')),
                            publication_precision=date_precision(node.get('datePosted')),
                            date_kind='publication' if parse_datetime(node.get('datePosted')) else '',
                            expires_at=parse_datetime(node.get('validThrough'), end_of_day=True),
                            full_time=full_time, contract=contract))
    if not node_count:
        raise SourceError('format_error', 'Aucun JobPosting : page dynamique, format modifié ou endpoint non adapté.')
    if not jobs:
        raise SourceError('format_error', 'JobPosting présents mais sans titre/lien individuel HTTPS exploitable.')
    return jobs


class TrianglePage(HTMLParser):
    """Public permalink metadata, not the disallowed AJAX search backend."""
    def __init__(self):
        super().__init__()
        self.location, self.contract = '', ''
        self.parts = []
        self.criteria_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('data-location') and attrs.get('data-contract'):
            self.location, self.contract = attrs['data-location'], attrs['data-contract']
        if self.criteria_depth and tag not in ('br', 'img', 'input', 'hr', 'meta', 'link'):
            self.criteria_depth += 1
        elif tag == 'section' and 'job-criteria' in attrs.get('class', '').split():
            self.criteria_depth = 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if self.criteria_depth:
            self.criteria_depth -= 1

    def handle_data(self, data):
        if self.criteria_depth:
            self.parts.append(data)


def parse_wordpress_posts(data, source):
    try:
        rows = json.loads(data)
    except (ValueError, RecursionError) as exc:
        raise SourceError('format_error', 'API WordPress : JSON illisible.') from exc
    if not isinstance(rows, list):
        raise SourceError('format_error', 'API WordPress : tableau d’offres attendu.')
    valid = [r for r in rows if isinstance(r, dict) and r.get('type') == 'job'
             and r.get('status') == 'publish' and isinstance(r.get('title'), dict)
             and plain_text(r['title'].get('rendered')) and safe_url(r.get('link', ''), source)
             and r.get('id') and isinstance(r.get('content'), dict) and not r['content'].get('protected')]
    if rows and not valid:
        raise SourceError('format_error', 'API WordPress : aucune offre publique exploitable.')
    return valid


class JobBatch(list):
    def __init__(self, jobs=(), *, partial=False, note='', fetched=None):
        super().__init__(jobs)
        self.partial, self.note = partial, note
        self.fetched = len(self) if fetched is None else fetched


def collect_wordpress(source, client):
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    # Current verified scope is search=Toulon. Do not present it as all Triangle offers in the Var.
    jobs = JobBatch(note='Triangle : recherche Toulon, posts WordPress uniquement ; moteur AJAX exclu.')
    fetched, details = 0, 0
    parts = urlsplit(source.url)
    for page_number in range(1, 4):
        query = dict(parse_qsl(parts.query)) | {'page': str(page_number)}
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))
        data, _ = client.get(url)
        posts = parse_wordpress_posts(data, source)
        fetched += len(posts)
        for post in posts:
            if details >= 30:
                jobs.partial = True
                jobs.note += ' Limite de 30 fiches par collecte atteinte.'
                jobs.fetched = fetched
                return jobs
            details += 1
            body, _ = client.get(post['link'])
            fields = TrianglePage()
            fields.feed(body.decode('utf-8', errors='replace'))
            if not fields.location:
                raise SourceError('format_error', 'Fiche Triangle sans localisation structurée : adapter le connecteur.')
            # Require a structured site label; a search term alone does not establish location.
            match = re.fullmatch(r'(.+),\s*83\s*-\s*Var', fields.location, flags=re.I)
            if not match:
                continue
            description = description_text(post['content']['rendered'])
            full_time, _ = employment_details(plain_text(' '.join(fields.parts)))
            _, contract = employment_details(fields.contract)
            if fields.contract in ('Alternance', 'Apprentissage'):
                contract = 'Apprentissage / alternance'
            elif fields.contract == 'CDII':
                contract = 'Autre'  # CDI intérimaire is not silently mapped to ordinary CDI.
            if contract == 'Non précisé' and fields.contract:
                contract = 'Autre'
            # WP's documented post publication time, never the relative card text or first observation.
            published = parse_datetime(str(post['date_gmt']) + 'Z') if post.get('date_gmt') else parse_datetime(post.get('date'))
            jobs.append(Job(source.id, source.name, plain_text(post['title']['rendered']),
                            canonical_url(post['link']), description[:10000], remote_id=str(post['id']),
                            location=match[1].strip(), department='83', location_verified=True,
                            published_at=published, date_kind='publication sur le site' if published else '',
                            full_time=full_time, contract=contract))
        if len(posts) < int(query.get('per_page', '100')):
            break
    else:
        jobs.partial = True
        jobs.note += ' Limite de 3 pages API atteinte.'
    jobs.fetched = fetched
    return jobs


def collect(source, client=None):
    if not source.enabled or source.access_review not in ('approved', 'public_rss'):
        raise SourceError('review_pending', 'Conditions d’accès non examinées ; collecte désactivée.')
    if source.kind not in ('rss', 'jsonld', 'wordpress'):
        raise SourceError('not_connected', 'Aucun endpoint public vérifié pour cette source.')
    client = client or PublicClient(source)
    if source.kind == 'wordpress':
        return collect_wordpress(source, client)
    data, url = client.get(source.url)
    return parse_rss(data, source) if source.kind == 'rss' else parse_jobposting(data, source, url)
