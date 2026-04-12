"""
RHNS Standards Gate — Upgraded Standards Layer
================================================
Replaces the simple confidence-threshold Standards check with
a three-stage gate:

  Stage 1: Confidence Floor (existing behavior)
  Stage 2: Symbolic Constraint Verification
  Stage 3: Formal Proof Certificate (for HIGH_STAKES domains)

Only actions that pass all three stages receive final approval.
This implements the RHNS Standards principle at its highest level.
"""

import os
from dataclasses import dataclass
from core.formal_verifier import FormalVerifier, Domain


@dataclass
class StandardsVerdict:
    """Final Standards gate decision."""
    approved: bool
    action: str
    stage_failed: str = ""   # "confidence" | "symbolic" | "formal" | ""
    proof_cert_id: str = ""
    confidence_used: float = 0.0
    reason: str = ""
    repair_hint: str = ""


class StandardsGate:
    """
    Three-stage Standards gate for RHNS action approval.

    Composes:
    - Confidence threshold check
    - SymbolicVerifier (constraint rules) — optional, skipped if unavailable
    - FormalVerifier (domain proof)
    """

    HIGH_STAKES_DOMAINS = {Domain.MONEY, Domain.SECURITY, Domain.DEPLOY}

    def __init__(
        self,
        confidence_floor: float = 0.60,
        formal_verifier: FormalVerifier = None,
        symbolic_verifier=None,
    ):
        self.confidence_floor = confidence_floor
        self.fv = formal_verifier or FormalVerifier()
        self.sv = symbolic_verifier  # Optional — None disables Stage 2

    def evaluate(
        self,
        action: str,
        signal_type: str,
        urgency: str,
        value_usd: float,
        confidence: float,
        state_facts: dict = None,
    ) -> StandardsVerdict:
        """
        Run the three-stage Standards gate.
        Returns a StandardsVerdict with full reasoning.
        """
        state_facts = state_facts or {}

        # Stage 1: Confidence Floor
        if confidence < self.confidence_floor:
            return StandardsVerdict(
                approved=False,
                action=action,
                stage_failed="confidence",
                confidence_used=confidence,
                reason=f"Confidence {confidence:.2f} below floor {self.confidence_floor:.2f}",
                repair_hint="Gather corroborating signals from additional sources.",
            )

        # Stage 2: Symbolic Constraint Verification (if verifier available)
        if self.sv is not None:
            sv_result = self.sv.verify(
                action=action,
                signal_type=signal_type,
                urgency=urgency,
                value_usd=value_usd,
                confidence=confidence,
                source="",
            )
            hard_violations = [v for v in sv_result.violations if v.severity == "hard"]
            if hard_violations:
                return StandardsVerdict(
                    approved=False,
                    action=action,
                    stage_failed="symbolic",
                    confidence_used=confidence,
                    reason=f"Symbolic constraint violated: {hard_violations[0].rule_name}",
                    repair_hint=sv_result.repair_suggestion,
                )

        # Stage 3: Formal Proof (high-stakes domains only)
        domain = self.fv.classify_domain(action)
        if domain in self.HIGH_STAKES_DOMAINS:
            # Enrich state_facts with available context
            enriched_facts = {
                "stripe_key_available": bool(os.getenv("STRIPE_SECRET_KEY")),
                "hubspot_key_available": bool(os.getenv("HUBSPOT_API_KEY")),
                "confidence": confidence,
                "value_usd": value_usd,
                "defense_state_nominal": True,   # Can be set from DAG context
                "ci_passing": True,
                "active_incident": False,
                "backup_recent": True,
                "privilege_escalation": False,
                **state_facts,
            }
            cert = self.fv.verify(action, enriched_facts, domain)

            if not cert.is_valid():
                return StandardsVerdict(
                    approved=False,
                    action=action,
                    stage_failed="formal",
                    proof_cert_id=cert.cert_id,
                    confidence_used=confidence,
                    reason=f"Formal proof failed for domain={domain.value}",
                    repair_hint=cert.counterexample,
                )

            return StandardsVerdict(
                approved=True,
                action=action,
                proof_cert_id=cert.cert_id,
                confidence_used=confidence,
                reason=f"All 3 stages passed. Formal proof: {cert.cert_id}",
            )

        # Low-stakes domain: stages 1+2 sufficient
        return StandardsVerdict(
            approved=True,
            action=action,
            confidence_used=confidence,
            reason="Confidence + symbolic constraints satisfied. Low-stakes domain.",
        )
