from dataclasses import replace
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from jobradar.connectors import collect, collect_wordpress, parse_jobposting, parse_rss, JobBatch
from jobradar.models import Job, Source, UTC, canonical_url, employment_details, parse_datetime
from jobradar.network import MAX_BYTES, PublicClient, SourceError
from jobradar.registry import SOURCES
from jobradar.service import deduplicate, filter_jobs, refresh
from jobradar.storage import Store
from jobradar.audit import audit_source

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)
SOURCE = Source('test', 'Test', ('jobs.example',), 'https://jobs.example/offres',
                kind='jsonld', enabled=True, access_review='approved')
TERRITORIAL = SOURCES[0]


def offer(**kwargs):
    values = dict(source_id='test', source_name='Test', title='Magasinier',
                  url='https://jobs.example/offre/1', remote_id='1', employer='Employeur',
                  location='Toulon', postal_code='83000', department='83', location_verified=True,
                  description='CDI à temps plein en entrepôt', contract='CDI', full_time=True,
                  published_at='2026-10-07T12:00:00+00:00', date_kind='publication')
    values.update(kwargs)
    return Job(**values)


def response(code, data=b'', headers=None):
    result = Mock(status_code=code, headers=headers or {})
    result.iter_content.return_value = [data]
    return result


class ParsingTests(unittest.TestCase):
    def test_rss_fields_tracking_and_invalid_links(self):
        xml = b'''<rss version="2.0"><channel><title>Offers</title><item>
        <title>Agent</title><link>https://www.emploi-territorial.fr/offre/1?mtm_campaign=rss</link>
        <pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate><description><![CDATA[
        <div class="employeur"><strong>Employeur :</strong> Ville de Toulon</div>
        <div class="lieutravail"><strong>Lieu de travail :</strong> Toulon</div>
        <div class="datecand"><strong>Date limite :</strong> 09/10/2026</div>
        Emploi permanent ; temps non complet]]></description></item>
        <item><title>Duplicate</title><link>https://www.emploi-territorial.fr/offre/1</link></item>
        <item><title>Unsafe</title><link>https://example.org/job</link></item></channel></rss>'''
        jobs = parse_rss(xml, TERRITORIAL)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].location, 'Toulon')
        self.assertEqual(jobs[0].employer, 'Ville de Toulon')
        self.assertFalse(jobs[0].full_time)
        self.assertEqual(jobs[0].contract, 'Emploi permanent (fonction publique)')
        self.assertEqual(jobs[0].expires_at, '2026-10-09T22:00:00+00:00')

    def test_html_instead_of_rss_fails(self):
        with self.assertRaises(SourceError):
            parse_rss(b'<html><body>CAPTCHA</body></html>', TERRITORIAL)

    def test_empty_feed_is_not_format_error(self):
        self.assertEqual(parse_rss(b'<rss version="2.0"><channel><title>Empty</title></channel></rss>', TERRITORIAL), [])

    def test_unknown_fields_not_invented(self):
        xml = b'<rss version="2.0"><channel><item><title>CDI chauffeur</title><link>https://www.emploi-territorial.fr/offre/1</link></item></channel></rss>'
        job = parse_rss(xml, TERRITORIAL)[0]
        self.assertIsNone(job.published_at)
        self.assertIsNone(job.full_time)
        self.assertEqual(job.contract, 'Non précisé')

    def test_jsonld_graph_locations_and_expiry(self):
        node = {'@type': 'JobPosting', 'title': 'Technicien', 'url': '/offre/7',
                'description': '<p>CDD</p>', 'employmentType': ['PART_TIME'],
                'datePosted': '2026-10-07', 'validThrough': '2026-11-01',
                'hiringOrganization': {'name': 'Entreprise'}, 'identifier': {'value': '7'},
                'jobLocation': [{'address': {'addressLocality': 'Toulon', 'postalCode': '83000'}}]}
        html = '<script type="application/ld+json">' + json.dumps({'@graph': [node]}) + '</script>'
        jobs = parse_jobposting(html, SOURCE, SOURCE.url)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].url, 'https://jobs.example/offre/7')
        self.assertEqual(jobs[0].department, '83')
        self.assertFalse(jobs[0].full_time)
        self.assertEqual(jobs[0].contract, 'CDD')
        self.assertEqual(jobs[0].published_at, '2026-10-06T22:00:00+00:00')

    def test_jsonld_does_not_use_listing_url_as_offer(self):
        for node in ({'@type': 'JobPosting', 'title': 'Agent'},
                     {'@type': 'JobPosting', 'title': 'Agent', 'url': 'https://evil.example/job'}):
            html = '<script type="application/ld+json">' + json.dumps(node) + '</script>'
            with self.assertRaises(SourceError):
                parse_jobposting(html, SOURCE, SOURCE.url)

    def test_no_jobposting_cannot_be_success(self):
        with self.assertRaises(SourceError):
            parse_jobposting('<html>Search app loading</html>', SOURCE, SOURCE.url)

    def test_public_employment_and_temporary_not_cdi_cdd(self):
        self.assertEqual(employment_details('Emploi permanent temps complet'), (True, 'Emploi permanent (fonction publique)'))
        self.assertEqual(employment_details('', 'TEMPORARY'), (None, 'Non précisé'))
        self.assertIsNone(parse_datetime('not a date'))
        self.assertEqual(canonical_url('https://jobs.example/j?id=7&utm_source=x#top'), 'https://jobs.example/j?id=7')


class NetworkTests(unittest.TestCase):
    def client(self, replies):
        session = Mock()
        session.get.side_effect = replies
        return PublicClient(SOURCE, session=session), session

    @patch('jobradar.network.time.sleep')
    def test_robots_denial_prevents_job_request(self, sleep):
        client, session = self.client([response(200, b'User-agent: *\nDisallow: /offres')])
        with self.assertRaises(SourceError) as caught:
            client.get(SOURCE.url)
        self.assertEqual(caught.exception.status, 'robots_denied')
        self.assertEqual(session.get.call_count, 1)

    @patch('jobradar.network.time.sleep')
    def test_redirect_does_not_follow_unknown_host(self, sleep):
        client, session = self.client([response(200, b'User-agent: *\nAllow: /'),
                                       response(302, headers={'Location': 'https://unapproved.example/offres'})])
        with self.assertRaises(SourceError):
            client.get(SOURCE.url)
        self.assertEqual(session.get.call_count, 2)

    @patch('jobradar.network.time.sleep')
    def test_robots_missing_allows_but_forbidden_does_not(self, sleep):
        client, _ = self.client([response(404), response(200, b'offers')])
        self.assertEqual(client.get(SOURCE.url)[0], b'offers')
        client, session = self.client([response(403)])
        with self.assertRaises(SourceError):
            client.get(SOURCE.url)
        self.assertEqual(session.get.call_count, 1)

    @patch('jobradar.network.time.sleep')
    def test_rate_limited_no_retries(self, sleep):
        client, session = self.client([response(200, b'User-agent: *\nAllow: /'), response(429)])
        with self.assertRaises(SourceError) as caught:
            client.get(SOURCE.url)
        self.assertEqual(caught.exception.status, 'rate_limited')
        self.assertEqual(session.get.call_count, 2)

    @patch('jobradar.network.time.sleep')
    def test_payload_limit_preserves_failed_state(self, sleep):
        client, _ = self.client([response(200, b'User-agent: *\nAllow: /'), response(200, b'x' * (MAX_BYTES + 1))])
        with self.assertRaises(SourceError):
            client.get(SOURCE.url)

    def test_proxy_failure_classified_without_credentials(self):
        client, _ = self.client([requests.exceptions.ProxyError('CONNECT 403')])
        with self.assertRaises(SourceError) as caught:
            client.get(SOURCE.url)
        self.assertEqual(caught.exception.status, 'network_blocked')

    def test_unreviewed_source_not_requested(self):
        client = Mock()
        with self.assertRaises(SourceError):
            collect(replace(SOURCE, access_review='pending'), client)
        client.get.assert_not_called()

    def test_budget_enforced_before_network(self):
        client, session = self.client([])
        client.deadline = 0
        with self.assertRaises(SourceError) as caught:
            client.get(SOURCE.url)
        self.assertEqual(caught.exception.status, 'budget_exceeded')
        session.get.assert_not_called()


class WordPressTests(unittest.TestCase):
    def setUp(self):
        self.source = replace(SOURCE, kind='wordpress', url='https://jobs.example/wp-json/wp/v2/job?search=Toulon&per_page=100')
        self.detail = b'''<button data-location="Toulon, 83 - Var" data-contract="Int\xc3\xa9rim"></button>
            <section class="job-criteria"><div><label>Type d'emploi :</label><span>Temps plein</span></div></section>'''

    def post(self, identifier=1):
        return {'id': identifier, 'type': 'job', 'status': 'publish',
                'link': 'https://jobs.example/offre/' + str(identifier),
                'title': {'rendered': 'Stagiaire'}, 'content': {'rendered': '<p>Description</p>', 'protected': False},
                'date_gmt': '2026-10-07T10:00:00'}

    def test_public_api_and_permalink_metadata(self):
        client = Mock()
        client.get.side_effect = [(json.dumps([self.post()]).encode(), self.source.url), (self.detail, 'unused')]
        jobs = collect_wordpress(self.source, client)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].location, 'Toulon')
        self.assertEqual(jobs[0].contract, 'Intérim')
        self.assertTrue(jobs[0].full_time)
        self.assertEqual(jobs[0].published_at, '2026-10-07T10:00:00+00:00')
        self.assertIn('sur le site', jobs[0].date_kind)
        self.assertFalse(jobs.partial)

    def test_permalink_schema_drift_fails(self):
        client = Mock()
        client.get.side_effect = [(json.dumps([self.post()]).encode(), self.source.url), (b'<html>Layout changed</html>', 'unused')]
        with self.assertRaises(SourceError):
            collect_wordpress(self.source, client)

    def test_bound_on_details_reports_partial(self):
        posts = [self.post(i) for i in range(40)]
        client = Mock()
        client.get.side_effect = [(json.dumps(posts).encode(), self.source.url)] + [(self.detail, 'unused')] * 30
        jobs = collect_wordpress(self.source, client)
        self.assertEqual(len(jobs), 30)
        self.assertTrue(jobs.partial)
        self.assertEqual(client.get.call_count, 31)

    def test_discovery_never_claims_connected(self):
        client = Mock()
        client.robots.return_value.site_maps.return_value = []
        client.get.return_value = (b'<html>Public homepage</html>', SOURCE.url)
        result = audit_source(replace(SOURCE, enabled=False, access_review='restricted', review_note='Restriction'),
                              client_factory=Mock(return_value=client))
        self.assertFalse(result['connected'])
        self.assertEqual(result['status'], 'terms_restricted')


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'jobs.sqlite3')

    def test_repeatability_change_history_and_disappearance(self):
        self.assertEqual(self.store.record_success(SOURCE, [offer()], fetched=1, now=NOW), (1, 0))
        self.assertEqual(self.store.record_success(SOURCE, [offer()], fetched=1, now=NOW + timedelta(hours=1)), (0, 0))
        changed = offer(description='CDI avec une nouvelle description')
        self.assertEqual(self.store.record_success(SOURCE, [changed], fetched=1, now=NOW + timedelta(hours=2)), (0, 1))
        self.store.record_success(SOURCE, [], fetched=0, now=NOW + timedelta(hours=3))
        self.assertEqual(len(self.store.jobs()), 1)
        self.assertEqual(len(self.store.history()), 2)
        self.assertEqual(self.store.jobs()[0]['first_seen'], NOW.isoformat())
        self.assertEqual(self.store.states()['test']['status'], 'empty')

    def test_source_failure_preserves_jobs_and_last_success(self):
        self.store.record_success(SOURCE, [offer()], fetched=1, now=NOW)
        self.store.record_error('test', 'network_error', 'Unavailable', NOW + timedelta(hours=1))
        self.assertEqual(len(self.store.jobs()), 1)
        self.assertEqual(self.store.states()['test']['last_nonempty_success'], NOW.isoformat())
        self.assertEqual(self.store.states()['test']['status'], 'network_error')

    def test_refresh_ttl_error_backoff_and_inactive_source(self):
        collector = Mock(return_value=[offer()])
        inactive = replace(SOURCE, id='inactive', enabled=False)
        refresh([SOURCE, inactive], self.store, collector=collector, now=NOW)
        refresh([SOURCE], self.store, collector=collector, now=NOW + timedelta(seconds=10), force=True)
        self.assertEqual(collector.call_count, 1)
        collector.side_effect = SourceError('network_error', 'offline')
        refresh([SOURCE], self.store, collector=collector, now=NOW + timedelta(hours=1))
        refresh([SOURCE], self.store, collector=collector, now=NOW + timedelta(hours=1, minutes=1), force=True)
        self.assertEqual(collector.call_count, 2)
        self.assertEqual(len(self.store.jobs()), 1)

    def test_outside_var_not_imported(self):
        outside = offer(location='Paris', postal_code='75001', department='')
        refresh([SOURCE], self.store, collector=Mock(return_value=[outside]), now=NOW)
        self.assertEqual(self.store.jobs(), [])
        self.assertEqual(self.store.states()['test']['fetched'], 1)

    def test_partial_success_has_its_own_status(self):
        batch = JobBatch([offer()], partial=True, fetched=40, note='Partial fixture')
        refresh([SOURCE], self.store, collector=Mock(return_value=batch), now=NOW)
        state = self.store.states()['test']
        self.assertEqual(state['status'], 'partial')
        self.assertEqual(state['fetched'], 40)
        self.assertEqual(state['last_nonempty_success'], NOW.isoformat())


class FilteringTests(unittest.TestCase):
    def records(self, *jobs):
        return [dict(j.payload(), first_seen=NOW.isoformat(), last_seen=NOW.isoformat()) for j in jobs]

    def test_cross_source_dedup_preserves_every_origin(self):
        a = offer()
        b = offer(source_id='other', source_name='Other', url='https://other.example/j/2', remote_id='2')
        merged = deduplicate(self.records(a, b))
        self.assertEqual(len(merged), 1)
        self.assertEqual({o['source_id'] for o in merged[0]['origins']}, {'test', 'other'})
        self.assertEqual(len(filter_jobs(merged, selected_sources={'other'}, now=NOW)[0]), 1)
        self.assertEqual(filter_jobs(merged, selected_sources=set(), now=NOW)[0], [])

    def test_same_title_different_description_not_merged(self):
        b = offer(source_id='other', url='https://other.example/2', description='Different mission')
        self.assertEqual(len(deduplicate(self.records(offer(), b))), 2)

    def test_filters_and_unknown_dates(self):
        a = offer()
        b = offer(remote_id='2', url='https://jobs.example/2', title='Technicien',
                  location='Draguignan', full_time=False, contract='CDD', published_at=None)
        jobs = deduplicate(self.records(a, b))
        self.assertEqual(len(filter_jobs(jobs, location='Toulon', hours='full', contracts=['CDI'], keywords='magasinier', now=NOW)[0]), 1)
        self.assertEqual(filter_jobs(jobs, zone='near', now=NOW)[0][0]['title'], 'Magasinier')
        dated, unknown = filter_jobs(jobs, start=date(2026, 10, 7), end=date(2026, 10, 7), now=NOW)
        self.assertEqual(len(dated), 1)
        self.assertEqual(unknown, 1)

    def test_sort_by_instant_and_unknown_last(self):
        jobs = deduplicate(self.records(offer(), offer(remote_id='2', url='https://jobs.example/2',
                                                       published_at='2026-10-08T10:00:00+00:00'),
                                         offer(remote_id='3', url='https://jobs.example/3', published_at=None)))
        recent = filter_jobs(jobs, now=NOW)[0]
        self.assertEqual([j['remote_id'] for j in recent], ['2', '1', '3'])
        oldest = filter_jobs(jobs, now=NOW, sort='oldest')[0]
        self.assertEqual([j['remote_id'] for j in oldest], ['1', '2', '3'])

    def test_expiry_and_24_hour_filter(self):
        jobs = deduplicate(self.records(offer(expires_at='2026-10-08T10:00:00+00:00')))
        self.assertEqual(filter_jobs(jobs, now=NOW)[0], [])
        self.assertTrue(filter_jobs(jobs, now=NOW, include_expired=True)[0][0]['expired'])
        self.assertEqual(len(filter_jobs(jobs, now=NOW, include_expired=True, since=NOW - timedelta(hours=24))[0]), 1)
        self.assertEqual(filter_jobs(jobs, now=NOW, include_expired=True, since=NOW - timedelta(hours=23))[0], [])


if __name__ == '__main__':
    unittest.main()
