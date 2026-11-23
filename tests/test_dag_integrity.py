"""Regression tests for RHNS graph and ambiguous execution integrity."""
import asyncio

import pytest

from core.dag_orchestrator import AgentNode, DAGOrchestrator, NodeStatus


async def completed(_):
    return {"status": "completed"}


def node(name, provides=None, requires=None, fn=completed):
    return AgentNode(
        node_id=name, name=name, description=name,
        provides=provides or [], requires=requires or [],
        execute_fn=fn, max_retries=2,
    )


def test_duplicate_node_rejected():
    dag = DAGOrchestrator()
    dag.register(node("same"))
    with pytest.raises(ValueError, match="Duplicate node"):
        dag.register(node("same"))


@pytest.mark.asyncio
async def test_missing_provider_fails_closed():
    dag = DAGOrchestrator()
    dag.register(node("buyer", requires=["unavailable"]))
    result = await dag.run()
    assert result.halted_early
    assert "Missing capability provider" in result.halt_reason
    assert result.succeeded == 0


@pytest.mark.asyncio
async def test_duplicate_provider_fails_closed():
    dag = DAGOrchestrator()
    dag.register(node("a", provides=["shared"]))
    dag.register(node("b", provides=["shared"]))
    result = await dag.run()
    assert result.halted_early
    assert "Duplicate capability provider" in result.halt_reason


@pytest.mark.asyncio
async def test_self_dependency_fails_closed():
    dag = DAGOrchestrator()
    dag.register(node("a", provides=["self"], requires=["self"]))
    result = await dag.run()
    assert result.halted_early
    assert "Self-dependent" in result.halt_reason


@pytest.mark.asyncio
async def test_timeout_never_retries_and_blocks_downstream():
    attempts = []

    async def unknown_outcome(_):
        attempts.append(1)
        await asyncio.sleep(0.03)
        return {"status": "completed"}

    dag = DAGOrchestrator()
    first = node("first", provides=["proof"], fn=unknown_outcome)
    first.timeout_s = 0.001
    first.critical = True
    dag.register(first)
    dag.register(node("second", requires=["proof"]))
    result = await dag.run()
    assert len(attempts) == 1
    assert result.unverified == 1
    assert result.halted_early
    assert dag.nodes["first"].status == NodeStatus.UNVERIFIED
    assert dag.nodes["second"].status == NodeStatus.SKIPPED
