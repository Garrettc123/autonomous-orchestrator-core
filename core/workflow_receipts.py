"""Durable, fail-closed RHNS workflow receipt ledger.

GitHub workflow_dispatch HTTP 204 proves acceptance only, never completion.
Provider run identity and terminal conclusion must be recorded separately.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class WorkflowReceiptLedger:
    """SQLite WAL ledger for independently reconciled GitHub workflow runs."""

    def __init__(self, path):
        self.path = str(Path(path))
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS workflow_receipts (
                dispatch_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                repo TEXT NOT NULL,
                workflow TEXT NOT NULL,
                ref TEXT NOT NULL,
                request_key TEXT NOT NULL,
                provider_run_id INTEGER UNIQUE,
                head_sha TEXT,
                state TEXT NOT NULL,
                conclusion TEXT,
                evidence_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(tenant_id, request_key)
            )""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def reserve(self, dispatch_id, tenant_id, repo, workflow, ref, request_key):
        """Reserve before dispatch. Reusing a key never permits a second dispatch."""
        if not all((dispatch_id, tenant_id, repo, workflow, ref, request_key)):
            raise ValueError("All receipt identity fields are required")
        now = utcnow()
        with self._connect() as db:
            db.execute("""INSERT INTO workflow_receipts
                (dispatch_id,tenant_id,repo,workflow,ref,request_key,
                 state,evidence_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,'reserved','{}',?,?)""",
                       (dispatch_id, tenant_id, repo, workflow, ref, request_key, now, now))
        return self.read(dispatch_id)

    def mark_accepted(self, dispatch_id):
        """Accepted dispatch remains nonterminal and unverified."""
        with self._connect() as db:
            cur = db.execute("""UPDATE workflow_receipts
                SET state='accepted', updated_at=?
                WHERE dispatch_id=? AND state='reserved'""", (utcnow(), dispatch_id))
            if cur.rowcount != 1:
                raise ValueError("Receipt not reserved or already transitioned")

    def bind_run(self, dispatch_id, provider_run_id, head_sha):
        """Bind a positively correlated provider run, not a guessed run."""
        if not isinstance(provider_run_id, int) or provider_run_id <= 0 or not head_sha:
            raise ValueError("Provider run ID and SHA required")
        with self._connect() as db:
            cur = db.execute(
                """UPDATE workflow_receipts
                SET provider_run_id=?, head_sha=?, state='running', updated_at=?
                WHERE dispatch_id=? AND state='accepted' AND provider_run_id IS NULL""",
                (provider_run_id, head_sha, utcnow(), dispatch_id),
            )
            if cur.rowcount != 1:
                raise ValueError("Cannot bind an unaccepted or already bound receipt")

    def reconcile(self, dispatch_id, provider_run_id, head_sha, status, conclusion, evidence):
        """Only a matched provider run with terminal conclusion may finalize."""
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("Provider evidence required")
        if status != "completed" or conclusion not in (
            "success", "failure", "cancelled", "timed_out", "action_required", "skipped"
        ):
            raise ValueError("Provider run is not terminal")
        state = "completed" if conclusion == "success" else "failed"
        with self._connect() as db:
            cur = db.execute(
                """UPDATE workflow_receipts
                SET state=?, conclusion=?, evidence_json=?, updated_at=?
                WHERE dispatch_id=? AND provider_run_id=? AND head_sha=?
                AND state='running'""",
                (
                    state, conclusion, json.dumps(evidence, sort_keys=True),
                    utcnow(), dispatch_id, provider_run_id, head_sha,
                ),
            )
            if cur.rowcount != 1:
                raise ValueError("Run identity mismatch or already finalized")
        return self.read(dispatch_id)

    def read(self, dispatch_id):
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM workflow_receipts WHERE dispatch_id=?",
                             (dispatch_id,)).fetchone()
            return dict(row) if row else None

    def unresolved(self):
        """Restart recovery: these require provider reconciliation, never blind retry."""
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("""SELECT * FROM workflow_receipts
                WHERE state IN ('reserved','accepted','running')
                ORDER BY created_at""").fetchall()
            return [dict(row) for row in rows]
