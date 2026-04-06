"""Tests for the ProsperityFlow core module."""

import pytest
from core.prosperity_flow import ProsperityFlow, WealthSignal


class TestWealthSignal:
    def test_defaults(self):
        sig = WealthSignal(source_system="test", amount=100.0)
        assert sig.currency == "USD"
        assert sig.velocity == 1.0
        assert sig.integrity_score == 1.0

    def test_custom_values(self):
        sig = WealthSignal(
            source_system="stripe",
            amount=500.0,
            currency="EUR",
            velocity=2.0,
            integrity_score=0.95,
        )
        assert sig.source_system == "stripe"
        assert sig.amount == 500.0
        assert sig.currency == "EUR"
        assert sig.velocity == 2.0
        assert sig.integrity_score == 0.95


class TestProsperityFlowInit:
    def test_init_no_stripe_key(self, capsys):
        flow = ProsperityFlow()
        assert flow.total_ecosystem_value == 0.0
        assert flow.flow_rate == 0.0
        assert flow.abundance_threshold == 0.88
        out = capsys.readouterr().out
        assert "Stripe" in out

    def test_init_with_stripe_key(self, capsys, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake_key_for_testing")
        ProsperityFlow()
        out = capsys.readouterr().out
        # Either connected (if stripe installed) or package-not-installed warning
        assert "Stripe" in out or "stripe" in out.lower()

    def test_init_stripe_key_cleared_after_test(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        flow = ProsperityFlow()
        assert flow is not None


class TestProsperityFlowManifest:
    @pytest.mark.asyncio
    async def test_manifest_revenue_success(self, capsys):
        flow = ProsperityFlow()
        signal = WealthSignal(source_system="stripe", amount=1000.0)
        result = await flow.manifest_revenue(signal)
        assert result is True
        assert flow.total_ecosystem_value == 1000.0
        assert flow.flow_rate == 1000.0

    @pytest.mark.asyncio
    async def test_manifest_revenue_low_integrity(self, capsys):
        flow = ProsperityFlow()
        signal = WealthSignal(source_system="bad_source", amount=500.0, integrity_score=0.5)
        result = await flow.manifest_revenue(signal)
        assert result is False
        assert flow.total_ecosystem_value == 0.0

    @pytest.mark.asyncio
    async def test_manifest_revenue_accumulates(self):
        flow = ProsperityFlow()
        sig1 = WealthSignal(source_system="s1", amount=100.0)
        sig2 = WealthSignal(source_system="s2", amount=200.0)
        await flow.manifest_revenue(sig1)
        await flow.manifest_revenue(sig2)
        assert flow.total_ecosystem_value == 300.0

    @pytest.mark.asyncio
    async def test_manifest_revenue_velocity(self):
        flow = ProsperityFlow()
        signal = WealthSignal(source_system="fast", amount=100.0, velocity=3.0)
        await flow.manifest_revenue(signal)
        assert flow.flow_rate == 300.0

    @pytest.mark.asyncio
    async def test_manifest_revenue_boundary_integrity(self):
        flow = ProsperityFlow()
        # Exactly at boundary: 0.9 → should succeed
        signal = WealthSignal(source_system="edge", amount=50.0, integrity_score=0.9)
        result = await flow.manifest_revenue(signal)
        assert result is True


class TestProsperityFlowStatus:
    def test_get_status_keys(self):
        flow = ProsperityFlow()
        status = flow.get_status()
        assert "total_value" in status
        assert "flow_rate" in status
        assert "abundance_level" in status
        assert "timestamp" in status

    def test_get_status_initial_values(self):
        flow = ProsperityFlow()
        status = flow.get_status()
        assert status["total_value"] == 0.0
        assert status["flow_rate"] == 0.0
        assert status["abundance_level"] == 0.0

    def test_get_status_abundance_capped_at_one(self):
        flow = ProsperityFlow()
        flow.flow_rate = 1_000_000.0
        status = flow.get_status()
        assert status["abundance_level"] <= 1.0

    def test_get_status_timestamp_format(self):
        from datetime import datetime
        flow = ProsperityFlow()
        status = flow.get_status()
        # Should be parseable ISO format
        datetime.fromisoformat(status["timestamp"])
