"""Tests for the MarketIntelligence module."""

import pytest
from unittest.mock import MagicMock, patch
from modules.market_intelligence import MarketIntelligence


class TestMarketIntelligenceInit:
    def test_init_creates_targets(self):
        mi = MarketIntelligence()
        assert isinstance(mi.targets, dict)
        assert len(mi.targets) > 0

    def test_init_has_user_agent(self):
        mi = MarketIntelligence()
        assert "User-Agent" in mi.headers
        assert len(mi.headers["User-Agent"]) > 0

    def test_known_competitors_present(self):
        mi = MarketIntelligence()
        assert "Kore.ai" in mi.targets
        assert "Microsoft" in mi.targets
        assert "Salesforce" in mi.targets


class TestScanLandscape:
    def test_scan_returns_list(self):
        mi = MarketIntelligence()
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network unavailable")
            result = mi.scan_landscape()
        assert isinstance(result, list)

    def test_scan_returns_empty_on_all_errors(self):
        mi = MarketIntelligence()
        with patch("requests.get") as mock_get:
            mock_get.side_effect = ConnectionError("timeout")
            result = mi.scan_landscape()
        assert result == []

    def test_scan_parses_headings(self):
        mi = MarketIntelligence()
        html = "<html><body><h2>New AI Agent Feature Released Today</h2></body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html

        with patch("requests.get", return_value=mock_resp):
            result = mi.scan_landscape()

        assert len(result) > 0
        assert any("New AI Agent Feature Released Today" in r for r in result)

    def test_scan_skips_non_200_responses(self):
        mi = MarketIntelligence()
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("requests.get", return_value=mock_resp):
            result = mi.scan_landscape()

        assert result == []

    def test_scan_skips_short_headings(self):
        mi = MarketIntelligence()
        html = "<html><body><h2>Hi</h2></body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html

        with patch("requests.get", return_value=mock_resp):
            result = mi.scan_landscape()

        assert result == []

    def test_scan_includes_competitor_name(self):
        mi = MarketIntelligence()
        html = "<html><body><h2>Autonomous Agent Platform Launch 2024</h2></body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html

        with patch("requests.get", return_value=mock_resp):
            result = mi.scan_landscape()

        for item in result:
            # Each detected feature should have competitor label prefix
            assert ":" in item


class TestAnalyzeThreatLevel:
    def setup_method(self):
        self.mi = MarketIntelligence()

    def test_no_features_returns_low(self):
        assert self.mi.analyze_threat_level([]) == "LOW - MAINTENANCE MODE"

    def test_threat_keyword_autonomous(self):
        features = ["Kore.ai: Autonomous AI Workflow Engine"]
        result = self.mi.analyze_threat_level(features)
        assert "HIGH" in result

    def test_threat_keyword_agent(self):
        features = ["Microsoft: New agent capabilities released"]
        result = self.mi.analyze_threat_level(features)
        assert "HIGH" in result

    def test_threat_keyword_self_healing(self):
        features = ["Salesforce: self-healing infrastructure platform"]
        result = self.mi.analyze_threat_level(features)
        assert "HIGH" in result

    def test_no_keywords_returns_low(self):
        features = ["Kore.ai: New pricing plan announced", "Microsoft: Blog post about culture"]
        result = self.mi.analyze_threat_level(features)
        assert result == "LOW - MAINTENANCE MODE"

    def test_case_insensitive_detection(self):
        features = ["Kore.ai: AUTONOMOUS SYSTEM LAUNCHED"]
        result = self.mi.analyze_threat_level(features)
        assert "HIGH" in result
