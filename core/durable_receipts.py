"""Durable, fail-closed RHNS workflow evidence registry.

A dispatch acknowledgement is not completion. Only provider-fetched terminal
evidence matching the registered run, repository, SHA and workflow can complete
a job. Caller must obtain observations from an authenticated provider API.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


TERMINAL = {"success", "failure", "cancelled", "timed_out", "action_required"}


class ReceiptConflict(ValueError):
    """Receipt identity mismatch or unsafe transition."""


class DurableReceiptRegistry:
    def __init__(self, path):
        self.path = str(Path(path))
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS dispatch_receipts (
                    dispatch_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    commit_sha TEXT NOT NULL,
                    run_id INTEGER UNIQUE,
                    state TEXT NOT NULL CHECK(state IN
                        ('pending','running','success','failed','unverified')),
                    evidence TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def register(self, dispatch_id, tenant_id, repository, workflow, commit_sha):
        fields = (dispatch_id, tenant_id, repository, workflow, commit_sha)
        if not all(isinstance(v, str) and v.strip() for v in fields):
            raise ValueError("Dispatch identity fields must be nonempty strings")
        with self._connect() as db:
            existing = db.execute(
                "SELECT tenant_id, repository, workflow, commit_sha FROM dispatch_receipts "
                "WHERE dispatch_id=?", (dispatch_id,)
            ).fetchone()
            if existing:
                if existing != fields[1:]:
                    raise ReceiptConflict("Dispatch ID reused for different intent")
                return False
            db.execute(
                "INSERT INTO dispatch_receipts "
                "(dispatch_id,tenant_id,repository,workflow,commit_sha,state,updated_at) "
                "VALUES (?,?,?,?,?,'pending',?)", (*fields, self._now())
            )
            return True

    def bind_run(self, dispatch_id, run_id):
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
            raise ValueError("Provider run ID must be a positive integer")
        with self._connect() as db:
            row = db.execute(
                "SELECT run_id,state FROM dispatch_receipts WHERE dispatch_id=?",
                (dispatch_id,)
            ).fetchone()
            if row is None:
                raise ReceiptConflict("Unknown dispatch")
            previous, state = row
            if previous is not None and previous != run_id:
                raise ReceiptConflict("Dispatch already bound to a different run")
            if state in ("success", "failed"):
                raise ReceiptConflict("Terminal dispatch cannot be rebound")
            db.execute(
                "UPDATE dispatch_receipts SET run_id=?,state='running',updated_at=? "
                "WHERE dispatch_id=?", (run_id, self._now(), dispatch_id)
            )

    def observe(self, dispatch_id, *, tenant_id, repository, workflow,
                commit_sha, run_id, provider_status, conclusion):
        """Consume an independently retrieved provider observation.

        Never pass agent-generated claims as provider evidence. A completed
        workflow with non-success conclusion is a failure, not a success.
        """
        with self._connect() as db:
            row = db.execute(
                "SELECT tenant_id,repository,workflow,commit_sha,run_id,state "
                "FROM dispatch_receipts WHERE dispatch_id=?", (dispatch_id,)
            ).fetchone()
            if row is None or row[:5] != (
                tenant_id, repository, workflow, commit_sha, run_id
            ):
                raise ReceiptConflict("Provider evidence does not match dispatch identity")
            if row[5] in ("success", "failed"):
                raise ReceiptConflict("Terminal outcome is immutable")
            if provider_status != "completed":
                state = "unverified"
            elif conclusion == "success":
                state = "success"
            elif conclusion in TERMINAL:
                state = "failed"
            else:
                state = "unverified"
            evidence = json.dumps({
                "run_id": run_id, "provider_status": provider_status,
                "conclusion": conclusion, "repository": repository,
                "workflow": workflow, "commit_sha": commit_sha
            }, sort_keys=True)
            db.execute(
                "UPDATE dispatch_receipts SET state=?,evidence=?,updated_at=? "
                "WHERE dispatch_id=?", (state, evidence, self._now(), dispatch_id)
            )
            return state

    def status(self, dispatch_id):
        with self._connect() as db:
            row = db.execute(
                "SELECT state,run_id,evidence FROM dispatch_receipts "
                "WHERE dispatch_id=?", (dispatch_id,)
            ).fetchone()
            if row is None:
                raise ReceiptConflict("Unknown dispatch")
            return {"state": row[0], "run_id": row[1],
                    "evidence": json.loads(row[2]) if row[2] else None}
