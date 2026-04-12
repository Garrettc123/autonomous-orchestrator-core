"""
RHNS DAG Orchestrator
======================
Replaces run_all_systems.py with a dependency-aware,
failure-isolated, capability-routing execution engine.

Architecture: AgentNet-style DAG + RHNS routing
- Nodes declare capabilities and dependencies
- Orchestrator builds and validates the execution DAG
- Topological sort enables maximum parallelism
- Failure of one node does NOT propagate to independent nodes
- Signals route to nodes by capability, not by position

Research basis:
- AgentNet: decentralized DAG with dynamic specialization (arXiv 2504.00587)
- HALO: hierarchical planning → role design → inference agents (arXiv 2505.13516)
- SagaLLM: transactional guarantees + compensation rollback (ACM 2025)
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Callable


logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"   # Skipped because a dependency failed


@dataclass
class AgentNode:
    """A single agent node in the execution DAG."""
    node_id: str
    name: str
    description: str

    # Capability declaration
    provides: list[str] = field(default_factory=list)   # e.g. ["revenue_signal", "stripe_events"]
    requires: list[str] = field(default_factory=list)   # e.g. ["stripe_events"] — must be provided by a dependency
    consumes: list[str] = field(default_factory=list)   # Signal types this node processes
    emits: list[str] = field(default_factory=list)      # Signal types this node produces

    # Execution config
    priority: int = 3           # 1=critical, 2=high, 3=normal, 4=low
    timeout_s: float = 30.0
    max_retries: int = 1
    critical: bool = False      # If True and this fails, halt entire orchestration

    # Runtime state (set by orchestrator)
    status: NodeStatus = NodeStatus.PENDING
    result: dict = field(default_factory=dict)
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    retry_count: int = 0

    # Execution function (async callable)
    execute_fn: Optional[Callable] = field(default=None, repr=False)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None


@dataclass
class OrchestrationResult:
    """Result of a full DAG orchestration run."""
    run_id: str
    started_at: str
    completed_at: str
    total_nodes: int
    succeeded: int
    failed: int
    skipped: int
    total_duration_ms: float
    node_results: dict[str, dict] = field(default_factory=dict)
    halted_early: bool = False
    halt_reason: str = ""


class DAGOrchestrator:
    """
    Dependency-aware parallel execution engine for RHNS agent nodes.

    Usage:
        orchestrator = DAGOrchestrator()
        orchestrator.register(my_node)
        result = await orchestrator.run()
    """

    def __init__(self, max_parallelism: int = 8):
        self.nodes: dict[str, AgentNode] = {}
        self.max_parallelism = max_parallelism
        self._semaphore: Optional[asyncio.Semaphore] = None

    def register(self, node: AgentNode) -> "DAGOrchestrator":
        """Register a node. Returns self for chaining."""
        self.nodes[node.node_id] = node
        return self

    def _build_dependency_edges(self) -> dict[str, list[str]]:
        """
        Build dependency edges from capability declarations.
        Node A depends on Node B if B.provides intersects A.requires.
        Returns {node_id: [dependency_node_ids]}
        """
        # Map capability → node_id
        capability_provider: dict[str, str] = {}
        for node_id, node in self.nodes.items():
            for cap in node.provides:
                capability_provider[cap] = node_id

        deps: dict[str, list[str]] = defaultdict(list)
        for node_id, node in self.nodes.items():
            for req in node.requires:
                provider = capability_provider.get(req)
                if provider and provider != node_id:
                    deps[node_id].append(provider)

        return dict(deps)

    def _topological_sort(self, deps: dict[str, list[str]]) -> list[list[str]]:
        """
        Kahn's algorithm topological sort.
        Returns layers where all nodes in a layer can run in parallel.
        Raises ValueError if a cycle is detected.
        """
        all_nodes = set(self.nodes.keys())
        in_degree: dict[str, int] = {n: 0 for n in all_nodes}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for node_id, dep_list in deps.items():
            for dep in dep_list:
                adjacency[dep].append(node_id)
                in_degree[node_id] += 1

        # Start with nodes that have no dependencies
        queue = deque([n for n in all_nodes if in_degree[n] == 0])
        layers: list[list[str]] = []
        processed = 0

        while queue:
            layer = list(queue)
            queue.clear()
            layers.append(layer)

            next_layer_candidates: dict[str, int] = {}
            for node_id in layer:
                processed += 1
                for dependent in adjacency[node_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_layer_candidates[dependent] = 1

            for node_id in next_layer_candidates:
                queue.append(node_id)

        if processed != len(all_nodes):
            raise ValueError("Cycle detected in agent dependency graph")

        return layers

    async def _execute_node(self, node: AgentNode, context: dict) -> None:
        """Execute a single node with timeout and retry logic."""
        node.status = NodeStatus.RUNNING
        node.start_time = time.time()

        for attempt in range(node.max_retries + 1):
            try:
                async with self._semaphore:
                    if node.execute_fn:
                        result = await asyncio.wait_for(
                            node.execute_fn(context),
                            timeout=node.timeout_s,
                        )
                        node.result = result or {}
                    else:
                        node.result = {"status": "no_execute_fn", "node_id": node.node_id}

                node.status = NodeStatus.SUCCESS
                node.end_time = time.time()
                logger.info(f"✅ [{node.node_id}] {node.name} — SUCCESS ({node.duration_ms:.0f}ms)")
                return

            except asyncio.TimeoutError:
                node.retry_count = attempt + 1
                node.error = f"Timeout after {node.timeout_s}s"
                logger.warning(f"⏱ [{node.node_id}] Timeout on attempt {attempt + 1}")

            except Exception as e:
                node.retry_count = attempt + 1
                node.error = str(e)
                logger.warning(f"❌ [{node.node_id}] Error on attempt {attempt + 1}: {e}")

            if attempt < node.max_retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        node.status = NodeStatus.FAILED
        node.end_time = time.time()
        logger.error(f"💀 [{node.node_id}] {node.name} — FAILED: {node.error}")

    def _reset_nodes(self) -> None:
        """Reset all node runtime state before a run."""
        for node in self.nodes.values():
            node.status = NodeStatus.PENDING
            node.result = {}
            node.error = None
            node.start_time = None
            node.end_time = None
            node.retry_count = 0

    def _available_caps(self) -> set:
        """Return the set of capabilities provided by all successful nodes so far."""
        caps: set = set()
        for n in self.nodes.values():
            if n.status == NodeStatus.SUCCESS:
                caps.update(n.provides)
        return caps

    def _filter_layer(self, layer_nodes: list, available_caps: set) -> list:
        """Skip nodes whose upstream capability requirements aren't met; return runnable nodes."""
        runnable = []
        for node in layer_nodes:
            missing = [cap for cap in node.requires if cap not in available_caps]
            if missing and node.requires:
                node.status = NodeStatus.SKIPPED
                node.error = f"Skipped: upstream provider failed for caps {missing}"
                logger.warning(f"⏭ [{node.node_id}] Skipped — missing upstream caps: {missing}")
            else:
                runnable.append(node)
        return runnable

    def _check_halt(self, layer_nodes: list) -> str:
        """Return a halt reason if any critical node failed, else empty string."""
        for node in layer_nodes:
            if node.status == NodeStatus.FAILED and node.critical:
                reason = f"Critical node [{node.node_id}] failed: {node.error}"
                logger.error(f"🛑 HALT: {reason}")
                return reason
        return ""

    def _update_context(self, layer_nodes: list, context: dict) -> None:
        """Merge successful node results into the shared context."""
        for node in layer_nodes:
            if node.status == NodeStatus.SUCCESS:
                context[f"result_{node.node_id}"] = node.result

    def _compile_result(
        self, run_id: str, started_at: str,
        wall_start: float, halted: bool, halt_reason: str,
    ) -> OrchestrationResult:
        """Build the final OrchestrationResult from node states."""
        succeeded = sum(1 for n in self.nodes.values() if n.status == NodeStatus.SUCCESS)
        failed = sum(1 for n in self.nodes.values() if n.status == NodeStatus.FAILED)
        skipped = sum(1 for n in self.nodes.values() if n.status == NodeStatus.SKIPPED)
        return OrchestrationResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            total_nodes=len(self.nodes),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            total_duration_ms=(time.time() - wall_start) * 1000,
            node_results={
                nid: {
                    "status": n.status.value,
                    "duration_ms": n.duration_ms,
                    "error": n.error,
                    "retry_count": n.retry_count,
                    "result_keys": list(n.result.keys()) if n.result else [],
                }
                for nid, n in self.nodes.items()
            },
            halted_early=halted,
            halt_reason=halt_reason,
        )

    async def run(self, context: dict = None) -> OrchestrationResult:
        """
        Execute the full DAG.
        Runs nodes layer by layer; within each layer, nodes run in parallel.
        """
        run_id = f"dag_{int(time.time())}"
        started_at = datetime.now(timezone.utc).isoformat()
        context = context or {}
        self._semaphore = asyncio.Semaphore(self.max_parallelism)
        logger.info(f"🚀 DAG Orchestration [{run_id}] — {len(self.nodes)} nodes")

        self._reset_nodes()

        try:
            deps = self._build_dependency_edges()
            layers = self._topological_sort(deps)
        except ValueError as e:
            return OrchestrationResult(
                run_id=run_id, started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                total_nodes=len(self.nodes), succeeded=0, failed=0,
                skipped=len(self.nodes), total_duration_ms=0,
                halted_early=True, halt_reason=str(e),
            )

        halted = False
        halt_reason = ""
        wall_start = time.time()

        for layer_idx, layer in enumerate(layers):
            if halted:
                for node_id in layer:
                    self.nodes[node_id].status = NodeStatus.SKIPPED
                continue

            layer_nodes = sorted(
                [self.nodes[nid] for nid in layer], key=lambda n: n.priority
            )
            logger.info(f"⚡ Layer {layer_idx + 1}/{len(layers)}: {[n.node_id for n in layer_nodes]}")

            nodes_to_run = self._filter_layer(layer_nodes, self._available_caps())
            await asyncio.gather(
                *[self._execute_node(n, context) for n in nodes_to_run],
                return_exceptions=True,
            )

            halt_reason = self._check_halt(layer_nodes)
            if halt_reason:
                halted = True
            self._update_context(layer_nodes, context)

        return self._compile_result(run_id, started_at, wall_start, halted, halt_reason)

    def visualize(self) -> str:
        """Return a text representation of the DAG."""
        deps = self._build_dependency_edges()
        lines = ["RHNS DAG — Node Dependency Graph", "=" * 40]
        for node_id, node in self.nodes.items():
            dep_str = " → ".join(deps.get(node_id, ["(no deps)"]))
            lines.append(f"  [{node.priority}] {node_id}: {node.name}")
            lines.append(f"       deps: {dep_str}")
            lines.append(f"       provides: {node.provides}")
        return "\n".join(lines)
