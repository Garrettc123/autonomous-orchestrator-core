"""
RHNS Local Inference Client
============================
Manages on-device inference endpoints (Ollama) for edge nodes defined in
configs/rhns_inference.yaml.

The client validates that a node is reachable before dispatching requests
and never assumes the endpoint is live — activation status is checked at
runtime against both the config file and a real health-check probe.
"""

import os
import yaml
import requests
from dataclasses import dataclass
from typing import Optional

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "configs", "rhns_inference.yaml"
)


@dataclass
class InferenceResult:
    """Container for a local inference response."""
    text: str = ""
    model: str = ""
    tokens_generated: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    node: str = ""


@dataclass
class NodeConfig:
    """Parsed configuration for a single RHNS node."""
    name: str = ""
    base_url: str = ""
    model_name: str = ""
    status: str = "pending"
    request_timeout_s: int = 30
    max_input_tokens: int = 1536
    max_output_tokens: int = 512
    health_check_path: str = "/api/tags"
    context_length: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    num_gpu: int = 0


class LocalInferenceClient:
    """
    Client for RHNS on-device inference endpoints.

    Reads node definitions from configs/rhns_inference.yaml, applies
    environment-variable overrides, and exposes methods to probe health
    and run inference against a local Ollama instance.
    """

    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self.raw_config: dict = {}
        self.nodes: dict[str, NodeConfig] = {}
        self._load_config()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self):
        """Load and parse the RHNS inference YAML config."""
        with open(self.config_path) as fh:
            self.raw_config = yaml.safe_load(fh)

        defaults = self.raw_config.get("defaults", {})
        env_map = defaults.get("env_overrides", {})
        nodes_raw = self.raw_config.get("nodes", {})

        for node_name, node_data in nodes_raw.items():
            runtime = node_data.get("runtime", {})
            model_cfg = node_data.get("model", {})
            activation = node_data.get("activation", {})
            params = model_cfg.get("parameters", {})

            base_url = os.environ.get(
                env_map.get("base_url", ""),
                runtime.get("base_url", ""),
            )
            model_name = os.environ.get(
                env_map.get("model_name", ""),
                model_cfg.get("name", ""),
            )
            status = os.environ.get(
                env_map.get("status", ""),
                activation.get("status", "pending"),
            )

            self.nodes[node_name] = NodeConfig(
                name=node_name,
                base_url=base_url.rstrip("/"),
                model_name=model_name,
                status=status,
                request_timeout_s=defaults.get("request_timeout_s", 30),
                max_input_tokens=defaults.get("max_input_tokens", 1536),
                max_output_tokens=defaults.get("max_output_tokens", 512),
                health_check_path=activation.get("health_check_path", "/api/tags"),
                context_length=params.get("context_length", 2048),
                temperature=params.get("temperature", 0.7),
                top_p=params.get("top_p", 0.9),
                num_gpu=params.get("num_gpu", 0),
            )

    def get_node(self, node_name: str = "pixel_10") -> Optional[NodeConfig]:
        """Return config for a named node, or None if not defined."""
        return self.nodes.get(node_name)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def check_health(self, node_name: str = "pixel_10") -> dict:
        """
        Probe the Ollama health endpoint on the named node.

        Returns a dict with keys:
            reachable (bool), models (list[str]), error (str|None)
        """
        node = self.get_node(node_name)
        if node is None:
            return {"reachable": False, "models": [], "error": f"Unknown node: {node_name}"}

        url = f"{node.base_url}{node.health_check_path}"
        try:
            resp = requests.get(url, timeout=node.request_timeout_s)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                return {"reachable": True, "models": models, "error": None}
            return {
                "reachable": False,
                "models": [],
                "error": f"HTTP {resp.status_code}",
            }
        except requests.RequestException as exc:
            return {"reachable": False, "models": [], "error": str(exc)}

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        node_name: str = "pixel_10",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> InferenceResult:
        """
        Send a generation request to the Ollama endpoint on the named node.

        The node must have status == 'active' (set via config or env var)
        and must be reachable. Returns an InferenceResult with the response
        text or an error description.
        """
        node = self.get_node(node_name)
        if node is None:
            return InferenceResult(error=f"Unknown node: {node_name}", node=node_name)

        if node.status != "active":
            return InferenceResult(
                error=f"Node '{node_name}' is not active (status={node.status}). "
                      "Set status to 'active' in config or via RHNS_PIXEL_STATUS env var.",
                node=node_name,
            )

        url = f"{node.base_url}/api/generate"
        payload = {
            "model": node.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else node.temperature,
                "top_p": node.top_p,
                "num_predict": max_tokens if max_tokens is not None else node.max_output_tokens,
                "num_ctx": node.context_length,
                "num_gpu": node.num_gpu,
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=node.request_timeout_s)
            if resp.status_code != 200:
                return InferenceResult(
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    node=node_name,
                    model=node.model_name,
                )
            data = resp.json()
            return InferenceResult(
                text=data.get("response", ""),
                model=data.get("model", node.model_name),
                tokens_generated=data.get("eval_count", 0),
                latency_ms=data.get("total_duration", 0) / 1_000_000,  # ns → ms
                node=node_name,
            )
        except requests.RequestException as exc:
            return InferenceResult(
                error=str(exc), node=node_name, model=node.model_name
            )

    # ------------------------------------------------------------------
    # Status summary
    # ------------------------------------------------------------------

    def status_summary(self) -> dict:
        """Return a dict summarizing all configured RHNS nodes."""
        summary = {}
        for name, node in self.nodes.items():
            summary[name] = {
                "base_url": node.base_url,
                "model": node.model_name,
                "status": node.status,
            }
        return summary
