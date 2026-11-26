"""Explicit, signed, fail-closed workflow dispatch gate for RHNS.

This module has NO background loop or automatic dispatch. The caller must hold
a pre-existing, independently issued approval signed by the control plane.
A reservation and an approval audit record are committed before any HTTP call.
An ambiguous network outcome is never blindly retried.
"""
import base64
import hashlib
import hmac
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import requests

from .workflow_receipts import WorkflowReceiptLedger, utcnow


APPROVAL_FIELDS = frozenset({
    "approval_id", "approved_by", "policy_version", "tenant_id",
    "dispatch_id", "request_key", "repo", "workflow", "ref",
    "issued_at", "expires_at", "intent_hash", "workflow_blob_sha",
})
# The scheduled revenue worker is deliberately not dispatchable from this
# gateway: it already runs hourly and must not be triggered in duplicate.
ALLOWED_TARGETS = frozenset({
    ("Garrettc123/defender-os", "status-report.yml", "main"),
})
CORRELATION_RE = re.compile(r"^[a-zA-Z0-9_-]{12,80}$")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def workflow_payload(claims):
    return {
        "ref": claims["ref"],
        "inputs": {"rhns_dispatch_id": claims["dispatch_id"]},
    }


def verify_approval(claims, signature, secret, now=None):  # noqa: C901
    """Verify exact action, trusted signature, authority, scope and expiry."""
    if not isinstance(claims, dict) or set(claims) != APPROVAL_FIELDS:
        raise PermissionError("Invalid approval fields")
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise PermissionError("A strong control-plane verification secret is required")
    if not isinstance(signature, str) or re.fullmatch(r"[a-f0-9]{64}", signature) is None:
        raise PermissionError("Missing approval signature")
    if not hmac.compare_digest(
        hmac.new(secret, canonical(claims), hashlib.sha256).hexdigest(), signature
    ):
        raise PermissionError("Approval signature mismatch")
    for field in ("approval_id", "approved_by", "policy_version", "tenant_id", "request_key"):
        if not isinstance(claims[field], str) or not claims[field].strip():
            raise PermissionError("Incomplete approval identity")
    if not isinstance(claims["dispatch_id"], str) or not CORRELATION_RE.fullmatch(
        claims["dispatch_id"]
    ):
        raise PermissionError("Invalid correlation identity")
    scope = (claims["repo"], claims["workflow"], claims["ref"])
    if scope not in ALLOWED_TARGETS:
        raise PermissionError("Target outside approved safe workflow scope")
    if not isinstance(claims["intent_hash"], str):
        raise PermissionError("Missing intent digest")
    if not isinstance(claims["workflow_blob_sha"], str) or not re.fullmatch(
        r"[a-f0-9]{40}", claims["workflow_blob_sha"]
    ):
        raise PermissionError("Approval must pin an exact workflow blob SHA")
    expected = hashlib.sha256(canonical(workflow_payload(claims))).hexdigest()
    if not hmac.compare_digest(expected, claims["intent_hash"]):
        raise PermissionError("Approval does not bind the exact dispatch payload")
    try:
        issued = datetime.fromisoformat(claims["issued_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(claims["expires_at"].replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError) as exc:
        raise PermissionError("Invalid approval timestamp") from exc
    if issued.tzinfo is None or expires.tzinfo is None:
        raise PermissionError("Approval timestamps must be timezone-aware")
    now = now or datetime.now(timezone.utc)
    if issued > now + timedelta(seconds=60) or expires <= now:
        raise PermissionError("Approval is not currently valid")
    if expires <= issued or expires > issued + timedelta(minutes=15):
        raise PermissionError("Approval exceeds maximum authority window")
    return True


class AuthorizedWorkflowDispatcher:
    """Approval-bound GitHub dispatch; no automatic retries or autonomous writes."""

    def __init__(self, ledger, verification_secret, enabled=False, http=None):
        if not isinstance(ledger, WorkflowReceiptLedger):
            raise TypeError("Durable WorkflowReceiptLedger required")
        self.ledger = ledger
        self.verification_secret = verification_secret
        self.enabled = enabled
        self.http = http if http is not None else requests.Session()
        with sqlite3.connect(self.ledger.path, timeout=10) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS workflow_dispatch_approvals (
                dispatch_id TEXT PRIMARY KEY,
                approval_id TEXT NOT NULL UNIQUE,
                approved_by TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                approval_digest TEXT NOT NULL,
                verified_at TEXT NOT NULL
            )""")

    def _workflow_contract_is_live(self, claims, github_token):
        # Verify the exact reviewed workflow is on the authorized branch
        # before committing any reservation or sending any dispatch.
        owner, name = claims["repo"].split("/")
        url = ("https://api.github.com/repos/" + owner + "/" + name +
               "/contents/.github/workflows/" + claims["workflow"])
        response = self.http.get(
            url,
            headers={
                "Authorization": "Bearer " + github_token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"ref": claims["ref"]},
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            return False
        if body.get("sha") != claims["workflow_blob_sha"]:
            return False
        source = base64.b64decode(body.get("content", "")).decode("utf-8")
        return all(token in source for token in (
            "run-name:", "RHNS/{0}", "rhns_dispatch_id:", "workflow_dispatch:",
        ))

    def _reserve_with_approval(self, claims):
        """Persist the idempotent reservation and signed approval before POST."""
        dispatch_id = claims["dispatch_id"]
        self.ledger.reserve(
            dispatch_id, claims["tenant_id"], claims["repo"], claims["workflow"],
            claims["ref"], claims["request_key"],
        )
        with sqlite3.connect(self.ledger.path, timeout=10) as db:
            db.execute(
                """INSERT INTO workflow_dispatch_approvals
                (dispatch_id,approval_id,approved_by,policy_version,
                 approval_digest,verified_at) VALUES(?,?,?,?,?,?)""",
                (dispatch_id, claims["approval_id"], claims["approved_by"],
                 claims["policy_version"], hashlib.sha256(canonical(claims)).hexdigest(),
                 utcnow()),
            )

    def _post_once(self, claims, github_token):
        """Only one external side effect; never retry an ambiguous outcome."""
        dispatch_id = claims["dispatch_id"]
        owner, repo = claims["repo"].split("/")
        url = ("https://api.github.com/repos/" + owner + "/" + repo +
               "/actions/workflows/" + claims["workflow"] + "/dispatches")
        try:
            response = self.http.post(
                url,
                headers={
                    "Authorization": "Bearer " + github_token,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json=workflow_payload(claims),
                timeout=10,
            )
            if response.status_code != 204:
                return {
                    "status": "unverified", "reason": "dispatch_not_confirmed",
                    "receipt_id": dispatch_id,
                }
            self.ledger.mark_accepted(dispatch_id)
            return {
                "status": "unverified", "reason": "dispatch_accepted_completion_pending",
                "receipt_id": dispatch_id,
            }
        except (requests.RequestException, sqlite3.Error, OSError):
            return {
                "status": "unverified", "reason": "dispatch_outcome_unknown",
                "receipt_id": dispatch_id,
            }

    def _preflight(self, claims, signature, github_token):
        """Validate authorization and deployed workflow before reserving."""
        if not self.enabled:
            return {"status": "denied", "reason": "execution_disabled"}
        try:
            verify_approval(claims, signature, self.verification_secret)
        except PermissionError:
            return {"status": "denied", "reason": "approval_invalid"}
        if not github_token:
            return {"status": "denied", "reason": "provider_token_missing"}
        try:
            if not self._workflow_contract_is_live(claims, github_token):
                return {"status": "denied", "reason": "approved_workflow_not_live"}
        except (requests.RequestException, ValueError, TypeError, UnicodeError, OSError):
            return {"status": "unverified", "reason": "workflow_contract_unavailable"}
        return None

    def dispatch(self, claims, signature, github_token):
        denial = self._preflight(claims, signature, github_token)
        if denial is not None:
            return denial
        try:
            self._reserve_with_approval(claims)
        except sqlite3.IntegrityError:
            return {"status": "unverified", "reason": "duplicate_or_existing_dispatch"}
        except (OSError, sqlite3.Error):
            return {"status": "unverified", "reason": "durable_reservation_failed"}
        return self._post_once(claims, github_token)
