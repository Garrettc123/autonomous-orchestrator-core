"""Safety tests for authorized RHNS workflow dispatch. No network calls."""
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import requests

from core.approved_workflow_dispatch import (
    AuthorizedWorkflowDispatcher, canonical, workflow_payload,
)
from core.workflow_receipts import WorkflowReceiptLedger


SECRET = b"verified-approval-signing-key-for-tests-only"
BLOB = "a" * 40
SOURCE = (
    "name: Defender Status\n"
    "run-name: RHNS/{0}\n"
    "on:\n  workflow_dispatch:\n    inputs:\n"
    "      rhns_dispatch_id:\n        type: string\n"
)


class Reply:
    def __init__(self, code=204, data=None):
        self.status_code = code
        self.data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("Provider unavailable")

    def json(self):
        return self.data


class HTTP:
    def __init__(self, code=204, source=SOURCE, blob=BLOB, timeout=False):
        self.posts = []
        self.gets = []
        self.code = code
        self.source = source
        self.blob = blob
        self.timeout = timeout

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return Reply(200, {
            "sha": self.blob,
            "content": base64.b64encode(self.source.encode()).decode(),
        })

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if self.timeout:
            raise requests.Timeout("Unknown provider outcome")
        return Reply(self.code)


def approval(now=None, **overrides):
    now = now or datetime.now(timezone.utc)
    claims = {
        "approval_id": "one-authority-record",
        "approved_by": "garcar-private-control-os",
        "policy_version": "rhns-v1",
        "tenant_id": "tenant-a",
        "dispatch_id": "approvedrun12345",
        "request_key": "tenant-a:defender:one",
        "repo": "Garrettc123/defender-os",
        "workflow": "status-report.yml",
        "ref": "main",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "workflow_blob_sha": BLOB,
        "intent_hash": "",
    }
    claims.update(overrides)
    claims["intent_hash"] = hashlib.sha256(canonical(workflow_payload(claims))).hexdigest()
    return claims


def signature(claims):
    return hmac.new(SECRET, canonical(claims), hashlib.sha256).hexdigest()


def gateway(tmp_path, http=None, enabled=True):
    ledger = WorkflowReceiptLedger(tmp_path / "approved-receipts.sqlite")
    http = http or HTTP()
    return AuthorizedWorkflowDispatcher(ledger, SECRET, enabled=enabled, http=http), http


def test_disabled_gate_never_reads_or_dispatches(tmp_path):
    system, http = gateway(tmp_path, enabled=False)
    claims = approval()
    assert system.dispatch(claims, signature(claims), "provider-token")["status"] == "denied"
    assert not http.gets and not http.posts
    assert system.ledger.unresolved() == []


def test_invalid_signature_and_expired_approval_do_not_dispatch(tmp_path):
    system, http = gateway(tmp_path)
    claims = approval()
    assert system.dispatch(claims, "0" * 64, "provider-token")["status"] == "denied"
    expired = approval(expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    assert system.dispatch(expired, signature(expired), "provider-token")["status"] == "denied"
    assert not http.gets and not http.posts


def test_unauthorized_workflow_rejected(tmp_path):
    system, http = gateway(tmp_path)
    claims = approval(repo="Garrettc123/revenue-intelligence-engine",
                      workflow="revenue-intelligence.yml")
    result = system.dispatch(claims, signature(claims), "provider-token")
    assert result["status"] == "denied"
    assert not http.posts


def test_approved_dispatch_stays_unverified_and_is_idempotent(tmp_path):
    system, http = gateway(tmp_path)
    claims = approval()
    first = system.dispatch(claims, signature(claims), "provider-token")
    assert first["status"] == "unverified"
    assert first["reason"] == "dispatch_accepted_completion_pending"
    assert system.ledger.read(claims["dispatch_id"])["state"] == "accepted"
    assert len(http.posts) == 1
    assert http.posts[0][1]["json"] == workflow_payload(claims)
    again = system.dispatch(claims, signature(claims), "provider-token")
    assert again["reason"] == "duplicate_or_existing_dispatch"
    assert len(http.posts) == 1


def test_workflow_change_prevents_dispatch(tmp_path):
    system, http = gateway(tmp_path, HTTP(blob="b" * 40))
    claims = approval()
    result = system.dispatch(claims, signature(claims), "provider-token")
    assert result["status"] == "denied"
    assert not http.posts
    assert system.ledger.read(claims["dispatch_id"]) is None


def test_uninstrumented_workflow_prevents_dispatch(tmp_path):
    system, http = gateway(tmp_path, HTTP(source="on: workflow_dispatch"))
    claims = approval()
    result = system.dispatch(claims, signature(claims), "provider-token")
    assert result["status"] == "denied"
    assert not http.posts


def test_network_timeout_is_held_without_replay(tmp_path):
    system, http = gateway(tmp_path, HTTP(timeout=True))
    claims = approval()
    first = system.dispatch(claims, signature(claims), "provider-token")
    assert first["reason"] == "dispatch_outcome_unknown"
    assert system.ledger.read(claims["dispatch_id"])["state"] == "reserved"
    second = system.dispatch(claims, signature(claims), "provider-token")
    assert second["reason"] == "duplicate_or_existing_dispatch"
    assert len(http.posts) == 1


def test_same_approval_cannot_authorize_two_dispatches(tmp_path):
    system, http = gateway(tmp_path)
    claims = approval()
    system.dispatch(claims, signature(claims), "provider-token")
    different = approval(dispatch_id="approvedrun67890", request_key="tenant-a:defender:two")
    result = system.dispatch(different, signature(different), "provider-token")
    assert result["reason"] == "duplicate_or_existing_dispatch"
    assert len(http.posts) == 1


def test_http_failure_never_fakes_completion(tmp_path):
    system, http = gateway(tmp_path, HTTP(code=503))
    claims = approval()
    result = system.dispatch(claims, signature(claims), "provider-token")
    assert result["status"] == "unverified"
    assert result["reason"] == "dispatch_not_confirmed"
    assert system.ledger.read(claims["dispatch_id"])["state"] == "reserved"
