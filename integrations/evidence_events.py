"""Validation boundary for normalized events; not a webhook authenticator."""
from datetime import datetime, timezone

SOURCES = frozenset({'github', 'linear', 'supabase'})

def normalize_event(source, event_id, event_type, observed_at, payload):
    if source not in SOURCES:
        raise ValueError('unsupported source')
    for value in (event_id, event_type):
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError('event id and type must be nonempty strings up to 256 characters')
    if not isinstance(payload, dict):
        raise ValueError('payload must be an object')
    if not isinstance(observed_at, str):
        raise ValueError('observed_at must be an ISO timestamp')
    try:
        timestamp = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid observed_at') from exc
    if timestamp.tzinfo is None:
        raise ValueError('observed_at requires timezone')
    return {
        'schema_version': '1.0.0',
        'source': source,
        'event_id': event_id,
        'event_type': event_type,
        'idempotency_key': f'{source}:{event_id}',
        'observed_at': timestamp.astimezone(timezone.utc).isoformat(),
        'payload': payload.copy(),
        'verification_status': 'unverified',
    }
