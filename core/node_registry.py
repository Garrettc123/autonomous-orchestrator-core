#!/usr/bin/env python3
"""
NODE REGISTRY - Orchestration Node Management
Loads, validates, and queries registered autonomous nodes from the
node registry configuration.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml


REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "configs",
    "node_registry.yaml",
)

VALID_ROLES = {"edge", "relay", "compute", "coordinator"}
VALID_HEALTH_STATUSES = {"pending", "healthy", "degraded", "unreachable"}
REQUIRED_NODE_FIELDS = {
    "node_id", "display_name", "enabled", "transport",
    "health", "capabilities", "role",
}
REQUIRED_TRANSPORT_FIELDS = {"protocol", "host", "port"}


@dataclass
class NodeTransport:
    protocol: str
    host: str
    port: int
    path: str = "/v1/orchestrate"
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_backoff_seconds: int = 2

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}{self.path}"


@dataclass
class NodeHealth:
    endpoint: str = "/healthz"
    interval_seconds: int = 60
    timeout_seconds: int = 10
    failure_threshold: int = 3
    expected_status: int = 200
    initial_status: str = "pending"


@dataclass
class OrchestrationNode:
    node_id: str
    display_name: str
    enabled: bool
    transport: NodeTransport
    health: NodeHealth
    capabilities: List[str]
    role: str
    priority: int = 100
    tags: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    @property
    def health_url(self) -> str:
        t = self.transport
        return f"{t.protocol}://{t.host}:{t.port}{self.health.endpoint}"


class NodeRegistry:
    """Loads and manages orchestration nodes from the YAML registry."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or REGISTRY_PATH
        self.nodes: List[OrchestrationNode] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            print(f"⚠️  Node registry not found at {self.path}")
            return

        with open(self.path, "r") as f:
            data = yaml.safe_load(f)

        if not data or "nodes" not in data:
            print("⚠️  Node registry is empty or missing 'nodes' key")
            return

        for entry in data["nodes"]:
            self._validate(entry)
            node = self._parse_node(entry)
            self.nodes.append(node)

        print(f"📡 Node registry loaded: {len(self.nodes)} node(s) registered")

    def _validate(self, entry: dict):
        missing = REQUIRED_NODE_FIELDS - set(entry.keys())
        if missing:
            raise ValueError(
                f"Node '{entry.get('node_id', '?')}' missing fields: {missing}"
            )

        transport = entry.get("transport", {})
        missing_transport = REQUIRED_TRANSPORT_FIELDS - set(transport.keys())
        if missing_transport:
            raise ValueError(
                f"Node '{entry['node_id']}' transport missing: {missing_transport}"
            )

        role = entry.get("role", "")
        if role not in VALID_ROLES:
            raise ValueError(
                f"Node '{entry['node_id']}' has invalid role '{role}'. "
                f"Must be one of {VALID_ROLES}"
            )

        status = entry.get("health", {}).get("initial_status", "pending")
        if status not in VALID_HEALTH_STATUSES:
            raise ValueError(
                f"Node '{entry['node_id']}' has invalid health status '{status}'. "
                f"Must be one of {VALID_HEALTH_STATUSES}"
            )

    def _parse_node(self, entry: dict) -> OrchestrationNode:
        transport_data = entry["transport"]
        health_data = entry.get("health", {})

        transport = NodeTransport(
            protocol=transport_data["protocol"],
            host=transport_data["host"],
            port=transport_data["port"],
            path=transport_data.get("path", "/v1/orchestrate"),
            timeout_seconds=transport_data.get("timeout_seconds", 30),
            retry_attempts=transport_data.get("retry_attempts", 3),
            retry_backoff_seconds=transport_data.get("retry_backoff_seconds", 2),
        )

        health = NodeHealth(
            endpoint=health_data.get("endpoint", "/healthz"),
            interval_seconds=health_data.get("interval_seconds", 60),
            timeout_seconds=health_data.get("timeout_seconds", 10),
            failure_threshold=health_data.get("failure_threshold", 3),
            expected_status=health_data.get("expected_status", 200),
            initial_status=health_data.get("initial_status", "pending"),
        )

        return OrchestrationNode(
            node_id=entry["node_id"],
            display_name=entry["display_name"],
            enabled=entry["enabled"],
            transport=transport,
            health=health,
            capabilities=entry.get("capabilities", []),
            role=entry["role"],
            priority=entry.get("priority", 100),
            tags=entry.get("tags", {}),
            metadata=entry.get("metadata", {}),
        )

    def get_node(self, node_id: str) -> Optional[OrchestrationNode]:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_enabled_nodes(self) -> List[OrchestrationNode]:
        return [n for n in self.nodes if n.enabled]

    def get_nodes_by_role(self, role: str) -> List[OrchestrationNode]:
        return [n for n in self.nodes if n.role == role]

    def get_nodes_by_capability(self, capability: str) -> List[OrchestrationNode]:
        return [n for n in self.nodes if capability in n.capabilities]

    def get_status(self) -> dict:
        return {
            "total_registered": len(self.nodes),
            "enabled": len(self.get_enabled_nodes()),
            "disabled": len(self.nodes) - len(self.get_enabled_nodes()),
            "by_role": {
                role: len(self.get_nodes_by_role(role))
                for role in VALID_ROLES
                if self.get_nodes_by_role(role)
            },
        }
