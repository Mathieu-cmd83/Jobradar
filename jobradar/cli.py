import argparse
from datetime import datetime
import json
import os
from pathlib import Path

from .audit import audit_agencies
from .models import UTC
from .registry import SOURCES
from .service import refresh
from .storage import Store


def main():
    parser = argparse.ArgumentParser(description='Collecte et diagnostic publics JobRadar')
    parser.add_argument('command', choices=('audit', 'sync', 'status'))
    parser.add_argument('--db', default=os.environ.get('JOBRADAR_DB_PATH', '.data/jobradar.sqlite3'))
    parser.add_argument('--output', default='docs/agency_audit.json')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if args.command == 'audit':
        rows = audit_agencies(SOURCES)
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'checked_at': datetime.now(UTC).isoformat(), 'agencies': rows},
                                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for row in rows:
            print(f"{row['name']}: {row['status']} — {row['message']}")
        print(f'Audit enregistré : {path} ; {len(rows)} agences ; aucune activation automatique.')
        return 0 if all(r['status'] == 'review_pending' for r in rows) else 2
    store = Store(args.db)
    if args.command == 'sync':
        refresh(SOURCES, store, force=args.force)
    states = store.states()
    for source in SOURCES:
        state = states.get(source.id)
        print(f"{source.name}: {state['status'] if state else 'non_connectée'}"
              + (f" — {state['message']}" if state else ''))
    if args.command == 'sync':
        required = [s for s in SOURCES if s.enabled]
        return 0 if required and all(states.get(s.id, {}).get('status') in ('ok', 'empty') for s in required) else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
