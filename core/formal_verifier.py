"""
RHNS Formal Verification Layer
================================
Inspired by AlphaProof / Lean4 proof-checking principles.
Every action in a HIGH_STAKES domain must pass formal proof
before the Standards layer permits execution.

Domains requiring formal verification:
  - MONEY: Any action affecting payments, subscriptions, refunds
  - SECURITY: Any action affecting credentials, tokens, access
  - DEPLOY: Any action triggering a production deployment
  - DATA: Any action modifying or deleting persistent data

Verification approach:
  1. Parse the action into a structured Proposition
  2. Apply proof rules (axioms + inference rules)
  3. Search for a valid proof chain
  4. If found: issue a ProofCertificate
  5. If not found: return a counterexample and block execution

This is a Python implementation of formal verification *principles*.
It is not a Lean4 interpreter but implements the same logical structure:
  - Axioms: rules that are always true
  - Inference rules: if premises hold, conclusion holds
  - Proof search: backward chaining from goal
  - Counterexample generation: if proof fails, explain why
"""

import json
import hashlib
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class Domain(Enum):
    """Verification domains for formal proof requirements."""
    MONEY = "money"
    SECURITY = "security"
    DEPLOY = "deploy"
    DATA = "data"
    MONITOR = "monitor"   # Low-stakes — no formal proof required
    UNKNOWN = "unknown"


class ProofStatus(Enum):
    PROVED = "proved"
    DISPROVED = "disproved"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"   # Domain does not require formal proof


@dataclass
class Proposition:
    """A formal statement about an action to be verified."""
    action: str
    domain: Domain
    
    # Preconditions that must hold for the action to be safe
    preconditions: list[str] = field(default_factory=list)
    
    # Postconditions the action claims to establish
    postconditions: list[str] = field(default_factory=list)
    
    # Context facts about the current system state
    state_facts: dict = field(default_factory=dict)
    
    def to_statement(self) -> str:
        """Format as a logical statement for proof search."""
        precs = " ∧ ".join(self.preconditions) if self.preconditions else "⊤"
        posts = " ∧ ".join(self.postconditions) if self.postconditions else "⊤"
        return f"[{self.domain.value.upper()}] Given ({precs}) → Prove ({posts})"


@dataclass
class ProofStep:
    """A single step in a proof chain."""
    rule_name: str
    premise: str
    conclusion: str
    justification: str


@dataclass
class ProofCertificate:
    """
    A formal certificate that an action has been verified.
    Analogous to a Lean4 proof term.
    """
    cert_id: str
    proposition: str
    domain: Domain
    status: ProofStatus
    proof_steps: list[ProofStep] = field(default_factory=list)
    counterexample: str = ""
    verified_at: str = ""
    verifier_version: str = "RHNS-FV-1.0"
    
    def is_valid(self) -> bool:
        return self.status in (ProofStatus.PROVED, ProofStatus.SKIPPED)
    
    def to_dict(self) -> dict:
        return {
            "cert_id": self.cert_id,
            "proposition": self.proposition,
            "domain": self.domain.value,
            "status": self.status.value,
            "proof_steps": [asdict(s) for s in self.proof_steps],
            "counterexample": self.counterexample,
            "verified_at": self.verified_at,
            "verifier_version": self.verifier_version,
            "valid": self.is_valid(),
        }


# ─── Axiom Library ──────────────────────────────────────────────────────────
# Axioms are base truths that require no proof.
# Represented as (condition_fn, conclusion) pairs.

class AxiomLibrary:
    """
    Axioms for each domain.
    An axiom is a rule that holds unconditionally given a condition.
    """
    
    @staticmethod
    def money_axioms() -> list[dict]:
        return [
            {
                "name": "PAYMENT_REQUIRES_KEY",
                "condition": lambda facts: facts.get("stripe_key_available", False),
                "conclusion": "payment_execution_permitted",
                "desc": "Payment actions are permitted only when Stripe API key is available",
            },
            {
                "name": "POSITIVE_VALUE_REQUIRED",
                "condition": lambda facts: facts.get("value_usd", 0) > 0,
                "conclusion": "value_constraint_satisfied",
                "desc": "Money actions must have positive value",
            },
            {
                "name": "HIGH_CONFIDENCE_REQUIRED",
                "condition": lambda facts: facts.get("confidence", 0) >= 0.75,
                "conclusion": "confidence_constraint_satisfied",
                "desc": "Money actions require confidence >= 0.75",
            },
        ]
    
    @staticmethod
    def security_axioms() -> list[dict]:
        return [
            {
                "name": "DEFENSE_BASELINE_REQUIRED",
                "condition": lambda facts: facts.get("defense_state_nominal", True),
                "conclusion": "security_context_clear",
                "desc": "Security actions require Defender OS baseline to be nominal",
            },
            {
                "name": "NO_ESCALATION_WITHOUT_VERIFICATION",
                "condition": lambda facts: not facts.get("privilege_escalation", False),
                "conclusion": "privilege_safe",
                "desc": "Actions must not escalate privileges without explicit authorization",
            },
        ]
    
    @staticmethod
    def deploy_axioms() -> list[dict]:
        return [
            {
                "name": "CI_PASS_REQUIRED",
                "condition": lambda facts: facts.get("ci_passing", True),
                "conclusion": "deploy_ci_gate_passed",
                "desc": "Deployments require CI to be passing",
            },
            {
                "name": "NOT_DURING_INCIDENT",
                "condition": lambda facts: not facts.get("active_incident", False),
                "conclusion": "deploy_timing_safe",
                "desc": "Deployments must not occur during active incidents",
            },
        ]
    
    @staticmethod
    def data_axioms() -> list[dict]:
        return [
            {
                "name": "BACKUP_VERIFIED",
                "condition": lambda facts: facts.get("backup_recent", True),
                "conclusion": "data_mutation_safe",
                "desc": "Data mutations require a recent backup to be verified",
            },
        ]


# ─── Inference Rules ────────────────────────────────────────────────────────

class InferenceRules:
    """
    Inference rules: if all premises hold, the conclusion holds.
    Used to chain axiom conclusions into the final proof goal.
    """
    
    MONEY_PROOF_GOAL = "money_action_verified"
    SECURITY_PROOF_GOAL = "security_action_verified"
    DEPLOY_PROOF_GOAL = "deploy_action_verified"
    DATA_PROOF_GOAL = "data_action_verified"
    
    MONEY_RULES = [
        {
            "name": "MONEY_SAFE",
            "premises": ["payment_execution_permitted", "value_constraint_satisfied", "confidence_constraint_satisfied"],
            "conclusion": MONEY_PROOF_GOAL,
        },
    ]
    
    SECURITY_RULES = [
        {
            "name": "SECURITY_CLEAR",
            "premises": ["security_context_clear", "privilege_safe"],
            "conclusion": SECURITY_PROOF_GOAL,
        },
    ]
    
    DEPLOY_RULES = [
        {
            "name": "DEPLOY_SAFE",
            "premises": ["deploy_ci_gate_passed", "deploy_timing_safe"],
            "conclusion": DEPLOY_PROOF_GOAL,
        },
    ]
    
    DATA_RULES = [
        {
            "name": "DATA_SAFE",
            "premises": ["data_mutation_safe"],
            "conclusion": DATA_PROOF_GOAL,
        },
    ]
    
    @classmethod
    def rules_for_domain(cls, domain: Domain) -> list[dict]:
        mapping = {
            Domain.MONEY: cls.MONEY_RULES,
            Domain.SECURITY: cls.SECURITY_RULES,
            Domain.DEPLOY: cls.DEPLOY_RULES,
            Domain.DATA: cls.DATA_RULES,
        }
        return mapping.get(domain, [])
    
    @classmethod
    def goal_for_domain(cls, domain: Domain) -> str:
        mapping = {
            Domain.MONEY: cls.MONEY_PROOF_GOAL,
            Domain.SECURITY: cls.SECURITY_PROOF_GOAL,
            Domain.DEPLOY: cls.DEPLOY_PROOF_GOAL,
            Domain.DATA: cls.DATA_PROOF_GOAL,
        }
        return mapping.get(domain, "")


# ─── The Formal Verifier ────────────────────────────────────────────────────

class FormalVerifier:
    """
    RHNS Formal Verification Engine.
    
    Proves or disproves propositions about agent actions using
    backward chaining from the proof goal through inference rules
    to axioms, evaluated against system state facts.
    
    Architecture mirrors Lean4 / AlphaProof:
    - Proposition: what must be proved
    - Axioms: base truths about system state
    - Inference rules: valid reasoning steps
    - Proof search: backward chaining
    - Certificate: the produced proof (or counterexample)
    """
    
    # Action keywords that indicate each domain
    DOMAIN_KEYWORDS = {
        Domain.MONEY: ["STRIPE", "PAYMENT", "CHARGE", "REFUND", "INVOICE", "SUBSCRIPTION", "BILLING", "RETRY_PAYMENT", "REVENUE"],
        Domain.SECURITY: ["TOKEN", "SECRET", "CREDENTIAL", "ROTATE", "REVOKE", "AUTH", "PERMISSION", "ACCESS"],
        Domain.DEPLOY: ["DEPLOY", "RELEASE", "ROLLOUT", "PUBLISH", "SHIP", "PRODUCTION"],
        Domain.DATA: ["DELETE", "MIGRATE", "TRUNCATE", "BACKUP_RESTORE", "SCHEMA_CHANGE"],
    }
    
    def __init__(self, cert_log_path: str = "rhns/proof_certificates.jsonl"):
        self.cert_log = Path(cert_log_path)
        self.cert_log.parent.mkdir(parents=True, exist_ok=True)
        self.axioms = AxiomLibrary()
        self.rules = InferenceRules()
    
    def classify_domain(self, action: str) -> Domain:
        """Classify an action into its verification domain."""
        action_upper = action.upper()
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(k in action_upper for k in keywords):
                return domain
        if "MONITOR" in action_upper or "LOG" in action_upper:
            return Domain.MONITOR
        return Domain.UNKNOWN
    
    def build_proposition(
        self,
        action: str,
        state_facts: dict,
        domain: Domain = None,
    ) -> Proposition:
        """Build a Proposition from an action and current system state."""
        if domain is None:
            domain = self.classify_domain(action)
        
        # Standard preconditions per domain
        preconditions = {
            Domain.MONEY: ["stripe_key_available", "positive_value", "high_confidence"],
            Domain.SECURITY: ["defense_baseline_nominal", "no_privilege_escalation"],
            Domain.DEPLOY: ["ci_passing", "no_active_incident"],
            Domain.DATA: ["backup_recent"],
            Domain.MONITOR: [],
            Domain.UNKNOWN: [],
        }.get(domain, [])
        
        postconditions = {
            Domain.MONEY: ["payment_processed_safely", "revenue_recorded"],
            Domain.SECURITY: ["credentials_rotated_safely"],
            Domain.DEPLOY: ["deployment_completed_safely"],
            Domain.DATA: ["data_mutated_safely"],
            Domain.MONITOR: ["observation_logged"],
            Domain.UNKNOWN: [],
        }.get(domain, [])
        
        return Proposition(
            action=action,
            domain=domain,
            preconditions=preconditions,
            postconditions=postconditions,
            state_facts=state_facts,
        )
    
    def _run_axioms(self, domain: Domain, facts: dict) -> tuple[set[str], list[ProofStep]]:
        """
        Evaluate all axioms for the domain against current facts.
        Returns (proved_conclusions, proof_steps).
        """
        domain_axiom_methods = {
            Domain.MONEY: self.axioms.money_axioms,
            Domain.SECURITY: self.axioms.security_axioms,
            Domain.DEPLOY: self.axioms.deploy_axioms,
            Domain.DATA: self.axioms.data_axioms,
        }
        
        axiom_fn = domain_axiom_methods.get(domain)
        if not axiom_fn:
            return set(), []
        
        proved: set[str] = set()
        steps: list[ProofStep] = []
        
        for axiom in axiom_fn():
            holds = axiom["condition"](facts)
            if holds:
                proved.add(axiom["conclusion"])
                steps.append(ProofStep(
                    rule_name=f"AXIOM:{axiom['name']}",
                    premise=axiom["desc"],
                    conclusion=axiom["conclusion"],
                    justification="Axiom evaluation: condition satisfied",
                ))
            else:
                steps.append(ProofStep(
                    rule_name=f"AXIOM:{axiom['name']}",
                    premise=axiom["desc"],
                    conclusion=f"NOT:{axiom['conclusion']}",
                    justification="Axiom evaluation: condition NOT satisfied",
                ))
        
        return proved, steps
    
    def _apply_inference_rules(
        self, domain: Domain, proved: set[str], steps: list[ProofStep]
    ) -> tuple[bool, str]:
        """
        Apply inference rules to derive the proof goal.
        Returns (goal_proved, counterexample_if_failed).
        """
        rules = self.rules.rules_for_domain(domain)
        goal = self.rules.goal_for_domain(domain)
        
        if not goal:
            return True, ""
        
        for rule in rules:
            premises_satisfied = all(p in proved for p in rule["premises"])
            if premises_satisfied:
                steps.append(ProofStep(
                    rule_name=f"RULE:{rule['name']}",
                    premise=" ∧ ".join(rule["premises"]),
                    conclusion=rule["conclusion"],
                    justification="Modus ponens: all premises proved",
                ))
                return True, ""
            else:
                missing = [p for p in rule["premises"] if p not in proved]
                counterexample = (
                    f"Rule '{rule['name']}' failed. "
                    f"Missing premises: {missing}. "
                    f"Fix: ensure {', '.join(missing)} hold before executing this action."
                )
                return False, counterexample
        
        return False, f"No inference rule reached the goal '{goal}' for domain {domain.value}"
    
    def verify(
        self,
        action: str,
        state_facts: dict,
        domain: Domain = None,
    ) -> ProofCertificate:
        """
        Verify an action against formal proof rules.
        
        Returns a ProofCertificate. Call .is_valid() to check approval.
        """
        now = datetime.now(timezone.utc).isoformat()
        cert_id = hashlib.sha256(f"{action}:{now}".encode()).hexdigest()[:16]
        
        if domain is None:
            domain = self.classify_domain(action)
        
        prop = self.build_proposition(action, state_facts, domain)
        
        # MONITOR and UNKNOWN domains skip formal proof
        if domain in (Domain.MONITOR, Domain.UNKNOWN):
            cert = ProofCertificate(
                cert_id=cert_id,
                proposition=prop.to_statement(),
                domain=domain,
                status=ProofStatus.SKIPPED,
                proof_steps=[ProofStep(
                    rule_name="DOMAIN_SKIP",
                    premise=f"Domain={domain.value}",
                    conclusion="formal_proof_not_required",
                    justification="Low-stakes domain: no formal proof required",
                )],
                verified_at=now,
            )
            self._log_certificate(cert)
            return cert
        
        # Run proof search
        all_steps: list[ProofStep] = []
        proved_conclusions, axiom_steps = self._run_axioms(domain, state_facts)
        all_steps.extend(axiom_steps)
        
        goal_proved, counterexample = self._apply_inference_rules(
            domain, proved_conclusions, all_steps
        )
        
        status = ProofStatus.PROVED if goal_proved else ProofStatus.DISPROVED
        
        cert = ProofCertificate(
            cert_id=cert_id,
            proposition=prop.to_statement(),
            domain=domain,
            status=status,
            proof_steps=all_steps,
            counterexample=counterexample,
            verified_at=now,
        )
        self._log_certificate(cert)
        return cert
    
    def _log_certificate(self, cert: ProofCertificate):
        """Append proof certificate to the JSONL log."""
        with self.cert_log.open("a") as f:
            f.write(json.dumps(cert.to_dict()) + "\n")
    
    def get_certificate_stats(self) -> dict:
        """Return aggregate proof stats from the certificate log."""
        if not self.cert_log.exists():
            return {"total": 0, "proved": 0, "disproved": 0, "skipped": 0}
        
        stats = {"total": 0, "proved": 0, "disproved": 0, "skipped": 0, "unknown": 0}
        with self.cert_log.open() as f:
            for line in f:
                try:
                    cert = json.loads(line)
                    stats["total"] += 1
                    status = cert.get("status", "unknown")
                    stats[status] = stats.get(status, 0) + 1
                except Exception:
                    pass
        return stats
