from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

UTC = timezone.utc
PARIS = ZoneInfo('Europe/Paris')
CONTRACT_OPTIONS = ['CDI', 'CDD', 'Intérim', 'Emploi permanent (fonction publique)',
                    'Emploi temporaire (fonction publique)', 'Contrat de projet',
                    'Apprentissage / alternance', 'Stage', 'Autre', 'Non précisé']
NEAR = ['toulon', 'la seyne sur mer', 'six fours les plages', 'la garde', 'la valette du var',
        'la farlede', 'le pradet', 'carqueiranne', 'ollioules', 'la crau', 'hyeres',
        'sollies pont', 'sollies toucas', 'sollies ville', 'le revest les eaux', 'cuers',
        'saint mandrier sur mer', 'bandol', 'sanary sur mer']


def normalize(value):
    text = unicodedata.normalize('NFKD', str(value or '').casefold())
    return re.sub(r'\s+', ' ', ''.join(c for c in text if not unicodedata.combining(c))
                  .replace('-', ' ').replace('’', "'")).strip()


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('br', 'p', 'div', 'li'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
        self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value):
    parser = TextParser()
    parser.feed(str(value or ''))
    return re.sub(r'\s+', ' ', unescape(''.join(parser.parts))).strip()


class DescriptionParser(TextParser):
    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if not self.hidden and tag in ('p', 'div', 'li', 'br', 'h2', 'h3', 'h4'):
            self.parts.append('\n')
        if not self.hidden and tag == 'li':
            self.parts.append('• ')

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag in ('p', 'div', 'li', 'h2', 'h3', 'h4'):
            self.parts.append('\n')


def description_text(value):
    """Safe text with paragraph/list boundaries, never rendered source HTML."""
    parser = DescriptionParser()
    parser.feed(str(value or ''))
    lines = [re.sub(r'[^\S\n]+', ' ', line).strip() for line in ''.join(parser.parts).splitlines()]
    return '\n'.join(line for line in lines if line)


def date_precision(value):
    return 'day' if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value or '').strip()) else 'time'


def effective_date(job, basis='available'):
    """Observation is never a publication fallback, including legacy V5 RSS rows."""
    rss = job.get('rss_published_at')
    updated = job.get('rss_updated_at')
    published = job.get('published_at')
    if job.get('source_id') == 'territorial' and not job.get('date_schema'):
        if job.get('date_kind') == 'mise à jour':
            updated = published
        else:
            rss = published
        published = None
    if basis == 'publication':
        return published
    if basis == 'rss':
        return rss
    return published or rss or updated


def parse_datetime(value, *, end_of_day=False):
    if not value:
        return None
    try:
        raw = str(value).strip()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
            result = datetime.combine(datetime.fromisoformat(raw).date(), time.min, PARIS)
            if end_of_day:
                result += timedelta(days=1)
        else:
            try:
                result = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            except ValueError:
                result = parsedate_to_datetime(raw)
        if result.tzinfo is None:
            result = result.replace(tzinfo=PARIS)
        return result.astimezone(UTC).isoformat()
    except (ValueError, TypeError, OverflowError, IndexError):
        return None


def canonical_url(value):
    parts = urlsplit(str(value or ''))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(('utm_', 'mtm_')) and k.lower() not in ('gclid', 'fbclid')]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path,
                       urlencode(sorted(query)), ''))


def employment_details(description, employment_type=None):
    text = normalize(description)
    full_time = None
    if re.search(r'\btemps\s+(non\s+complet|partiel)\b', text):
        full_time = False
    elif re.search(r'\btemps\s+(complet|plein)\b', text):
        full_time = True
    types = employment_type if isinstance(employment_type, list) else [employment_type or '']
    if full_time is None:
        if 'PART_TIME' in types:
            full_time = False
        elif 'FULL_TIME' in types:
            full_time = True
    patterns = [
        (r'\bcontrat\s+de\s+projet\b', 'Contrat de projet'),
        (r'\bemploi\s+temporaire\b', 'Emploi temporaire (fonction publique)'),
        (r'\bemploi\s+permanent\b', 'Emploi permanent (fonction publique)'),
        (r'\binterim\b', 'Intérim'),
        (r'\bcontrat\s+d.apprentissage\b|\balternance\b', 'Apprentissage / alternance'),
        (r'\bstage\b|\bstagiaire\b', 'Stage'),
        (r'\bcontrat\s+a\s+duree\s+indeterminee\b|\bcdi\b', 'CDI'),
        (r'\bcontrat\s+a\s+duree\s+determinee\b|\bcdd\b', 'CDD'),
    ]
    contract = next((label for pattern, label in patterns if re.search(pattern, text)), 'Non précisé')
    if contract == 'Non précisé' and 'INTERN' in types:
        contract = 'Stage'
    # TEMPORARY/CONTRACTOR do not establish a French CDD or an interim contract.
    return full_time, contract


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    domains: tuple[str, ...]
    url: str
    kind: str = 'undiscovered'
    enabled: bool = False
    access_review: str = 'pending'
    terms_url: str = ''
    var_scope: bool = False
    review_note: str = ''


@dataclass(frozen=True)
class Job:
    source_id: str
    source_name: str
    title: str
    url: str
    description: str = ''
    remote_id: str = ''
    employer: str = ''
    location: str = ''
    postal_code: str = ''
    department: str = ''
    location_verified: bool = False
    published_at: str | None = None
    date_kind: str = ''
    expires_at: str | None = None
    full_time: bool | None = None
    contract: str = 'Non précisé'
    rss_published_at: str | None = None
    rss_updated_at: str | None = None
    publication_precision: str = 'time'
    date_schema: int = 2

    @property
    def key(self):
        return sha256(f'{self.source_id}:{self.remote_id or canonical_url(self.url)}'.encode()).hexdigest()

    def payload(self):
        return asdict(self)
