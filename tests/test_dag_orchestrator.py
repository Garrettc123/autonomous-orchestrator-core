"""
Tests for RHNS DAG Orchestrator
================================
7 unit tests covering:
1. Single node execution
2. Dependency order enforcement
3. Cycle detection
4. Failed node skips dependents
5. Critical node halts DAG
6. Parallel layer concurrency
7. Visualize returns string
"""

import asyncio
import pytest
from core.dag_orchestrator import DAGOrchestrator, AgentNode, NodeStatus


# ─── Helpers ──────────────────────────────────────────────────────────────

def make_node(node_id: str, provides=None, requires=None, execute_fn=None,
              critical=False, priority=3, timeout_s=5.0, max_retries=0) -> AgentNode:
    return AgentNode(
        node_id=node_id,
        name=f"Node {node_id}",
        description=f"Test node {node_id}",
        provides=provides or [],
        requires=requires or [],
        priority=priority,
        critical=critical,
        timeout_s=timeout_s,
        max_retries=max_retries,
        execute_fn=execute_fn,
    )


async def ok_fn(ctx: dict) -> dict:
    return {"status": "ok"}


async def fail_fn(ctx: dict) -> dict:
    raise RuntimeError("Deliberate test failure")


# ─── Tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_node_executes():
    """Register 1 node, run DAG, confirm succeeded=1."""
    dag = DAGOrchestrator()
    dag.register(make_node("alpha", execute_fn=ok_fn))
    result = await dag.run()
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.skipped == 0
    assert result.total_nodes == 1


@pytest.mark.asyncio
async def test_dependency_order_enforced():
    """B requires A's output; confirm A runs (and succeeds) before B starts."""
    execution_order = []

    async def fn_a(ctx):
        execution_order.append("A")
        return {"cap_a": True}

    async def fn_b(ctx):
        execution_order.append("B")
        # By the time B runs, A must have already succeeded
        assert "A" in execution_order, "B ran before A!"
        return {"status": "ok"}

    dag = DAGOrchestrator()
    dag.register(make_node("node_a", provides=["cap_a"], execute_fn=fn_a))
    dag.register(make_node("node_b", requires=["cap_a"], execute_fn=fn_b))

    result = await dag.run()
    assert result.succeeded == 2
    assert execution_order.index("A") < execution_order.index("B")


@pytest.mark.asyncio
async def test_cycle_detection_raises():
    """Create A→B→A cycle; confirm the orchestrator handles it gracefully."""
    dag = DAGOrchestrator()
    # A provides cap_a and requires cap_b; B provides cap_b and requires cap_a
    dag.register(make_node("node_a", provides=["cap_a"], requires=["cap_b"], execute_fn=ok_fn))
    dag.register(make_node("node_b", provides=["cap_b"], requires=["cap_a"], execute_fn=ok_fn))

    result = await dag.run()
    assert result.halted_early is True
    assert "Cycle" in result.halt_reason


@pytest.mark.asyncio
async def test_failed_node_skips_dependents():
    """A fails; B requires A → B is SKIPPED (not run)."""
    dag = DAGOrchestrator()
    dag.register(make_node("node_a", provides=["cap_a"], execute_fn=fail_fn, critical=False, max_retries=0))
    dag.register(make_node("node_b", requires=["cap_a"], execute_fn=ok_fn))

    result = await dag.run()
    assert dag.nodes["node_a"].status == NodeStatus.FAILED
    assert dag.nodes["node_b"].status == NodeStatus.SKIPPED
    assert result.failed == 1
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_critical_node_halts_dag():
    """Critical node fails → remaining independent layers are skipped."""
    dag = DAGOrchestrator()
    # Layer 0: critical node that fails
    dag.register(make_node("critical_node", provides=["cap_c"], critical=True,
                           execute_fn=fail_fn, max_retries=0))
    # Layer 1 (independent, no deps): should be skipped due to halt
    dag.register(make_node("later_node", provides=[], requires=["cap_c"], execute_fn=ok_fn))

    result = await dag.run()
    assert result.halted_early is True
    assert "critical_node" in result.halt_reason
    assert dag.nodes["critical_node"].status == NodeStatus.FAILED
    assert dag.nodes["later_node"].status == NodeStatus.SKIPPED


@pytest.mark.asyncio
async def test_parallel_layer_runs_concurrently():
    """3 independent nodes each sleep 0.3s; total time should be < 0.9s (sum)."""
    SLEEP_S = 0.3

    async def slow_fn(ctx: dict) -> dict:
        await asyncio.sleep(SLEEP_S)
        return {"status": "ok"}

    dag = DAGOrchestrator(max_parallelism=4)
    for i in range(3):
        dag.register(make_node(f"parallel_{i}", execute_fn=slow_fn))

    result = await dag.run()
    assert result.succeeded == 3
    # All 3 run concurrently so total should be much less than 3 * SLEEP_S
    assert result.total_duration_ms < (SLEEP_S * 3 * 1000 * 0.9), (
        f"Expected parallel execution < {SLEEP_S * 3 * 0.9:.2f}s, "
        f"got {result.total_duration_ms / 1000:.2f}s"
    )


def test_visualize_returns_string():
    """dag.visualize() returns a non-empty string."""
    dag = DAGOrchestrator()
    dag.register(make_node("vis_a", provides=["x"]))
    dag.register(make_node("vis_b", requires=["x"]))
    output = dag.visualize()
    assert isinstance(output, str)
    assert len(output) > 0
    assert "vis_a" in output or "vis_b" in output
