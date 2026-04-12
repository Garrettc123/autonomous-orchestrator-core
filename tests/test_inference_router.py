"""
Unit tests for RHNS Two-Tier Inference Router.
All HTTP calls are mocked via unittest.mock.patch.
"""

import unittest
from unittest.mock import patch, MagicMock

from modules.inference_router import (
    InferenceRouter,
    InferenceRequest,
    InferenceTier,
)


def _make_ollama_response(text="ok", eval_count=10):
    """Helper: build a mock Ollama /api/generate response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": text, "eval_count": eval_count}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _make_openai_response(text="cloud_ok", total_tokens=50, model="gpt-4o-mini"):
    """Helper: build a mock OpenAI /v1/chat/completions response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": text}}],
        "usage": {"total_tokens": total_tokens},
        "model": model,
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _make_ollama_tags_ok():
    """Helper: mock a healthy /api/tags probe."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    return mock_resp


class TestSymbolicRouting(unittest.TestCase):
    """Test 1: heartbeat routes to SYMBOLIC with zero HTTP calls."""

    @patch("modules.inference_router.requests.post")
    @patch("modules.inference_router.requests.get")
    def test_symbolic_signal_no_http_call(self, mock_get, mock_post):
        router = InferenceRouter(openai_api_key="sk-test")
        req = InferenceRequest(
            prompt="ping",
            signal_type="heartbeat",
            urgency="low",
            value_usd=0.0,
        )
        resp = router.route(req)

        mock_get.assert_not_called()
        mock_post.assert_not_called()
        self.assertEqual(resp.tier_used, InferenceTier.SYMBOLIC)
        self.assertEqual(resp.model, "symbolic")
        self.assertIsNone(resp.error)


class TestCloudRouting(unittest.TestCase):
    """Test 2: payment_failed (cloud-forced signal) routes to CLOUD."""

    @patch("modules.inference_router.requests.post")
    def test_high_urgency_routes_to_cloud(self, mock_post):
        mock_post.return_value = _make_openai_response()

        router = InferenceRouter(openai_api_key="sk-test")
        req = InferenceRequest(
            prompt="Payment failed for customer X, what should we do?",
            signal_type="payment_failed",
            urgency="immediate",
            value_usd=250.0,
        )
        resp = router.route(req)

        self.assertEqual(resp.tier_used, InferenceTier.CLOUD)
        self.assertIsNone(resp.error)
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        self.assertIn("openai.com", call_url)


class TestLocalRouting(unittest.TestCase):
    """Test 3: low-urgency monitoring signal routes to LOCAL."""

    @patch("modules.inference_router.requests.post")
    @patch("modules.inference_router.requests.get")
    def test_low_urgency_routes_to_local(self, mock_get, mock_post):
        mock_get.return_value = _make_ollama_tags_ok()
        mock_post.return_value = _make_ollama_response(text="classified: normal")

        router = InferenceRouter(openai_api_key="sk-test")
        req = InferenceRequest(
            prompt="Classify this metric: CPU 45%",
            signal_type="monitoring",
            urgency="low",
            value_usd=0.0,
        )
        resp = router.route(req)

        self.assertEqual(resp.tier_used, InferenceTier.LOCAL)
        self.assertEqual(resp.cost_estimate_usd, 0.0)
        self.assertIsNone(resp.error)
        # Verify the POST went to Ollama, not OpenAI
        call_url = mock_post.call_args[0][0]
        self.assertIn("11434", call_url)


class TestFallbackToCloud(unittest.TestCase):
    """Test 4: when LOCAL is down, router falls back to CLOUD."""

    @patch("modules.inference_router.requests.post")
    @patch("modules.inference_router.requests.get")
    def test_fallback_to_cloud_when_local_down(self, mock_get, mock_post):
        # Ollama probe fails
        mock_get.side_effect = ConnectionError("Ollama not running")

        # Cloud succeeds
        mock_post.return_value = _make_openai_response(text="cloud_fallback")

        router = InferenceRouter(openai_api_key="sk-test")
        req = InferenceRequest(
            prompt="Classify signal",
            signal_type="monitoring",
            urgency="low",
            value_usd=0.0,
        )
        resp = router.route(req)

        # Should have fallen back to CLOUD
        self.assertEqual(resp.tier_used, InferenceTier.CLOUD)
        self.assertIsNone(resp.error)
        self.assertEqual(resp.text, "cloud_fallback")


class TestThinkingEffort(unittest.TestCase):
    """Test 5: value=$500 + urgency=immediate → reasoning_effort=high."""

    def test_thinking_effort_high_for_large_value(self):
        router = InferenceRouter(openai_api_key="sk-test")
        effort = router._thinking_effort(urgency="immediate", value_usd=500.0)
        self.assertEqual(effort, "high")

    def test_thinking_effort_medium_for_high_urgency_low_value(self):
        router = InferenceRouter(openai_api_key="sk-test")
        effort = router._thinking_effort(urgency="high", value_usd=10.0)
        self.assertEqual(effort, "medium")

    def test_thinking_effort_low_for_medium_urgency(self):
        router = InferenceRouter(openai_api_key="sk-test")
        effort = router._thinking_effort(urgency="medium", value_usd=50.0)
        self.assertEqual(effort, "low")


class TestMissingApiKey(unittest.TestCase):
    """Test 6: missing OpenAI key returns graceful error, does not crash."""

    @patch("modules.inference_router.requests.get")
    def test_no_openai_key_returns_error_not_crash(self, mock_get):
        # Ollama also unavailable so it goes to cloud path
        mock_get.side_effect = ConnectionError("no ollama")

        router = InferenceRouter(openai_api_key="")  # no key
        req = InferenceRequest(
            prompt="Revenue dropped 40%, action needed",
            signal_type="revenue_anomaly",
            urgency="immediate",
            value_usd=500.0,
        )
        resp = router.route(req)

        # Must not raise; error field should indicate missing key
        self.assertIsNotNone(resp.error)
        self.assertIn("OPENAI_API_KEY", resp.error)
        self.assertEqual(resp.text, "")
        self.assertEqual(resp.cost_estimate_usd, 0.0)


class TestTierStats(unittest.TestCase):
    """Test 7: tier_stats() returns a dict with all expected keys."""

    @patch("modules.inference_router.requests.get")
    def test_tier_stats_returns_dict(self, mock_get):
        mock_get.return_value = _make_ollama_tags_ok()

        router = InferenceRouter(openai_api_key="sk-test")
        stats = router.tier_stats()

        expected_keys = {
            "local_available",
            "cloud_available",
            "cloud_model_standard",
            "cloud_model_high_stakes",
            "local_model",
            "high_stakes_threshold_usd",
        }
        self.assertTrue(expected_keys.issubset(stats.keys()))
        self.assertIsInstance(stats["local_available"], bool)
        self.assertIsInstance(stats["cloud_available"], bool)
        self.assertTrue(stats["cloud_available"])  # key was provided
        self.assertEqual(stats["high_stakes_threshold_usd"], 100.0)


if __name__ == "__main__":
    unittest.main()
