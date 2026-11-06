import unittest
from integrations.evidence_events import normalize_event, SOURCES

class EvidenceEventTests(unittest.TestCase):
    def event(self, **changes):
        args = dict(source='github', event_id='delivery-1', event_type='integration.observed', observed_at='2026-11-05T21:55:00-06:00', payload={'healthy': True})
        args.update(changes)
        return normalize_event(**args)

    def test_supported_sources_remain_unverified(self):
        for source in SOURCES:
            event = self.event(source=source)
            self.assertEqual(event['verification_status'], 'unverified')
            self.assertEqual(event['source'], source)

    def test_utc_conversion(self):
        self.assertEqual(self.event()['observed_at'], '2026-11-06T03:55:00+00:00')

    def test_stable_source_scoped_key(self):
        self.assertEqual(self.event()['idempotency_key'], self.event()['idempotency_key'])
        self.assertNotEqual(self.event()['idempotency_key'], self.event(source='linear')['idempotency_key'])

    def test_invalid_inputs_rejected(self):
        for change in ({'source': 'unknown'}, {'event_id': ''}, {'event_type': ' '}, {'event_id': 'x' * 257}, {'payload': []}, {'observed_at': 'invalid'}, {'observed_at': '2026-11-05T21:55:00'}, {'observed_at': None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.event(**change)

    def test_payload_top_level_copy(self):
        payload = {'healthy': True}
        event = self.event(payload=payload)
        payload['healthy'] = False
        self.assertTrue(event['payload']['healthy'])

if __name__ == '__main__':
    unittest.main()
