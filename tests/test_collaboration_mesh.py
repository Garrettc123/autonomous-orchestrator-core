"""Tests for the CollaborationMesh integration module."""

import pytest
from unittest.mock import MagicMock, patch, call
from security.one_key import OneKeySystem
from integrations.collaboration_mesh import CollaborationMesh


FAKE_SEED = "test_seed_for_collaboration_mesh_tests"


def make_mesh(env_vars=None, monkeypatch=None):
    """Helper to create a CollaborationMesh with a test OneKeySystem."""
    security = OneKeySystem(FAKE_SEED)
    if monkeypatch and env_vars:
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)
    return CollaborationMesh(security)


class TestCollaborationMeshInit:
    def test_init_without_env_vars(self, monkeypatch):
        monkeypatch.delenv("NOTION_TOKEN", raising=False)
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        mesh = make_mesh()
        # When env vars missing, credentials come from OneKeySystem derivation (non-None)
        assert mesh is not None

    def test_init_uses_env_vars_over_derived(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-fake-slack-token-for-testing-purposes")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)
        assert mesh.slack_token == "xoxb-fake-slack-token-for-testing-purposes"


class TestBroadcastPulse:
    def test_no_token_silently_skips(self, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        # Force short token from derived key - patch get_credential to return short string
        security = OneKeySystem(FAKE_SEED)
        with patch.object(security, "get_credential", return_value="short"):
            mesh = CollaborationMesh(security)
            # Should not raise even if requests would fail
            with patch("requests.post") as mock_post:
                mesh.broadcast_pulse("hello")
                mock_post.assert_not_called()

    def test_broadcasts_message_on_valid_token(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-a-long-enough-fake-token-here-x")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            mesh.broadcast_pulse("Test message", "info")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert "autonomous-ops" in str(call_kwargs)

    def test_broadcasts_warning_level(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-a-long-enough-fake-token-here-x")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}

        with patch("requests.post", return_value=mock_resp):
            # Should not raise
            mesh.broadcast_pulse("Warning!", "warning")

    def test_handles_network_exception_silently(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-a-long-enough-fake-token-here-x")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        with patch("requests.post", side_effect=ConnectionError("timeout")):
            # Should not raise
            mesh.broadcast_pulse("Test")

    def test_logs_non_scope_slack_error(self, monkeypatch, capsys):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-a-long-enough-fake-token-here-x")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": False, "error": "channel_not_found"}

        with patch("requests.post", return_value=mock_resp):
            mesh.broadcast_pulse("Test")
        out = capsys.readouterr().out
        assert "channel_not_found" in out


class TestGetLinearTeamId:
    def test_returns_team_id_on_success(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_a_long_enough_fake_key_value")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"teams": {"nodes": [{"id": "team-123", "name": "My Team"}]}}
        }
        with patch("requests.post", return_value=mock_resp):
            team_id = mesh._get_linear_team_id()
        assert team_id == "team-123"

    def test_returns_none_on_empty_teams(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_a_long_enough_fake_key_value")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"teams": {"nodes": []}}}
        with patch("requests.post", return_value=mock_resp):
            team_id = mesh._get_linear_team_id()
        assert team_id is None

    def test_returns_none_on_exception(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_a_long_enough_fake_key_value")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        with patch("requests.post", side_effect=Exception("network error")):
            team_id = mesh._get_linear_team_id()
        assert team_id is None


class TestCreateOptimizationTask:
    def test_skips_if_no_linear_key(self, monkeypatch, capsys):
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)
        security = OneKeySystem(FAKE_SEED)
        with patch.object(security, "get_credential", return_value="short"):
            mesh = CollaborationMesh(security)
            result = mesh.create_optimization_task("Title", "Desc")
        assert result == "skipped"

    def test_returns_no_team_when_team_lookup_fails(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_a_long_enough_fake_key_value")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        with patch.object(mesh, "_get_linear_team_id", return_value=None):
            result = mesh.create_optimization_task("Title", "Desc")
        assert result == "no_team"

    def test_creates_issue_successfully(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_a_long_enough_fake_key_value")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"issueCreate": {"issue": {"id": "issue-1", "identifier": "ENG-42"}}}
        }

        with patch.object(mesh, "_get_linear_team_id", return_value="team-abc"):
            with patch("requests.post", return_value=mock_resp):
                result = mesh.create_optimization_task("Test Issue", "Description here", 2)

        assert result == "ENG-42"

    def test_returns_error_on_api_errors(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_a_long_enough_fake_key_value")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errors": [{"message": "Unauthorized"}]}

        with patch.object(mesh, "_get_linear_team_id", return_value="team-abc"):
            with patch("requests.post", return_value=mock_resp):
                result = mesh.create_optimization_task("Title", "Desc")

        assert result == "error"

    def test_returns_net_error_on_exception(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_a_long_enough_fake_key_value")
        security = OneKeySystem(FAKE_SEED)
        mesh = CollaborationMesh(security)

        with patch.object(mesh, "_get_linear_team_id", return_value="team-abc"):
            with patch("requests.post", side_effect=ConnectionError("timeout")):
                result = mesh.create_optimization_task("Title", "Desc")

        assert result == "net_error"
