"""
Tests for RHNS Formal Verification Layer
==========================================
9 unit tests covering proof success, failure, domain classification,
certificate structure, and counterexample generation.
"""

import sys
import os
import pytest

# Allow direct import without package install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.formal_verifier import (
    FormalVerifier,
    Domain,
    ProofStatus,
)


@pytest.fixture
def verifier(tmp_path):
    """Return a FormalVerifier with a temp cert log path."""
    return FormalVerifier(cert_log_path=str(tmp_path / "proof_certificates.jsonl"))


# ── Test 1 ──────────────────────────────────────────────────────────────────

def test_money_action_proves_with_valid_facts(verifier):
    """Full valid facts for a MONEY action should yield PROVED."""
    facts = {
        "stripe_key_available": True,
        "value_usd": 49.99,
        "confidence": 0.90,
    }
    cert = verifier.verify("STRIPE_CHARGE_CUSTOMER", facts)
    assert cert.status == ProofStatus.PROVED
    assert cert.is_valid()
    assert cert.domain == Domain.MONEY


# ── Test 2 ──────────────────────────────────────────────────────────────────

def test_money_action_disproves_without_stripe_key(verifier):
    """Missing Stripe key should cause the MONEY proof to be DISPROVED."""
    facts = {
        "stripe_key_available": False,
        "value_usd": 99.0,
        "confidence": 0.85,
    }
    cert = verifier.verify("STRIPE_CHARGE_CUSTOMER", facts)
    assert cert.status == ProofStatus.DISPROVED
    assert not cert.is_valid()


# ── Test 3 ──────────────────────────────────────────────────────────────────

def test_money_action_disproves_low_confidence(verifier):
    """Confidence below 0.75 should cause the MONEY proof to be DISPROVED."""
    facts = {
        "stripe_key_available": True,
        "value_usd": 49.99,
        "confidence": 0.30,
    }
    cert = verifier.verify("RETRY_PAYMENT_SUBSCRIPTION", facts)
    assert cert.status == ProofStatus.DISPROVED
    assert not cert.is_valid()


# ── Test 4 ──────────────────────────────────────────────────────────────────

def test_security_action_proves_with_clear_baseline(verifier):
    """Nominal defense baseline, no privilege escalation → PROVED."""
    facts = {
        "defense_state_nominal": True,
        "privilege_escalation": False,
    }
    cert = verifier.verify("ROTATE_TOKEN_API_KEY", facts)
    assert cert.status == ProofStatus.PROVED
    assert cert.is_valid()
    assert cert.domain == Domain.SECURITY


# ── Test 5 ──────────────────────────────────────────────────────────────────

def test_deploy_action_proves_ci_passing(verifier):
    """CI passing, no active incident → DEPLOY proof should be PROVED."""
    facts = {
        "ci_passing": True,
        "active_incident": False,
    }
    cert = verifier.verify("DEPLOY_PRODUCTION_RELEASE", facts)
    assert cert.status == ProofStatus.PROVED
    assert cert.is_valid()
    assert cert.domain == Domain.DEPLOY


# ── Test 6 ──────────────────────────────────────────────────────────────────

def test_deploy_action_disproves_during_incident(verifier):
    """Active incident present → DEPLOY proof should be DISPROVED."""
    facts = {
        "ci_passing": True,
        "active_incident": True,
    }
    cert = verifier.verify("DEPLOY_PRODUCTION_RELEASE", facts)
    assert cert.status == ProofStatus.DISPROVED
    assert not cert.is_valid()


# ── Test 7 ──────────────────────────────────────────────────────────────────

def test_monitor_action_skips_proof(verifier):
    """MONITOR domain should be SKIPPED — and still considered valid (no block)."""
    facts = {}
    cert = verifier.verify("MONITOR_SYSTEM_HEALTH_LOG", facts)
    assert cert.status == ProofStatus.SKIPPED
    assert cert.is_valid()


# ── Test 8 ──────────────────────────────────────────────────────────────────

def test_certificate_has_proof_steps(verifier):
    """A verified certificate (any domain) must contain at least one proof step."""
    facts = {
        "stripe_key_available": True,
        "value_usd": 10.0,
        "confidence": 0.80,
    }
    cert = verifier.verify("PAYMENT_INVOICE_SEND", facts)
    assert len(cert.proof_steps) > 0


# ── Test 9 ──────────────────────────────────────────────────────────────────

def test_counterexample_populated_on_failure(verifier):
    """A DISPROVED certificate must have a non-empty counterexample string."""
    facts = {
        "stripe_key_available": True,
        "value_usd": 0,          # violates POSITIVE_VALUE_REQUIRED
        "confidence": 0.95,
    }
    cert = verifier.verify("STRIPE_CHARGE_CUSTOMER", facts)
    assert cert.status == ProofStatus.DISPROVED
    assert cert.counterexample != ""
    assert len(cert.counterexample) > 0
