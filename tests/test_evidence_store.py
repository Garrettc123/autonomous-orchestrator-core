"""Local storage tests; no live integration or credential use."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from integrations.evidence_store import EvidenceConflict, EvidenceStore


class EvidenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / 'evidence.sqlite3')
        self.store = EvidenceStore(self.path)
        self.event = {'source': 'github', 'event_id': 'test-1',
                      'verification_status': 'unverified', 'payload': {'healthy': True}}

    def test_restart_and_duplicate(self):
        first = self.store.append(self.event)
        second = EvidenceStore(self.path).append(self.event)
        self.assertFalse(first['duplicate'])
        self.assertTrue(second['duplicate'])
        self.assertEqual(first['sequence'], second['sequence'])
        self.assertEqual(len(self.store.list_events('github')['events']), 1)

    def test_conflict_preserves_original(self):
        self.store.append(self.event)
        with self.assertRaises(EvidenceConflict):
            self.store.append(dict(self.event, payload={'healthy': False}))
        self.assertEqual(self.store.list_events('github')['events'][0]['event'], self.event)

    def test_sources_are_isolated(self):
        for source in ('github', 'linear', 'supabase'):
            self.store.append(dict(self.event, source=source))
        for source in ('github', 'linear', 'supabase'):
            events = self.store.list_events(source)['events']
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['event']['source'], source)

    def test_pagination(self):
        for index in range(3):
            self.store.append(dict(self.event, event_id=str(index)))
        first = self.store.list_events('github', limit=2)
        second = self.store.list_events('github', after_id=first['next_after_id'])
        self.assertEqual(len(first['events']), 2)
        self.assertEqual(len(second['events']), 1)

    def test_invalid_configuration_and_pagination(self):
        for path in ('', ':memory:', None):
            with self.assertRaises(ValueError):
                EvidenceStore(path)
        for arguments in ({'limit': 0}, {'limit': 101}, {'after_id': -1}, {'limit': True}):
            with self.assertRaises(ValueError):
                self.store.list_events('github', **arguments)
        with self.assertRaises(ValueError):
            self.store.list_events('unknown')

    def test_invalid_evidence(self):
        for changes in ({'source': 'unknown'}, {'event_id': ''}, {'payload': float('nan')}):
            with self.assertRaises(ValueError):
                self.store.append(dict(self.event, **changes))

    def test_concurrent_duplicates(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.store.append(self.event), range(24)))
        self.assertEqual(sum(not item['duplicate'] for item in results), 1)
        self.assertEqual(len(self.store.list_events('github')['events']), 1)
