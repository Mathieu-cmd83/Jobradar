from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .models import UTC


class Store:
    """Local persistence. Missing from a partial feed never means withdrawn."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, source_id TEXT NOT NULL, payload TEXT NOT NULL,
                    digest TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_source ON jobs(source_id);
                CREATE TABLE IF NOT EXISTS revisions (
                    id INTEGER PRIMARY KEY, job_id TEXT NOT NULL, observed_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS revisions_job ON revisions(job_id);
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, checked_at TEXT NOT NULL,
                    status TEXT NOT NULL, message TEXT NOT NULL, fetched INTEGER NOT NULL,
                    imported INTEGER NOT NULL, new_jobs INTEGER NOT NULL, changed INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS runs_source ON runs(source_id, id);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=30000')
        try:
            with db:
                yield db
        finally:
            db.close()

    def record_success(self, source, jobs, *, fetched, now=None, partial=False, note=''):
        stamp = (now or datetime.now(UTC)).isoformat()
        new, changed = 0, 0
        with self.connection() as db:
            for job in jobs:
                payload = json.dumps(job.payload(), ensure_ascii=False, sort_keys=True)
                digest = sha256(payload.encode()).hexdigest()
                previous = db.execute('SELECT digest FROM jobs WHERE id=?', (job.key,)).fetchone()
                if previous is None:
                    new += 1
                elif previous['digest'] != digest:
                    changed += 1
                if previous is None or previous['digest'] != digest:
                    db.execute('INSERT INTO revisions(job_id, observed_at, payload) VALUES (?, ?, ?)',
                               (job.key, stamp, payload))
                db.execute('''INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)
                              ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,
                              digest=excluded.digest, last_seen=excluded.last_seen''',
                           (job.key, source.id, payload, digest, stamp, stamp))
            status = 'partial' if partial else 'ok' if jobs else 'empty'
            message = (f'{len(jobs)} offres du Var importées sur {fetched} offres reçues. '
                       'Liste éventuellement partielle ; absence ≠ retrait. ' + note)
            db.execute('''INSERT INTO runs(source_id, checked_at, status, message, fetched, imported, new_jobs, changed)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                       (source.id, stamp, status, message, fetched, len(jobs), new, changed))
        return new, changed

    def record_error(self, source_id, status, message, now=None):
        with self.connection() as db:
            db.execute('''INSERT INTO runs(source_id, checked_at, status, message, fetched, imported, new_jobs, changed)
                          VALUES (?, ?, ?, ?, 0, 0, 0, 0)''',
                       (source_id, (now or datetime.now(UTC)).isoformat(), status, message))

    def states(self):
        with self.connection() as db:
            rows = db.execute('''SELECT r.*,
                (SELECT MAX(checked_at) FROM runs good WHERE good.source_id=r.source_id
                    AND good.status IN ('ok', 'empty', 'partial')) AS last_success,
                (SELECT MAX(checked_at) FROM runs tested WHERE tested.source_id=r.source_id
                    AND tested.status IN ('ok', 'partial') AND tested.imported>0) AS last_nonempty_success
                FROM runs r WHERE r.id=(SELECT MAX(id) FROM runs s WHERE s.source_id=r.source_id)''').fetchall()
        return {row['source_id']: dict(row) for row in rows}

    def jobs(self):
        with self.connection() as db:
            rows = db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
        return [dict(json.loads(r['payload']), id=r['id'], first_seen=r['first_seen'], last_seen=r['last_seen'])
                for r in rows]

    def history(self, limit=300):
        with self.connection() as db:
            rows = db.execute('SELECT * FROM revisions ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [dict(json.loads(row['payload']), job_id=row['job_id'], observed_at=row['observed_at']) for row in rows]

    def runs(self, limit=100):
        with self.connection() as db:
            return [dict(r) for r in db.execute('SELECT * FROM runs ORDER BY id DESC LIMIT ?', (limit,))]
