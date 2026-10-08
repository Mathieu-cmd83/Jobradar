from datetime import date
from dataclasses import replace
import unittest
from jobradar.connectors import parse_rss, parse_jobposting
from jobradar.models import description_text, effective_date
from jobradar.registry import SOURCES
from jobradar.service import deduplicate, filter_jobs


class DateDescriptionTests(unittest.TestCase):
    def rss(self):
        return parse_rss('''<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
        <channel><item><title>Agent</title><link>https://www.emploi-territorial.fr/offre/1</link>
        <pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate><description>Résumé</description>
        <content:encoded><![CDATA[<p>Missions</p><ul><li>Préparer les colis</li><li>Contrôler le stock</li></ul>]]></content:encoded>
        </item></channel></rss>''', SOURCES[0])[0]

    def test_rss_does_not_claim_actual_publication(self):
        job = self.rss()
        self.assertIsNone(job.published_at)
        self.assertEqual(job.rss_published_at, '2026-10-07T12:00:00+00:00')
        self.assertIn('RSS', job.date_kind)
        self.assertEqual(job.description, 'Missions\n• Préparer les colis\n• Contrôler le stock')

    def test_legacy_rss_dates_remain_truthful(self):
        row = {'source_id': 'territorial', 'published_at': '2026-10-07T12:00:00+00:00', 'date_kind': 'publication'}
        self.assertIsNone(effective_date(row, 'publication'))
        self.assertEqual(effective_date(row, 'rss'), row['published_at'])
        row['date_kind'] = 'mise à jour'
        self.assertIsNone(effective_date(row, 'rss'))
        self.assertEqual(effective_date(row), row['published_at'])

    def test_publication_filters_and_descending_rss_sort(self):
        records = []
        for job in (self.rss(), replace(self.rss(), url='https://www.emploi-territorial.fr/offre/2',
                                       remote_id='2', rss_published_at='2026-10-08T12:00:00+00:00')):
            records.append(dict(job.payload(), first_seen='2026-10-08T15:00:00+00:00', last_seen='2026-10-08T15:00:00+00:00'))
        jobs = deduplicate(records)
        result, _ = filter_jobs(jobs)
        self.assertTrue(result[0]['url'].endswith('/2'))
        result, unknown = filter_jobs(jobs, start=date(2026, 10, 7), date_basis='publication')
        self.assertEqual((result, unknown), ([], 2))
        result, _ = filter_jobs(jobs, start=date(2026, 10, 8), date_basis='rss')
        self.assertEqual(len(result), 1)

    def test_observation_never_fills_unknown_publication(self):
        self.assertIsNone(effective_date({'first_seen': '2026-10-08', 'last_seen': '2026-10-08'}))

    def test_description_safe_boundaries_and_entities(self):
        self.assertEqual(description_text('<p>A &amp; B</p><script>bad()</script><p>C</p>'), 'A & B\nC')

    def test_day_precision_retained(self):
        import json
        source = replace(SOURCES[0], kind='jsonld')
        data = {'@type': 'JobPosting', 'title': 'Agent', 'url': '/offre/1', 'datePosted': '2026-10-07'}
        job = parse_jobposting('<script type="application/ld+json">' + json.dumps(data) + '</script>', source, source.url)[0]
        self.assertEqual(job.publication_precision, 'day')
