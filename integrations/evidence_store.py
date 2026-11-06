"""Durable normalized-evidence inbox; no provider calls or business side effects."""
import json
import sqlite3


class EvidenceConflict(ValueError):
    """An event ID was reused for different evidence."""


class EvidenceStore:
    def __init__(self, path):
        if not isinstance(path, str) or not path.strip() or path == ':memory:':
            raise ValueError('persistent database path required')
        self.path = path
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS evidence_inbox ('
                       'sequence INTEGER PRIMARY KEY AUTOINCREMENT, '
                       'source TEXT NOT NULL, event_id TEXT NOT NULL, '
                       'event_json TEXT NOT NULL, UNIQUE(source,event_id))')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def append(self, event):
        if event.get('source') not in ('github', 'linear', 'supabase'):
            raise ValueError('unsupported source')
        if not isinstance(event.get('event_id'), str) or not event['event_id'].strip():
            raise ValueError('event_id required')
        encoded = json.dumps(event, sort_keys=True, separators=(',', ':'), allow_nan=False)
        with self._connect() as db:
            cursor = db.execute('INSERT INTO evidence_inbox(source,event_id,event_json) '
                                'VALUES(?,?,?) ON CONFLICT(source,event_id) DO NOTHING',
                                (event['source'], event['event_id'], encoded))
            duplicate = cursor.rowcount == 0
            row = db.execute('SELECT sequence,event_json FROM evidence_inbox '
                             'WHERE source=? AND event_id=?',
                             (event['source'], event['event_id'])).fetchone()
            if row[1] != encoded:
                raise EvidenceConflict('event ID already exists with different evidence')
            return {'sequence': row[0], 'duplicate': duplicate, 'event': json.loads(row[1])}

    def list_events(self, source, after_id=0, limit=50):
        if source not in ('github', 'linear', 'supabase'):
            raise ValueError('unsupported source')
        if type(after_id) is not int or after_id < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('invalid pagination')
        with self._connect() as db:
            rows = db.execute('SELECT sequence,event_json FROM evidence_inbox '
                              'WHERE source=? AND sequence>? ORDER BY sequence LIMIT ?',
                              (source, after_id, limit)).fetchall()
        return {'events': [{'sequence': row[0], 'event': json.loads(row[1])} for row in rows],
                'next_after_id': rows[-1][0] if rows else after_id}
