"""Tests for FastAPI app startup and health endpoints."""

from main import app, health, root


def test_app_metadata_is_stable():
    assert app.title == "Autonomous Orchestrator Core"
    assert app.version == "1.0.0"


def test_health_endpoint_returns_healthy_status():
    assert health() == {
        "status": "healthy",
        "system": "Autonomous Orchestrator Core",
    }


def test_root_endpoint_exposes_service_metadata():
    payload = root()
    assert payload["status"] == "operational"
    assert payload["status_endpoint"] == "/status"
