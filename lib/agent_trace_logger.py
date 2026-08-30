"""RHNS episodic memory logger. Writes every agent decision to Supabase agent_traces."""

import os
import time
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, Field

SUPABASE_URL = (
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    or os.environ.get("SUPABASE_URL")
    or "https://sqnckbvdqofoirgtwwxt.supabase.co"
)
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    or ""
)
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
AgentType = Literal["reason", "harmony", "navigation", "standards", "orchestrator", "arbiter", "custom"]
Outcome = Literal["success", "failure", "partial", "escalated"]


class AgentTrace(BaseModel):
    agent_id: str
    agent_type: AgentType
    task_type: str
    input_summary: str
    output_summary: str
    execution_path: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    outcome: Outcome
    latency_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    metadata: dict = Field(default_factory=dict)


async def log_trace(trace: AgentTrace) -> Optional[str]:
    if not SUPABASE_KEY:
        print("[AgentTrace] Missing SUPABASE_SERVICE_ROLE_KEY")
        return None
    payload = trace.model_dump()
    payload["created_at"] = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/agent_traces",
            headers=HEADERS,
            json=payload,
            timeout=5.0,
        )
        if r.status_code not in (200, 201):
            print(f"[AgentTrace] Log failed {r.status_code}: {r.text}")
            return None
        data = r.json()
        return data[0]["id"] if data else None


class TraceContext:
    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        task_type: str,
        input_summary: str = "",
        metadata: dict | None = None,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.task_type = task_type
        self.input_summary = input_summary
        self.output_summary = ""
        self.confidence_score = 0.0
        self.outcome: Outcome = "failure"
        self.execution_path: list[str] = []
        self.tokens_used: Optional[int] = None
        self.metadata = metadata or {}
        self._start = 0.0

    async def __aenter__(self):
        self._start = time.monotonic()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        latency_ms = int((time.monotonic() - self._start) * 1000)
        if exc_type is not None:
            self.outcome = "failure"
            self.output_summary = f"Exception: {exc_val}"
        await log_trace(
            AgentTrace(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                task_type=self.task_type,
                input_summary=self.input_summary,
                output_summary=self.output_summary,
                execution_path=self.execution_path,
                confidence_score=self.confidence_score,
                outcome=self.outcome,
                latency_ms=latency_ms,
                tokens_used=self.tokens_used,
                metadata=self.metadata,
            )
        )
        return False
