"""Tests for the RHNS LocalInferenceClient module."""

import pytest
import requests as req_lib
from unittest.mock import patch, MagicMock
from modules.local_inference import LocalInferenceClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Return a LocalInferenceClient loaded from the real config file."""
    return LocalInferenceClient()


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestConfigLoading:
    def test_loads_pixel_10_node(self, client):
        node = client.get_node("pixel_10")
        assert node is not None
        assert node.name == "pixel_10"
        assert "11434" in node.base_url
        assert "qwen2.5" in node.model_name

    def test_pixel_10_defaults(self, client):
        node = client.get_node("pixel_10")
        assert node.status == "pending"
        assert node.request_timeout_s == 30
        assert node.max_input_tokens == 1536
        assert node.max_output_tokens == 512

    def test_model_parameters_parsed(self, client):
        node = client.get_node("pixel_10")
        assert node.context_length == 2048
        assert node.temperature == 0.7
        assert node.top_p == 0.9
        assert node.num_gpu == 0

    def test_unknown_node_returns_none(self, client):
        assert client.get_node("nonexistent_node") is None

    def test_env_override_base_url(self, monkeypatch):
        monkeypatch.setenv("RHNS_PIXEL_ENDPOINT", "http://10.0.0.42:11434")
        c = LocalInferenceClient()
        node = c.get_node("pixel_10")
        assert node.base_url == "http://10.0.0.42:11434"

    def test_env_override_model_name(self, monkeypatch):
        monkeypatch.setenv("RHNS_PIXEL_MODEL", "qwen2.5:0.5b-instruct")
        c = LocalInferenceClient()
        node = c.get_node("pixel_10")
        assert node.model_name == "qwen2.5:0.5b-instruct"

    def test_env_override_status(self, monkeypatch):
        monkeypatch.setenv("RHNS_PIXEL_STATUS", "active")
        c = LocalInferenceClient()
        node = c.get_node("pixel_10")
        assert node.status == "active"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_healthy_endpoint(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "qwen2.5:0.5b"}, {"name": "phi3:mini"}]
        }
        with patch("modules.local_inference.requests.get", return_value=mock_resp):
            result = client.check_health("pixel_10")
        assert result["reachable"] is True
        assert "qwen2.5:0.5b" in result["models"]
        assert result["error"] is None

    def test_unhealthy_endpoint_status_code(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("modules.local_inference.requests.get", return_value=mock_resp):
            result = client.check_health("pixel_10")
        assert result["reachable"] is False
        assert "503" in result["error"]

    def test_unreachable_endpoint(self, client):
        with patch(
            "modules.local_inference.requests.get",
            side_effect=req_lib.ConnectionError("refused"),
        ):
            result = client.check_health("pixel_10")
        assert result["reachable"] is False
        assert "refused" in result["error"]

    def test_unknown_node_health(self, client):
        result = client.check_health("no_such_node")
        assert result["reachable"] is False
        assert "Unknown node" in result["error"]


# ---------------------------------------------------------------------------
# Inference (generate)
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_rejects_pending_node(self, client):
        result = client.generate("Hello", node_name="pixel_10")
        assert result.error is not None
        assert "not active" in result.error

    def test_active_node_success(self, monkeypatch):
        monkeypatch.setenv("RHNS_PIXEL_STATUS", "active")
        c = LocalInferenceClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "Hello! How can I help?",
            "model": "qwen2.5:0.5b",
            "eval_count": 8,
            "total_duration": 450_000_000,  # 450 ms in nanoseconds
        }
        with patch("modules.local_inference.requests.post", return_value=mock_resp):
            result = c.generate("Hi there")
        assert result.text == "Hello! How can I help?"
        assert result.model == "qwen2.5:0.5b"
        assert result.tokens_generated == 8
        assert result.latency_ms == pytest.approx(450.0)
        assert result.error is None
        assert result.node == "pixel_10"

    def test_active_node_http_error(self, monkeypatch):
        monkeypatch.setenv("RHNS_PIXEL_STATUS", "active")
        c = LocalInferenceClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("modules.local_inference.requests.post", return_value=mock_resp):
            result = c.generate("Test")
        assert result.error is not None
        assert "500" in result.error

    def test_active_node_network_error(self, monkeypatch):
        monkeypatch.setenv("RHNS_PIXEL_STATUS", "active")
        c = LocalInferenceClient()
        with patch(
            "modules.local_inference.requests.post",
            side_effect=req_lib.ConnectionError("timeout"),
        ):
            result = c.generate("Test")
        assert result.error is not None
        assert "timeout" in result.error

    def test_unknown_node_generate(self, client):
        result = client.generate("Hello", node_name="no_such_node")
        assert result.error is not None
        assert "Unknown node" in result.error

    def test_custom_temperature_and_max_tokens(self, monkeypatch):
        monkeypatch.setenv("RHNS_PIXEL_STATUS", "active")
        c = LocalInferenceClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "ok",
            "model": "qwen2.5:0.5b",
            "eval_count": 1,
            "total_duration": 100_000_000,
        }
        with patch("modules.local_inference.requests.post", return_value=mock_resp) as mock_post:
            c.generate("Test", temperature=0.2, max_tokens=64)

        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["options"]["temperature"] == 0.2
        assert call_payload["options"]["num_predict"] == 64


# ---------------------------------------------------------------------------
# Status summary
# ---------------------------------------------------------------------------

class TestStatusSummary:
    def test_returns_all_nodes(self, client):
        summary = client.status_summary()
        assert "pixel_10" in summary
        assert summary["pixel_10"]["status"] == "pending"
        assert "qwen2.5" in summary["pixel_10"]["model"]
