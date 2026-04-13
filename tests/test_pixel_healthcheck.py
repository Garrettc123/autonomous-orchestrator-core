"""Tests for the Pixel 10 Qwen health-check module."""

import pytest
from unittest.mock import patch, MagicMock

from modules.pixel_healthcheck import (
    load_config,
    is_enabled,
    poll_running_models,
    probe_latency,
    extract_memory_stats,
    build_slack_payload,
    post_to_slack,
    run_healthcheck,
    DEFAULT_CONFIG,
)


class TestLoadConfig:
    def test_loads_defaults_when_no_file(self, tmp_path):
        cfg = load_config(str(tmp_path / "nonexistent.yaml"))
        assert cfg['enabled'] is False
        assert cfg['endpoint']['base_url'] == 'http://pixel10.local:11434'
        assert cfg['polling']['interval_seconds'] == 300

    def test_loads_from_yaml_file(self, tmp_path):
        yaml_file = tmp_path / "test_config.yaml"
        yaml_file.write_text(
            "enabled: true\n"
            "endpoint:\n"
            "  base_url: 'http://192.168.1.50:11434'\n"
        )
        cfg = load_config(str(yaml_file))
        assert cfg['enabled'] is True
        assert cfg['endpoint']['base_url'] == 'http://192.168.1.50:11434'
        # Defaults still present for unset keys.
        assert cfg['polling']['timeout_seconds'] == 10

    def test_handles_empty_yaml(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        cfg = load_config(str(yaml_file))
        assert cfg['enabled'] is False


class TestIsEnabled:
    def test_disabled_by_default(self):
        cfg = {**DEFAULT_CONFIG, 'enabled': False}
        assert is_enabled(cfg) is False

    def test_enabled_requires_env_flag(self, monkeypatch):
        cfg = {
            'enabled': True,
            'activation_gate': {'env_flag': 'PIXEL_HEALTHCHECK_ENABLED'},
        }
        monkeypatch.delenv('PIXEL_HEALTHCHECK_ENABLED', raising=False)
        assert is_enabled(cfg) is False

    def test_enabled_with_env_flag_set(self, monkeypatch):
        cfg = {
            'enabled': True,
            'activation_gate': {'env_flag': 'PIXEL_HEALTHCHECK_ENABLED'},
        }
        monkeypatch.setenv('PIXEL_HEALTHCHECK_ENABLED', '1')
        assert is_enabled(cfg) is True

    def test_enabled_with_truthy_values(self, monkeypatch):
        cfg = {
            'enabled': True,
            'activation_gate': {'env_flag': 'PIXEL_HEALTHCHECK_ENABLED'},
        }
        for val in ('true', 'True', 'yes', '1'):
            monkeypatch.setenv('PIXEL_HEALTHCHECK_ENABLED', val)
            assert is_enabled(cfg) is True

    def test_disabled_with_falsy_env(self, monkeypatch):
        cfg = {
            'enabled': True,
            'activation_gate': {'env_flag': 'PIXEL_HEALTHCHECK_ENABLED'},
        }
        monkeypatch.setenv('PIXEL_HEALTHCHECK_ENABLED', '0')
        assert is_enabled(cfg) is False

    def test_enabled_no_gate_var(self):
        cfg = {
            'enabled': True,
            'activation_gate': {'env_flag': ''},
        }
        assert is_enabled(cfg) is True


class TestPollRunningModels:
    def test_successful_poll(self):
        cfg = load_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'models': [
                {
                    'name': 'qwen3:0.6b',
                    'size': 400_000_000,
                    'size_vram': 350_000_000,
                    'digest': 'abc123',
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch('modules.pixel_healthcheck.requests.get',
                   return_value=mock_resp):
            result = poll_running_models(cfg)

        assert result['ok'] is True
        assert len(result['models']) == 1
        assert result['error'] is None

    def test_connection_error(self):
        cfg = load_config()
        import requests as req
        with patch('modules.pixel_healthcheck.requests.get',
                   side_effect=req.ConnectionError('refused')):
            result = poll_running_models(cfg)

        assert result['ok'] is False
        assert 'refused' in result['error']

    def test_uses_env_override(self, monkeypatch):
        monkeypatch.setenv('PIXEL_OLLAMA_URL', 'http://custom:1234')
        cfg = load_config()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'models': []}
        mock_resp.raise_for_status = MagicMock()

        with patch('modules.pixel_healthcheck.requests.get',
                   return_value=mock_resp) as mock_get:
            poll_running_models(cfg)
            call_url = mock_get.call_args[0][0]
            assert call_url.startswith('http://custom:1234')


class TestProbeLatency:
    def test_successful_probe(self):
        cfg = load_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'total_duration': 1_500_000_000,  # 1500ms in nanoseconds
            'eval_duration': 1_000_000_000,   # 1000ms
            'eval_count': 5,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch('modules.pixel_healthcheck.requests.post',
                   return_value=mock_resp):
            result = probe_latency(cfg)

        assert result['ok'] is True
        assert result['total_duration_ms'] == 1500.0
        assert result['eval_duration_ms'] == 1000.0
        assert result['eval_count'] == 5
        assert result['tokens_per_second'] == 5.0

    def test_connection_error(self):
        cfg = load_config()
        import requests as req
        with patch('modules.pixel_healthcheck.requests.post',
                   side_effect=req.ConnectionError('timeout')):
            result = probe_latency(cfg)

        assert result['ok'] is False
        assert result['total_duration_ms'] is None
        assert 'timeout' in result['error']

    def test_zero_duration_fallback(self):
        cfg = load_config()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'total_duration': 0,
            'eval_duration': 0,
            'eval_count': 0,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch('modules.pixel_healthcheck.requests.post',
                   return_value=mock_resp):
            result = probe_latency(cfg)

        assert result['ok'] is True
        # Falls back to wall-clock time.
        assert result['total_duration_ms'] is not None


class TestExtractMemoryStats:
    def test_finds_matching_model(self):
        models = [
            {'name': 'qwen3:0.6b', 'size': 500_000_000,
             'size_vram': 400_000_000},
        ]
        stats = extract_memory_stats(models, 'qwen3:0.6b')
        assert stats['found'] is True
        assert stats['size_mb'] == pytest.approx(476.8, abs=0.1)
        assert stats['size_vram_mb'] == pytest.approx(381.5, abs=0.1)

    def test_no_matching_model(self):
        models = [{'name': 'llama3:8b', 'size': 1_000_000_000}]
        stats = extract_memory_stats(models, 'qwen3:0.6b')
        assert stats['found'] is False
        assert stats['size_mb'] is None

    def test_empty_models_list(self):
        stats = extract_memory_stats([], 'qwen3:0.6b')
        assert stats['found'] is False


class TestBuildSlackPayload:
    def _make_config(self):
        return load_config()

    def test_healthy_payload(self):
        cfg = self._make_config()
        ps = {'ok': True, 'models': [{'name': 'qwen3:0.6b'}]}
        latency = {
            'ok': True, 'total_duration_ms': 500,
            'tokens_per_second': 10.0,
        }
        memory = {'found': True, 'size_mb': 400.0, 'size_vram_mb': 350.0}

        payload = build_slack_payload(cfg, ps, latency, memory)
        assert 'Healthy' in payload['text']
        assert '#autonomous-ops' == payload['channel']

    def test_down_payload(self):
        cfg = self._make_config()
        ps = {'ok': False, 'models': [], 'error': 'Connection refused'}
        latency = {'ok': False, 'total_duration_ms': None, 'error': 'timeout'}
        memory = {'found': False, 'size_mb': None}

        payload = build_slack_payload(cfg, ps, latency, memory)
        assert 'Down' in payload['text']

    def test_degraded_on_high_latency(self):
        cfg = self._make_config()
        ps = {'ok': True, 'models': [{'name': 'qwen3:0.6b'}]}
        latency = {
            'ok': True, 'total_duration_ms': 6000,
            'tokens_per_second': 2.0,
        }
        memory = {'found': True, 'size_mb': 400.0, 'size_vram_mb': None}

        payload = build_slack_payload(cfg, ps, latency, memory)
        assert 'Degraded' in payload['text']
        assert 'threshold' in payload['text'].lower()


class TestPostToSlack:
    def test_posts_via_webhook(self, monkeypatch):
        monkeypatch.setenv(
            'SLACK_HEALTHCHECK_WEBHOOK_URL',
            'https://hooks.slack.com/test',
        )
        monkeypatch.delenv('SLACK_BOT_TOKEN', raising=False)
        cfg = load_config()
        payload = {'channel': '#test', 'text': 'hello'}

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch('modules.pixel_healthcheck.requests.post',
                   return_value=mock_resp) as mock_post:
            result = post_to_slack(cfg, payload)
            assert result is True
            call_url = mock_post.call_args[0][0]
            assert 'hooks.slack.com' in call_url

    def test_falls_back_to_bot_token(self, monkeypatch):
        monkeypatch.delenv('SLACK_HEALTHCHECK_WEBHOOK_URL', raising=False)
        monkeypatch.setenv(
            'SLACK_BOT_TOKEN', 'xoxb-long-enough-token-for-test'
        )
        cfg = load_config()
        payload = {'channel': '#test', 'text': 'hello'}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'ok': True}

        with patch('modules.pixel_healthcheck.requests.post',
                   return_value=mock_resp) as mock_post:
            result = post_to_slack(cfg, payload)
            assert result is True
            call_url = mock_post.call_args[0][0]
            assert 'chat.postMessage' in call_url

    def test_no_credentials_prints_to_stdout(self, monkeypatch, capsys):
        monkeypatch.delenv('SLACK_HEALTHCHECK_WEBHOOK_URL', raising=False)
        monkeypatch.delenv('SLACK_BOT_TOKEN', raising=False)
        cfg = load_config()
        payload = {'channel': '#test', 'text': 'report text'}

        result = post_to_slack(cfg, payload)
        assert result is False
        captured = capsys.readouterr().out
        assert 'report text' in captured

    def test_webhook_network_error(self, monkeypatch):
        monkeypatch.setenv(
            'SLACK_HEALTHCHECK_WEBHOOK_URL',
            'https://hooks.slack.com/test',
        )
        cfg = load_config()
        payload = {'channel': '#test', 'text': 'hello'}

        import requests as req
        with patch('modules.pixel_healthcheck.requests.post',
                   side_effect=req.ConnectionError('timeout')):
            result = post_to_slack(cfg, payload)
            assert result is False


class TestRunHealthcheck:
    def test_returns_full_result(self):
        cfg = load_config()

        mock_ps_resp = MagicMock()
        mock_ps_resp.json.return_value = {
            'models': [
                {'name': 'qwen3:0.6b', 'size': 400_000_000,
                 'size_vram': 350_000_000},
            ]
        }
        mock_ps_resp.raise_for_status = MagicMock()

        mock_gen_resp = MagicMock()
        mock_gen_resp.json.return_value = {
            'total_duration': 800_000_000,
            'eval_duration': 500_000_000,
            'eval_count': 3,
        }
        mock_gen_resp.raise_for_status = MagicMock()

        with patch('modules.pixel_healthcheck.requests.get',
                   return_value=mock_ps_resp):
            with patch('modules.pixel_healthcheck.requests.post',
                       return_value=mock_gen_resp):
                result = run_healthcheck(cfg)

        assert result['endpoint']['ok'] is True
        assert result['latency']['ok'] is True
        assert result['memory']['found'] is True
        assert result['model'] == 'qwen3:0.6b'

    def test_handles_endpoint_down(self):
        cfg = load_config()

        import requests as req
        with patch('modules.pixel_healthcheck.requests.get',
                   side_effect=req.ConnectionError('refused')):
            with patch('modules.pixel_healthcheck.requests.post',
                       side_effect=req.ConnectionError('refused')):
                result = run_healthcheck(cfg)

        assert result['endpoint']['ok'] is False
        assert result['latency']['ok'] is False
        assert result['memory']['found'] is False
