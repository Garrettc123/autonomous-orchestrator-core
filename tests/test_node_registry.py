"""Tests for the NodeRegistry core module."""

import os

import pytest
import yaml

from core.node_registry import (
    NodeHealth,
    NodeRegistry,
    NodeTransport,
    OrchestrationNode,
)


def _make_node_entry(**overrides):
    """Return a minimal valid node dict, with optional overrides."""
    base = {
        "node_id": "test-node",
        "display_name": "Test Node",
        "enabled": False,
        "transport": {
            "protocol": "https",
            "host": "test.local",
            "port": 8443,
        },
        "health": {
            "initial_status": "pending",
        },
        "capabilities": ["edge_inference"],
        "role": "edge",
    }
    base.update(overrides)
    return base


def _write_registry(nodes, tmp_path):
    """Write a node registry YAML file and return its path."""
    path = os.path.join(str(tmp_path), "node_registry.yaml")
    with open(path, "w") as f:
        yaml.dump({"nodes": nodes}, f)
    return path


# --- NodeTransport ---


class TestNodeTransport:
    def test_base_url(self):
        t = NodeTransport(protocol="https", host="example.com", port=8443)
        assert t.base_url == "https://example.com:8443/v1/orchestrate"

    def test_base_url_custom_path(self):
        t = NodeTransport(
            protocol="https", host="example.com", port=443, path="/custom"
        )
        assert t.base_url == "https://example.com:443/custom"

    def test_defaults(self):
        t = NodeTransport(protocol="https", host="h", port=1)
        assert t.timeout_seconds == 30
        assert t.retry_attempts == 3
        assert t.retry_backoff_seconds == 2


# --- NodeHealth ---


class TestNodeHealth:
    def test_defaults(self):
        h = NodeHealth()
        assert h.endpoint == "/healthz"
        assert h.interval_seconds == 60
        assert h.initial_status == "pending"


# --- OrchestrationNode ---


class TestOrchestrationNode:
    def test_health_url(self):
        t = NodeTransport(protocol="https", host="n.local", port=8443)
        h = NodeHealth(endpoint="/healthz")
        node = OrchestrationNode(
            node_id="n1",
            display_name="N1",
            enabled=False,
            transport=t,
            health=h,
            capabilities=[],
            role="edge",
        )
        assert node.health_url == "https://n.local:8443/healthz"


# --- NodeRegistry loading ---


class TestNodeRegistryLoad:
    def test_load_valid_registry(self, tmp_path, capsys):
        nodes = [_make_node_entry()]
        path = _write_registry(nodes, tmp_path)
        registry = NodeRegistry(path=path)
        assert len(registry.nodes) == 1
        assert registry.nodes[0].node_id == "test-node"
        out = capsys.readouterr().out
        assert "1 node(s) registered" in out

    def test_load_multiple_nodes(self, tmp_path):
        nodes = [
            _make_node_entry(node_id="a", role="edge"),
            _make_node_entry(node_id="b", role="compute"),
        ]
        path = _write_registry(nodes, tmp_path)
        registry = NodeRegistry(path=path)
        assert len(registry.nodes) == 2

    def test_load_missing_file(self, tmp_path, capsys):
        path = os.path.join(str(tmp_path), "missing.yaml")
        registry = NodeRegistry(path=path)
        assert len(registry.nodes) == 0
        out = capsys.readouterr().out
        assert "not found" in out

    def test_load_empty_file(self, tmp_path, capsys):
        path = os.path.join(str(tmp_path), "empty.yaml")
        with open(path, "w") as f:
            f.write("")
        registry = NodeRegistry(path=path)
        assert len(registry.nodes) == 0
        out = capsys.readouterr().out
        assert "empty" in out

    def test_load_real_registry(self, capsys):
        """Verify the actual configs/node_registry.yaml loads correctly."""
        registry = NodeRegistry()
        assert len(registry.nodes) >= 1
        pixel = registry.get_node("pixel-10")
        assert pixel is not None
        assert pixel.enabled is False
        assert pixel.role == "edge"


# --- Validation ---


class TestNodeRegistryValidation:
    def test_missing_required_field(self, tmp_path):
        entry = _make_node_entry()
        del entry["role"]
        path = _write_registry([entry], tmp_path)
        with pytest.raises(ValueError, match="missing fields"):
            NodeRegistry(path=path)

    def test_missing_transport_field(self, tmp_path):
        entry = _make_node_entry()
        del entry["transport"]["host"]
        path = _write_registry([entry], tmp_path)
        with pytest.raises(ValueError, match="transport missing"):
            NodeRegistry(path=path)

    def test_invalid_role(self, tmp_path):
        entry = _make_node_entry(role="invalid_role")
        path = _write_registry([entry], tmp_path)
        with pytest.raises(ValueError, match="invalid role"):
            NodeRegistry(path=path)

    def test_invalid_health_status(self, tmp_path):
        entry = _make_node_entry()
        entry["health"]["initial_status"] = "bad_status"
        path = _write_registry([entry], tmp_path)
        with pytest.raises(ValueError, match="invalid health status"):
            NodeRegistry(path=path)


# --- Query methods ---


class TestNodeRegistryQueries:
    @pytest.fixture()
    def registry(self, tmp_path):
        nodes = [
            _make_node_entry(
                node_id="a", enabled=False, role="edge",
                capabilities=["edge_inference", "telemetry_relay"],
            ),
            _make_node_entry(
                node_id="b", enabled=True, role="compute",
                capabilities=["batch_processing"],
            ),
            _make_node_entry(
                node_id="c", enabled=True, role="edge",
                capabilities=["edge_inference"],
            ),
        ]
        path = _write_registry(nodes, tmp_path)
        return NodeRegistry(path=path)

    def test_get_node_found(self, registry):
        node = registry.get_node("a")
        assert node is not None
        assert node.node_id == "a"

    def test_get_node_not_found(self, registry):
        assert registry.get_node("nonexistent") is None

    def test_get_enabled_nodes(self, registry):
        enabled = registry.get_enabled_nodes()
        assert len(enabled) == 2
        ids = {n.node_id for n in enabled}
        assert ids == {"b", "c"}

    def test_get_nodes_by_role(self, registry):
        edges = registry.get_nodes_by_role("edge")
        assert len(edges) == 2
        computes = registry.get_nodes_by_role("compute")
        assert len(computes) == 1

    def test_get_nodes_by_capability(self, registry):
        infer = registry.get_nodes_by_capability("edge_inference")
        assert len(infer) == 2
        batch = registry.get_nodes_by_capability("batch_processing")
        assert len(batch) == 1
        empty = registry.get_nodes_by_capability("nonexistent")
        assert len(empty) == 0

    def test_get_status(self, registry):
        status = registry.get_status()
        assert status["total_registered"] == 3
        assert status["enabled"] == 2
        assert status["disabled"] == 1
        assert "edge" in status["by_role"]
        assert "compute" in status["by_role"]


# --- Pixel 10 specific checks ---


class TestPixel10Registration:
    def test_pixel10_is_disabled(self):
        registry = NodeRegistry()
        pixel = registry.get_node("pixel-10")
        assert pixel is not None
        assert pixel.enabled is False

    def test_pixel10_transport(self):
        registry = NodeRegistry()
        pixel = registry.get_node("pixel-10")
        assert pixel.transport.protocol == "https"
        assert pixel.transport.port == 8443
        assert pixel.transport.host == "pixel10.edge.orchestrator.internal"

    def test_pixel10_health_pending(self):
        registry = NodeRegistry()
        pixel = registry.get_node("pixel-10")
        assert pixel.health.initial_status == "pending"

    def test_pixel10_capabilities(self):
        registry = NodeRegistry()
        pixel = registry.get_node("pixel-10")
        assert "edge_inference" in pixel.capabilities
        assert "sensor_fusion" in pixel.capabilities

    def test_pixel10_role_and_tags(self):
        registry = NodeRegistry()
        pixel = registry.get_node("pixel-10")
        assert pixel.role == "edge"
        assert pixel.tags.get("device_class") == "mobile"
        assert pixel.tags.get("hardware") == "pixel_10"
