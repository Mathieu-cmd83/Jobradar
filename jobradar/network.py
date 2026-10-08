"""Bounded public HTTPS requests, explicit redirects and robots policy."""
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = 'JobRadar/5.0 (public job aggregator; no candidate accounts)'
MAX_BYTES = 4 * 1024 * 1024


class SourceError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def safe_url(url, source):
    parts = urlsplit(str(url))
    try:
        port = parts.port
    except ValueError:
        return False
    return (parts.scheme == 'https' and parts.hostname in source.domains and port in (None, 443)
            and not parts.username and not parts.password)


class PublicClient:
    def __init__(self, source, *, session=None, delay=1.0):
        self.source = source
        self.session = session or requests.Session()
        self.delay = max(1.0, delay)
        self.last_request = None
        self.policies = {}
        self.deadline = time.monotonic() + 90
        self.request_count = 0

    def _request(self, url):
        if not safe_url(url, self.source):
            raise SourceError('access_blocked', 'Destination HTTPS non approuvée pour cette source.')
        if self.request_count >= 50 or time.monotonic() + self.delay + 1 >= self.deadline:
            raise SourceError('budget_exceeded', 'Budget de collecte atteint (90 s, 50 requêtes maximum).')
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        self.request_count += 1
        try:
            remaining = max(1, self.deadline - time.monotonic())
            response = self.session.get(url, timeout=(min(5, remaining), min(20, remaining)), allow_redirects=False, stream=True,
                                        headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
        except requests.RequestException as exc:
            is_proxy = isinstance(exc, requests.exceptions.ProxyError)
            status = 'network_blocked' if is_proxy and '403' in str(exc) else 'network_error'
            raise SourceError(status, 'Accès refusé par le proxy cloud.' if status == 'network_blocked'
                              else 'Source inaccessible : ' + type(exc).__name__) from exc
        return response

    def _read(self, response):
        content = bytearray()
        try:
            for chunk in response.iter_content(65536):
                if time.monotonic() >= self.deadline:
                    raise SourceError('budget_exceeded', 'Lecture interrompue : budget de 90 s atteint.')
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise SourceError('format_error', 'Réponse trop volumineuse (limite 4 Mio).')
            return bytes(content)
        except requests.RequestException as exc:
            raise SourceError('network_error', 'Lecture interrompue : ' + type(exc).__name__) from exc
        finally:
            response.close()

    def _robots(self, url):
        parts = urlsplit(url)
        origin = f'https://{parts.netloc}'
        if origin in self.policies:
            return self.policies[origin]
        robots_url = origin + '/robots.txt'
        target = robots_url
        for _ in range(4):
            response = self._request(target)
            if response.status_code in (301, 302, 303, 307, 308):
                next_url = urljoin(target, response.headers.get('Location', ''))
                response.close()
                if not safe_url(next_url, self.source):
                    raise SourceError('access_blocked', 'Redirection robots vers un domaine non approuvé.')
                target = next_url
                continue
            if response.status_code == 404:
                response.close()
                text = 'User-agent: *\nAllow: /'
            elif response.status_code == 200:
                text = self._read(response).decode('utf-8', errors='replace')
                if '<html' in text[:500].lower():
                    raise SourceError('access_blocked', 'robots.txt remplacé par une page HTML ; règles inconnues.')
            else:
                code = response.status_code
                response.close()
                raise SourceError('access_blocked', f'robots.txt inaccessible (HTTP {code}).')
            parser = RobotFileParser(robots_url)
            parser.parse(text.splitlines())
            delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay('*') or 1
            rate = parser.request_rate(USER_AGENT) or parser.request_rate('*')
            if rate and rate.requests:
                delay = max(delay, rate.seconds / rate.requests)
            if delay > 30:
                raise SourceError('access_blocked', 'Délai robots supérieur à 30 s : collecte automatique suspendue.')
            self.delay = max(self.delay, float(delay))
            self.policies[origin] = parser
            return parser
        raise SourceError('access_blocked', 'Trop de redirections pour robots.txt.')

    def robots(self, url):
        if not safe_url(url, self.source):
            raise SourceError('access_blocked', 'Domaine non approuvé.')
        return self._robots(url)

    def get(self, url):
        for _ in range(4):
            if not safe_url(url, self.source):
                raise SourceError('access_blocked', 'Destination non approuvée.')
            if not self._robots(url).can_fetch(USER_AGENT, url):
                raise SourceError('robots_denied', 'Collecte interdite par robots.txt pour ce chemin.')
            response = self._request(url)
            code = response.status_code
            if code in (301, 302, 303, 307, 308):
                next_url = urljoin(url, response.headers.get('Location', ''))
                response.close()
                if not safe_url(next_url, self.source):
                    raise SourceError('access_blocked', 'Redirection vers un domaine non approuvé.')
                url = next_url
                continue
            if code != 200:
                response.close()
                status = 'rate_limited' if code == 429 else 'access_blocked' if code in (401, 403) else 'http_error'
                raise SourceError(status, f'Source HTTP {code} ; aucun contournement effectué.')
            return self._read(response), url
        raise SourceError('access_blocked', 'Trop de redirections.')
