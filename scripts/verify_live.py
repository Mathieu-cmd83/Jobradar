"""Explicit real-network validation; every run uses a fresh temporary database."""
import argparse
from datetime import datetime
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamlit.testing.v1 import AppTest

from jobradar.models import UTC
from jobradar.registry import SOURCES
from jobradar.service import deduplicate, filter_jobs, refresh
from jobradar.storage import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs/live_validation.json')
    args = parser.parse_args()
    report = {'checked_at': datetime.now(UTC).isoformat(),
              'versions': {p: importlib.metadata.version(p) for p in ('streamlit', 'requests', 'feedparser')},
              'sources': [], 'success': False}
    with tempfile.TemporaryDirectory(prefix='jobradar-live-') as temporary:
        path = Path(temporary) / 'live.sqlite3'
        store = Store(path)
        refresh(SOURCES, store)
        states = store.states()
        for source in SOURCES:
            if source.enabled:
                state = states.get(source.id, {})
                report['sources'].append({'id': source.id, 'name': source.name, 'endpoint': source.url,
                                          'status': state.get('status'), 'fetched': state.get('fetched', 0),
                                          'imported': state.get('imported', 0), 'message': state.get('message', '')})
        source_ok = all(r['status'] == 'ok' and r['imported'] > 0 for r in report['sources'])
        # This AppTest uses the database just populated by real HTTPS requests, with no mocks.
        previous_path = os.environ.get('JOBRADAR_DB_PATH')
        os.environ['JOBRADAR_DB_PATH'] = str(path)
        try:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=120).run()
            report['app_exceptions'] = [e.message for e in app.exception]
            report['app_errors'] = [e.value for e in app.error]
            report['rendered_offers'] = int(app.metric[0].value) if app.metric else 0
            offers, _ = filter_jobs(deduplicate(store.jobs()))
            report['display_matches_store'] = report['rendered_offers'] == len(offers)
            report['tabs'] = [t.label for t in app.tabs]
            report['success'] = bool(source_ok and not app.exception and not app.error and offers
                                     and report['display_matches_store'] and len(app.tabs) == 3)
        finally:
            if previous_path is None:
                os.environ.pop('JOBRADAR_DB_PATH', None)
            else:
                os.environ['JOBRADAR_DB_PATH'] = previous_path
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
