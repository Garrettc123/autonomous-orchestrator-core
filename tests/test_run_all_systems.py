"""Tests for the UnifiedEcosystem runner (run_all_systems module)."""

import asyncio
import pytest
from unittest.mock import patch
from run_all_systems import UnifiedEcosystem


class TestUnifiedEcosystemInit:
    def test_init_defaults(self):
        eco = UnifiedEcosystem()
        assert eco.total_systems == 332
        assert eco.active_systems == []
        assert eco.prosperity_flow == 0.0
        assert eco.harmony_score == 0.0


class TestDiscoverSystems:
    @pytest.mark.asyncio
    async def test_discover_returns_list(self):
        eco = UnifiedEcosystem()
        systems = await eco.discover_systems()
        assert isinstance(systems, list)
        assert len(systems) > 0

    @pytest.mark.asyncio
    async def test_discover_returns_strings(self):
        eco = UnifiedEcosystem()
        systems = await eco.discover_systems()
        for s in systems:
            assert isinstance(s, str)

    @pytest.mark.asyncio
    async def test_discover_includes_this_repo(self):
        eco = UnifiedEcosystem()
        systems = await eco.discover_systems()
        assert "autonomous-orchestrator-core" in systems


class TestRunSystem:
    @pytest.mark.asyncio
    async def test_run_system_increments_prosperity(self):
        eco = UnifiedEcosystem()
        initial = eco.prosperity_flow

        # Run one iteration then cancel the infinite loop
        task = asyncio.create_task(eco.run_system("test-system"))
        await asyncio.sleep(0.01)  # Let it run briefly
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert eco.prosperity_flow > initial

    @pytest.mark.asyncio
    async def test_run_system_increases_harmony(self):
        eco = UnifiedEcosystem()
        initial = eco.harmony_score

        task = asyncio.create_task(eco.run_system("test-system"))
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert eco.harmony_score >= initial

    @pytest.mark.asyncio
    async def test_harmony_capped_at_0_99(self):
        eco = UnifiedEcosystem()
        eco.harmony_score = 0.99

        task = asyncio.create_task(eco.run_system("test-system"))
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert eco.harmony_score <= 0.99


class TestMonitorProsperity:
    @pytest.mark.asyncio
    async def test_monitor_runs_without_error(self):
        eco = UnifiedEcosystem()

        task = asyncio.create_task(eco.monitor_prosperity())
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Should complete without raising


class TestActivateAll:
    @pytest.mark.asyncio
    async def test_activate_all_starts_tasks(self):
        eco = UnifiedEcosystem()
        run_system_calls = []

        async def fake_run_system(system_id):
            run_system_calls.append(system_id)
            await asyncio.sleep(0)

        monitor_called = []

        async def fake_monitor():
            monitor_called.append(True)
            await asyncio.sleep(0)

        with patch.object(eco, "run_system", side_effect=fake_run_system):
            with patch.object(eco, "monitor_prosperity", side_effect=fake_monitor):
                await eco.activate_all()

        # Verify run_system was called for each of the first 10 discovered systems
        assert len(run_system_calls) == 10
        # Verify monitor_prosperity was called once
        assert len(monitor_called) == 1
