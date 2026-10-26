"""Trusted-process, in-memory prototype; not a production security boundary."""
import hashlib
import json
import math
import threading
import time
from dataclasses import dataclass
from uuid import uuid4


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def request_digest(proposal):
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be a dictionary")
    required = {"action_id", "tenant", "action", "target", "parameters"}
    if set(proposal) != required:
        raise ValueError("proposal fields must match the contract")
    for key in required - {"parameters"}:
        if not isinstance(proposal[key], str) or not proposal[key].strip():
            raise ValueError("identifiers must be nonempty strings")
    if not isinstance(proposal["parameters"], dict):
        raise ValueError("parameters must be an object")
    encoded = canonical(proposal)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), encoded


@dataclass(frozen=True)
class Receipt:
    action_id: str
    attempt_id: str
    request_digest: str
    outcome: str
    observed_at: float


class ActionLedger:
    """No persistence, authentication, adapter execution, or retry support."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._lock = threading.Lock()
        self._actions = {}

    def propose(self, proposal):
        digest, snapshot = request_digest(proposal)
        action_id = json.loads(snapshot)["action_id"]
        with self._lock:
            if action_id in self._actions:
                raise ValueError("action already registered")
            self._actions[action_id] = {
                "digest": digest, "snapshot": snapshot, "state": "proposed"
            }

    def authorize(self, action_id, approver, policy_revision, expires_at):
        if not isinstance(approver, str) or not approver.strip():
            raise ValueError("approver required")
        if not isinstance(policy_revision, str) or not policy_revision.strip():
            raise ValueError("policy revision required")
        if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
            raise ValueError("numeric expiry required")
        if not math.isfinite(expires_at):
            raise ValueError("finite expiry required")
        with self._lock:
            record = self._actions[action_id]
            if record["state"] != "proposed" or expires_at <= self._clock():
                raise ValueError("invalid authorization transition or expiry")
            record.update(state="authorized", approver=approver,
                          policy_revision=policy_revision, expires_at=expires_at)

    def begin(self, proposal):
        digest, snapshot = request_digest(proposal)
        action_id = json.loads(snapshot)["action_id"]
        with self._lock:
            record = self._actions[action_id]
            if record["state"] != "authorized":
                raise ValueError("authorization required; duplicate execution denied")
            if digest != record["digest"] or snapshot != record["snapshot"]:
                raise ValueError("authorization binding mismatch")
            if self._clock() >= record["expires_at"]:
                raise ValueError("authorization expired")
            attempt_id = str(uuid4())
            record.update(state="executing", attempt_id=attempt_id)
            return attempt_id

    def finish(self, action_id, attempt_id, outcome):
        if outcome not in {"completed", "failed", "uncertain"}:
            raise ValueError("explicit terminal outcome required")
        with self._lock:
            record = self._actions[action_id]
            if record["state"] != "executing" or record["attempt_id"] != attempt_id:
                raise ValueError("invalid completion or attempt")
            receipt = Receipt(action_id, attempt_id, record["digest"],
                              outcome, self._clock())
            record.update(state=outcome, receipt=receipt)
            return receipt
