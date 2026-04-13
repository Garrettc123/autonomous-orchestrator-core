"""
PIXEL 10 QWEN HEALTH CHECK MODULE
===================================
Polls the on-device Ollama /api/ps endpoint on a Pixel 10 node and
reports inference latency plus memory statistics to Slack.

Gated: will not run unless explicitly enabled via config or env var.
"""

import os
import time
import json
import requests
import yaml
from typing import Dict, Any, Optional

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'configs', 'pixel_healthcheck.yaml'
)

DEFAULT_CONFIG = {
    'enabled': False,
    'endpoint': {
        'base_url': 'http://pixel10.local:11434',
        'ps_path': '/api/ps',
        'generate_path': '/api/generate',
    },
    'polling': {
        'interval_seconds': 300,
        'timeout_seconds': 10,
        'failure_threshold': 3,
    },
    'activation_gate': {
        'env_flag': 'PIXEL_HEALTHCHECK_ENABLED',
    },
    'model': {
        'name': 'qwen3:0.6b',
    },
    'latency_probe': {
        'prompt': 'ping',
        'stream': False,
    },
    'slack': {
        'channel': '#autonomous-ops',
        'webhook_secret_name': 'SLACK_HEALTHCHECK_WEBHOOK_URL',
        'healthy_report_every_n': 12,
    },
    'thresholds': {
        'latency_warn_ms': 5000,
        'memory_warn_mb': 3072,
    },
}


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load health-check config from YAML, falling back to defaults."""
    cfg_path = path or CONFIG_PATH
    try:
        with open(cfg_path, 'r') as f:
            file_cfg = yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError):
        file_cfg = {}

    # Merge file config over defaults (shallow per top-level key).
    merged = {}
    for key in DEFAULT_CONFIG:
        if isinstance(DEFAULT_CONFIG[key], dict):
            merged[key] = {**DEFAULT_CONFIG[key], **file_cfg.get(key, {})}
        else:
            merged[key] = file_cfg.get(key, DEFAULT_CONFIG[key])
    return merged


def is_enabled(config: Dict[str, Any]) -> bool:
    """Check whether the health-check should run.

    Returns True only when BOTH conditions are met:
    1. config['enabled'] is True, AND
    2. The activation gate env var (if configured) is set and truthy.
    """
    if not config.get('enabled', False):
        return False

    gate_var = (
        config.get('activation_gate', {}).get('env_flag', '')
    )
    if gate_var:
        val = os.environ.get(gate_var, '').strip().lower()
        if val not in ('1', 'true', 'yes'):
            return False
    return True


def poll_running_models(config: Dict[str, Any]) -> Dict[str, Any]:
    """Call Ollama /api/ps and return running model info.

    Returns a dict with keys:
        ok (bool), models (list), error (str|None)
    Each model dict includes name, size, size_vram, digest, etc.
    """
    base_url = os.environ.get(
        'PIXEL_OLLAMA_URL',
        config['endpoint']['base_url'],
    )
    url = base_url.rstrip('/') + config['endpoint']['ps_path']
    timeout = config['polling']['timeout_seconds']

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        models = data.get('models', [])
        return {'ok': True, 'models': models, 'error': None}
    except requests.RequestException as exc:
        return {'ok': False, 'models': [], 'error': str(exc)}


def probe_latency(config: Dict[str, Any]) -> Dict[str, Any]:
    """Send a minimal generate request to measure inference latency.

    Returns a dict with keys:
        ok (bool),
        total_duration_ms (float|None),
        eval_duration_ms (float|None),
        eval_count (int|None),
        tokens_per_second (float|None),
        error (str|None)
    """
    base_url = os.environ.get(
        'PIXEL_OLLAMA_URL',
        config['endpoint']['base_url'],
    )
    url = base_url.rstrip('/') + config['endpoint']['generate_path']
    timeout = config['polling']['timeout_seconds']
    model_name = config['model']['name']
    probe_cfg = config.get('latency_probe', {})

    payload = {
        'model': model_name,
        'prompt': probe_cfg.get('prompt', 'ping'),
        'stream': probe_cfg.get('stream', False),
    }

    try:
        start = time.monotonic()
        resp = requests.post(url, json=payload, timeout=timeout)
        wall_ms = (time.monotonic() - start) * 1000
        resp.raise_for_status()
        data = resp.json()

        # Ollama returns durations in nanoseconds.
        total_ns = data.get('total_duration', 0)
        eval_ns = data.get('eval_duration', 0)
        eval_count = data.get('eval_count', 0)

        total_ms = total_ns / 1_000_000 if total_ns else wall_ms
        eval_ms = eval_ns / 1_000_000 if eval_ns else None
        tps = (
            (eval_count / (eval_ns / 1e9)) if eval_ns and eval_count
            else None
        )

        return {
            'ok': True,
            'total_duration_ms': round(total_ms, 2),
            'eval_duration_ms': round(eval_ms, 2) if eval_ms else None,
            'eval_count': eval_count,
            'tokens_per_second': round(tps, 2) if tps else None,
            'error': None,
        }
    except requests.RequestException as exc:
        return {
            'ok': False,
            'total_duration_ms': None,
            'eval_duration_ms': None,
            'eval_count': None,
            'tokens_per_second': None,
            'error': str(exc),
        }


def extract_memory_stats(
    models: list, model_name: str
) -> Dict[str, Any]:
    """Extract memory stats for the target model from /api/ps output.

    Returns dict with keys:
        found (bool), size_mb (float|None), size_vram_mb (float|None)
    """
    for m in models:
        if m.get('name', '').startswith(model_name.split(':')[0]):
            size_bytes = m.get('size', 0)
            vram_bytes = m.get('size_vram', 0)
            return {
                'found': True,
                'size_mb': round(size_bytes / (1024 * 1024), 1),
                'size_vram_mb': round(vram_bytes / (1024 * 1024), 1),
            }
    return {'found': False, 'size_mb': None, 'size_vram_mb': None}


def _check_threshold_warnings(
    latency_result: Dict[str, Any],
    memory_stats: Dict[str, Any],
    thresholds: Dict[str, Any],
) -> list:
    """Return a list of threshold-violation warning strings."""
    warnings = []
    latency_warn = thresholds.get('latency_warn_ms', 5000)
    memory_warn = thresholds.get('memory_warn_mb', 3072)

    lat_ms = latency_result.get('total_duration_ms')
    if lat_ms and lat_ms > latency_warn:
        warnings.append(
            f"Latency {lat_ms}ms > {latency_warn}ms threshold"
        )

    mem_mb = memory_stats.get('size_mb')
    if mem_mb and mem_mb > memory_warn:
        warnings.append(
            f"Memory {mem_mb}MB > {memory_warn}MB threshold"
        )
    return warnings


def _format_detail_lines(
    ps_result: Dict[str, Any],
    latency_result: Dict[str, Any],
    memory_stats: Dict[str, Any],
) -> list:
    """Build the detail lines for the Slack report body."""
    lines = []
    if ps_result['ok']:
        model_count = len(ps_result.get('models', []))
        lines.append(f"  Models loaded: {model_count}")
    else:
        lines.append(
            f"  Endpoint error: {ps_result.get('error', 'unknown')}"
        )

    if latency_result['ok']:
        lines.append(
            f"  Inference latency: "
            f"{latency_result['total_duration_ms']}ms"
        )
        if latency_result.get('tokens_per_second'):
            lines.append(
                f"  Throughput: "
                f"{latency_result['tokens_per_second']} tok/s"
            )
    else:
        lines.append(
            f"  Latency probe failed: "
            f"{latency_result.get('error', 'unknown')}"
        )

    if memory_stats.get('found'):
        lines.append(f"  Model memory: {memory_stats['size_mb']}MB")
        if memory_stats.get('size_vram_mb'):
            lines.append(
                f"  VRAM usage: {memory_stats['size_vram_mb']}MB"
            )
    return lines


def build_slack_payload(
    config: Dict[str, Any],
    ps_result: Dict[str, Any],
    latency_result: Dict[str, Any],
    memory_stats: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a Slack message payload summarizing health-check results."""
    thresholds = config.get('thresholds', {})
    warnings = _check_threshold_warnings(
        latency_result, memory_stats, thresholds
    )

    is_healthy = ps_result['ok'] and latency_result['ok']
    if not is_healthy:
        icon, status = "rotating_light", "Down"
    elif warnings:
        icon, status = "warning", "Degraded"
    else:
        icon, status = "white_check_mark", "Healthy"

    lines = [f":{icon}: *Pixel 10 Qwen Health Check* - {status}"]
    lines.extend(
        _format_detail_lines(ps_result, latency_result, memory_stats)
    )
    for w in warnings:
        lines.append(f"  :warning: {w}")

    return {
        'channel': config['slack']['channel'],
        'text': '\n'.join(lines),
    }


def post_to_slack(
    config: Dict[str, Any], payload: Dict[str, Any]
) -> bool:
    """Post health-check payload to Slack via webhook or Bot API.

    Tries webhook URL first (SLACK_HEALTHCHECK_WEBHOOK_URL), then
    falls back to SLACK_BOT_TOKEN with chat.postMessage.
    """
    webhook_url = os.environ.get('SLACK_HEALTHCHECK_WEBHOOK_URL', '')
    bot_token = os.environ.get('SLACK_BOT_TOKEN', '')

    if webhook_url:
        try:
            resp = requests.post(
                webhook_url,
                json={'text': payload['text']},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    if bot_token and len(bot_token) >= 20:
        try:
            resp = requests.post(
                'https://slack.com/api/chat.postMessage',
                headers={
                    'Authorization': f'Bearer {bot_token}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=10,
            )
            return resp.json().get('ok', False)
        except requests.RequestException:
            return False

    print("[pixel-healthcheck] No Slack credentials configured. "
          "Printing report to stdout.")
    print(payload.get('text', ''))
    return False


def run_healthcheck(
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute one health-check cycle. Returns the full result dict."""
    if config is None:
        config = load_config()

    ps_result = poll_running_models(config)
    latency_result = probe_latency(config)

    model_name = config['model']['name']
    memory_stats = extract_memory_stats(
        ps_result.get('models', []), model_name
    )

    return {
        'endpoint': ps_result,
        'latency': latency_result,
        'memory': memory_stats,
        'model': model_name,
    }


def run_loop(config: Optional[Dict[str, Any]] = None) -> None:
    """Run the health-check in a polling loop (for app-level use)."""
    if config is None:
        config = load_config()

    if not is_enabled(config):
        print("[pixel-healthcheck] Disabled. Set enabled: true in "
              "config and PIXEL_HEALTHCHECK_ENABLED=1 to activate.")
        return

    interval = config['polling']['interval_seconds']
    failure_threshold = config['polling']['failure_threshold']
    healthy_report_n = config['slack'].get('healthy_report_every_n', 12)
    consecutive_failures = 0
    poll_count = 0

    print(f"[pixel-healthcheck] Starting poll loop "
          f"(interval={interval}s, model={config['model']['name']})")

    while True:
        result = run_healthcheck(config)
        poll_count += 1

        is_ok = (
            result['endpoint']['ok'] and result['latency']['ok']
        )

        if not is_ok:
            consecutive_failures += 1
        else:
            consecutive_failures = 0

        should_post = False
        if not is_ok and consecutive_failures >= failure_threshold:
            should_post = True
        elif is_ok and healthy_report_n > 0 and (
            poll_count % healthy_report_n == 0
        ):
            should_post = True

        if should_post:
            payload = build_slack_payload(
                config,
                result['endpoint'],
                result['latency'],
                result['memory'],
            )
            post_to_slack(config, payload)

        print(
            f"[pixel-healthcheck] poll={poll_count} "
            f"ok={is_ok} failures={consecutive_failures}"
        )

        time.sleep(interval)


if __name__ == '__main__':
    cfg = load_config()
    if is_enabled(cfg):
        run_loop(cfg)
    else:
        print("[pixel-healthcheck] Not enabled. "
              "Running single check for diagnostics.")
        result = run_healthcheck(cfg)
        print(json.dumps(result, indent=2))
