from datetime import datetime, timedelta
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from jobradar.models import UTC
from jobradar.network import SourceError
from jobradar.storage import Store
from jobradar.registry import SOURCES

APP = Path(__file__).resolve().parents[1] / 'app.py'


def sample_feed():
    now = datetime.now(UTC)
    xml = '<rss version="2.0"><channel><title>Test only</title>'
    for identifier, title, city, contract, work_time, day in [
        ('1', 'Magasinier', 'Toulon', 'CDI', 'Temps plein', now),
        ('2', 'Agent technique', 'La Garde', 'Emploi permanent', 'Temps partiel', now - timedelta(days=1)),
        ('3', 'Chauffeur', 'Draguignan', '', '', now - timedelta(days=2)),
    ]:
        xml += (f'<item><title>{title}</title><link>https://www.emploi-territorial.fr/offre/{identifier}</link>'
                f'<pubDate>{day.strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate>'
                f'<description><![CDATA[<div class="lieutravail">Lieu de travail : {city}</div>'
                f'<div class="employeur">Employeur : Test {identifier}</div>{contract} {work_time}]]></description></item>')
    return (xml + '</channel></rss>').encode()


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / 'jobradar.sqlite3')
        self.env = patch.dict(os.environ, {'JOBRADAR_DB_PATH': self.db})
        self.env.start()
        self.addCleanup(self.env.stop)
        # UI isolation: only the RSS is active in these fixtures. Live checks cover the production registry.
        self.registry = patch('jobradar.registry.SOURCES', [replace(s, enabled=False) if s.id == 'triangle' else s for s in SOURCES])
        self.registry.start()
        self.addCleanup(self.registry.stop)
        self.client = patch('jobradar.connectors.PublicClient')
        self.mock_client = self.client.start()
        self.addCleanup(self.client.stop)
        self.mock_client.return_value.get.return_value = (sample_feed(), 'https://www.emploi-territorial.fr/rss?search-dept=083')

    def select(self, at, label):
        return next(x for x in at.selectbox if x.label == label)

    def healthy(self, at):
        self.assertFalse(at.exception, [e.message for e in at.exception])
        self.assertFalse(at.error, [e.value for e in at.error])

    def test_rendering_filters_provenance_and_no_fake_agency(self):
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        self.healthy(at)
        self.assertEqual([s.value for s in at.subheader], ['Magasinier', 'Agent technique', 'Chauffeur'])
        self.assertEqual(at.metric[0].value, '3')
        self.assertIn('0/23', at.info[0].value)
        source_table = at.dataframe[0].value
        self.assertEqual(len(source_table), 24)
        self.assertEqual(len(source_table[source_table['Collecte activée'] == 'Oui']), 1)
        self.select(at, 'Temps de travail').set_value('Temps partiel uniquement').run()
        self.healthy(at)
        self.assertEqual([s.value for s in at.subheader], ['Agent technique'])
        self.select(at, 'Temps de travail').set_value('Indifférent').run()
        at.multiselect[0].set_value(['CDI']).run()
        self.healthy(at)
        self.assertEqual([s.value for s in at.subheader], ['Magasinier'])
        at.multiselect[0].set_value([]).run()
        self.select(at, 'Zone').set_value('Autour de Toulon (indicatif)').run()
        self.assertEqual(at.metric[0].value, '2')
        at.multiselect[1].set_value([]).run()
        self.healthy(at)
        self.assertEqual(at.metric[0].value, '0')

    def test_source_failure_is_visible_and_history_remains(self):
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        self.healthy(at)
        store = Store(self.db)
        store.record_error('territorial', 'network_error', 'Test: source indisponible', datetime.now(UTC))
        at.run()
        self.healthy(at)
        self.assertEqual(at.metric[0].value, '3')
        self.assertTrue(any('source indisponible' in w.value for w in at.warning))
        self.assertEqual(len(store.history()), 3)

    def test_initial_outage_displays_zero_and_diagnostic(self):
        self.mock_client.return_value.get.side_effect = SourceError('network_error', 'Test: source indisponible')
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        self.healthy(at)
        self.assertEqual(at.metric[0].value, '0')
        self.assertTrue(any('source indisponible' in w.value for w in at.warning))

    def test_invalid_date_range_visible(self):
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        self.select(at, 'Date de parution').set_value('Période personnalisée').run()
        at.date_input[0].set_value(datetime.now(UTC).date()).run()
        at.date_input[1].set_value(datetime.now(UTC).date() - timedelta(days=1)).run()
        self.assertFalse(at.exception)
        self.assertIn('début', at.error[0].value)


if __name__ == '__main__':
    unittest.main()
