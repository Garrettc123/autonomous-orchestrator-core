"""Tests for Garcar Enterprise integration status helpers."""

from core.enterprise_status import build_enterprise_status


class TestBuildEnterpriseStatus:
    def test_defaults_include_priority_systems(self):
        status = build_enterprise_status()
        repos = {system["repo"] for system in status["systems"]}
        assert "garcar-payments" in repos
        assert "garcar-autonomous-wealth-system" in repos
        assert "autonomous-income-deployment" in repos
        assert "ai-business-platform" in repos
        assert "NEXUS-AI-CORE" in repos
        assert "zeus-dashboard" in repos

    def test_marks_systems_ready_when_required_env_present(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_value")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_value")
        monkeypatch.setenv("APOLLO_API_KEY", "apollo_test_value")
        monkeypatch.setenv("LINEAR_API_KEY", "linear_test_value")
        monkeypatch.setenv("GITHUB_TOKEN", "github_test_value")
        monkeypatch.setenv("OPENAI_API_KEY", "openai_test_value")
        monkeypatch.setenv("NEXUS_STATUS_ENDPOINT", "https://nexus.example/status")
        monkeypatch.setenv("ZEUS_STATUS_ENDPOINT", "https://zeus.example/status")

        status = build_enterprise_status()

        assert status["summary"]["ready_systems"] == status["summary"]["total_systems"]
        assert all(system["status"] == "ready" for system in status["systems"])

    def test_derives_arr_and_conversion_rate_from_metrics(self):
        status = build_enterprise_status({
            "mrr": 2500.0,
            "lead_count": 8,
            "paid_customers": 2,
            "churn_rate": 0.125,
        })

        assert status["kpis"]["arr"] == 30000.0
        assert status["kpis"]["conversion_rate"] == 0.25
        assert status["kpis"]["churn_rate"] == 0.125
