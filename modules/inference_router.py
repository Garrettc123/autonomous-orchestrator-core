"""
RHNS Two-Tier Inference Router
================================
Routes inference requests to the optimal model tier:

TIER 1 — LOCAL (Qwen2.5:0.5b via Ollama)
  Fast path: classification, heartbeats, low-stakes signals
  Latency: < 200ms warm / ~800ms cold
  Cost: $0 (on-device)
  Use when: urgency=low|medium, value_usd < $100, signal_type in [heartbeat, monitoring]

TIER 2 — CLOUD (OpenAI o3 / GPT-4o via API)
  Deep path: Reason-layer decisions involving money, security, deployment
  Latency: 2-30s depending on thinking budget
  Cost: ~$0.002-$0.06 per call
  Use when: urgency=immediate|high, value_usd >= $100, or signal_type in [payment_failed, churn_risk]

The router also supports a TIER 0 — SYMBOLIC:
  Zero-latency path: Pure Python constraint evaluation
  Use when: no language model needed (e.g., simple threshold checks)

Based on research: AlphaProof test-time compute, o3 "thinking budget" architecture,
and LOOP iterative LLM-planner feedback.
"""

import os
import time
import requests
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class InferenceTier(Enum):
    SYMBOLIC = 0   # Pure Python, zero latency
    LOCAL = 1      # Qwen2.5 on-device via Ollama
    CLOUD = 2      # o3 / GPT-4o via OpenAI API


@dataclass
class InferenceRequest:
    prompt: str
    signal_type: str
    urgency: str
    value_usd: float
    max_tokens: int = 512
    thinking_budget: str = "low"   # low | medium | high — maps to o3 reasoning effort
    system_prompt: str = ""
    metadata: dict = None


@dataclass
class InferenceResponse:
    text: str
    tier_used: InferenceTier
    model: str
    latency_ms: float
    tokens_used: int
    cost_estimate_usd: float
    error: Optional[str] = None


class InferenceRouter:
    """
    Routes RHNS inference requests to the optimal model tier.

    Decision logic:
    1. If the signal requires no language model → SYMBOLIC (immediate)
    2. If urgency is immediate/high AND value > $100 → CLOUD (o3/GPT-4o)
    3. If urgency is immediate/high BUT value < $100 → CLOUD with low thinking budget
    4. If urgency is medium/low → LOCAL (Qwen2.5)
    5. If LOCAL is unavailable → fall back to CLOUD
    6. If CLOUD is unavailable (no API key) → fall back to LOCAL or log + skip
    """

    # Signal types that always route to CLOUD regardless of urgency
    CLOUD_FORCED_SIGNALS = {
        "payment_failed",
        "churn_risk",
        "security_breach",
        "deploy_failure",
        "revenue_anomaly",
    }

    # Signal types that always route to SYMBOLIC (no LLM needed)
    SYMBOLIC_SIGNALS = {
        "heartbeat",
        "health_check",
        "metric_sample",
    }

    def __init__(
        self,
        ollama_base_url: str = None,
        ollama_model: str = "qwen2.5:0.5b",
        openai_api_key: str = None,
        cloud_model: str = "gpt-4o-mini",  # default to cost-efficient; override with o3
        cloud_model_high_stakes: str = "o3",
        high_stakes_threshold_usd: float = 100.0,
    ):
        self.ollama_url = ollama_base_url or os.getenv(
            "RHNS_PIXEL_ENDPOINT", "http://localhost:11434"
        )
        self.ollama_model = ollama_model
        self.openai_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.cloud_model = cloud_model
        self.cloud_model_high = cloud_model_high_stakes
        self.threshold_usd = high_stakes_threshold_usd

        self._tier1_available: Optional[bool] = None  # cached health check
        self._tier2_available: Optional[bool] = None

    def _thinking_effort(self, urgency: str, value_usd: float) -> str:
        """Map urgency + value to o3 reasoning effort level."""
        if urgency == "immediate" and value_usd >= self.threshold_usd:
            return "high"
        elif urgency in ("immediate", "high"):
            return "medium"
        else:
            return "low"

    def _select_tier(self, request: InferenceRequest) -> InferenceTier:
        """Determine which inference tier to use."""
        if request.signal_type in self.SYMBOLIC_SIGNALS:
            return InferenceTier.SYMBOLIC

        if request.signal_type in self.CLOUD_FORCED_SIGNALS:
            return InferenceTier.CLOUD

        if request.urgency in ("immediate", "high"):
            return InferenceTier.CLOUD

        return InferenceTier.LOCAL

    def _probe_local(self) -> bool:
        """Check if local Ollama endpoint is reachable."""
        if self._tier1_available is not None:
            return self._tier1_available
        try:
            resp = requests.get(
                f"{self.ollama_url}/api/tags",
                timeout=3
            )
            self._tier1_available = resp.status_code == 200
        except Exception:
            self._tier1_available = False
        return self._tier1_available

    def _call_local(self, request: InferenceRequest) -> InferenceResponse:
        """Call Qwen2.5 via Ollama."""
        start = time.time()

        if not self._probe_local():
            return InferenceResponse(
                text="",
                tier_used=InferenceTier.LOCAL,
                model=self.ollama_model,
                latency_ms=0,
                tokens_used=0,
                cost_estimate_usd=0.0,
                error="Local Ollama endpoint unavailable",
            )

        payload = {
            "model": self.ollama_model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "num_predict": request.max_tokens,
                "temperature": 0.3,
                "top_p": 0.9,
            }
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            elapsed = (time.time() - start) * 1000
            return InferenceResponse(
                text=data.get("response", ""),
                tier_used=InferenceTier.LOCAL,
                model=self.ollama_model,
                latency_ms=elapsed,
                tokens_used=data.get("eval_count", 0),
                cost_estimate_usd=0.0,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return InferenceResponse(
                text="",
                tier_used=InferenceTier.LOCAL,
                model=self.ollama_model,
                latency_ms=elapsed,
                tokens_used=0,
                cost_estimate_usd=0.0,
                error=str(e),
            )

    def _call_cloud(self, request: InferenceRequest) -> InferenceResponse:
        """Call o3 or GPT-4o via OpenAI API with thinking budget."""
        start = time.time()

        if not self.openai_key:
            return InferenceResponse(
                text="",
                tier_used=InferenceTier.CLOUD,
                model="none",
                latency_ms=0,
                tokens_used=0,
                cost_estimate_usd=0.0,
                error="OPENAI_API_KEY not configured",
            )

        effort = self._thinking_effort(request.urgency, request.value_usd)

        # Use o3 for high-stakes, gpt-4o-mini for everything else
        model = (
            self.cloud_model_high
            if request.value_usd >= self.threshold_usd and request.urgency == "immediate"
            else self.cloud_model
        )

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": request.max_tokens,
        }

        # o3 supports reasoning_effort parameter
        if model in ("o3", "o3-mini", "o1"):
            payload["reasoning_effort"] = effort

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            elapsed = (time.time() - start) * 1000

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)

            # Rough cost estimate
            cost_per_1k = 0.002 if "mini" in model else 0.015
            cost = (total_tokens / 1000) * cost_per_1k

            return InferenceResponse(
                text=content,
                tier_used=InferenceTier.CLOUD,
                model=model,
                latency_ms=elapsed,
                tokens_used=total_tokens,
                cost_estimate_usd=cost,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return InferenceResponse(
                text="",
                tier_used=InferenceTier.CLOUD,
                model=model,
                latency_ms=elapsed,
                tokens_used=0,
                cost_estimate_usd=0.0,
                error=str(e),
            )

    def _call_symbolic(self, request: InferenceRequest) -> InferenceResponse:
        """Handle purely symbolic signals without any LLM call."""
        start = time.time()
        result = f"SYMBOLIC_PASS: signal_type={request.signal_type} requires no language model. Route to MONITOR."
        elapsed = (time.time() - start) * 1000
        return InferenceResponse(
            text=result,
            tier_used=InferenceTier.SYMBOLIC,
            model="symbolic",
            latency_ms=elapsed,
            tokens_used=0,
            cost_estimate_usd=0.0,
        )

    def route(self, request: InferenceRequest) -> InferenceResponse:
        """
        Route the inference request to the optimal tier.
        Falls back gracefully if a tier is unavailable.
        """
        tier = self._select_tier(request)

        if tier == InferenceTier.SYMBOLIC:
            return self._call_symbolic(request)

        if tier == InferenceTier.LOCAL:
            resp = self._call_local(request)
            if resp.error:
                # Fall back to cloud
                resp = self._call_cloud(request)
            return resp

        # CLOUD tier
        resp = self._call_cloud(request)
        if resp.error and "API_KEY" not in (resp.error or ""):
            # Non-key error — try local as fallback
            fallback = self._call_local(request)
            if not fallback.error:
                return fallback
        return resp

    def tier_stats(self) -> dict:
        """Return routing tier availability summary."""
        return {
            "local_available": self._probe_local(),
            "cloud_available": bool(self.openai_key),
            "cloud_model_standard": self.cloud_model,
            "cloud_model_high_stakes": self.cloud_model_high,
            "local_model": self.ollama_model,
            "high_stakes_threshold_usd": self.threshold_usd,
        }
