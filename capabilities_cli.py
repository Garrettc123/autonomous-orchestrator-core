#!/usr/bin/env python3
"""
CAPABILITIES CLI - Unprecedented Capabilities Management Tool
=============================================================
Command-line interface for managing and monitoring unprecedented capabilities.

Usage:
    python3 capabilities_cli.py list              # List all capabilities
    python3 capabilities_cli.py status            # Show status report
    python3 capabilities_cli.py sync              # Run synchronization
    python3 capabilities_cli.py monitor           # Continuous monitoring
"""

import sys
import asyncio
import json
from core.capabilities_registry import UnprecedentedCapabilitiesRegistry, CapabilityStatus
from core.capability_sync import CapabilitySyncEngine


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def cmd_list(registry):
    """List all capabilities"""
    print_header("🌈 UNPRECEDENTED CAPABILITIES LIST")

    capabilities = registry.list_all_capabilities()

    for cap in capabilities:
        status_icon = "✅" if cap['status'] == 'active' else "🔄"
        print(f"\n{status_icon} {cap['name']}")
        print(f"   ID: {cap['id']}")
        print(f"   Category: {cap['category']}")
        print(f"   Status: {cap['status']}")
        print(f"   Harmony Impact: {cap['harmony_impact']:.2f}")
        print(f"   Prosperity Multiplier: {cap['prosperity_multiplier']:.2f}x")

        if cap['dependencies']:
            print(f"   Dependencies: {', '.join(cap['dependencies'])}")
        if cap['systems_required']:
            print(f"   Systems: {', '.join(cap['systems_required'])}")


def cmd_status(registry):
    """Show status report"""
    print_header("📊 UNPRECEDENTED CAPABILITIES STATUS REPORT")

    report = registry.get_status_report()

    print(f"\n📈 Overall Metrics:")
    print(f"   Total Capabilities: {report['total_capabilities']}")
    print(f"   Active Capabilities: {report['active_capabilities']}")
    print(f"   Deployment Rate: {report['deployment_rate'] * 100:.1f}%")
    print(f"   Total Harmony Impact: {report['total_harmony_impact']:.3f}")
    print(f"   Total Prosperity Multiplier: {report['total_prosperity_multiplier']:.2f}x")
    print(f"   🌟 Unprecedented Score: {report['unprecedented_score']:.2f}")

    print(f"\n📊 Capabilities by Category:")
    for category, count in report['categories'].items():
        print(f"   • {category}: {count}")

    # JSON output option
    print(f"\n💾 JSON Output:")
    print(json.dumps(report, indent=2))


async def cmd_sync(registry):
    """Run synchronization"""
    print_header("🔄 UNPRECEDENTED CAPABILITIES SYNCHRONIZATION")

    sync_engine = CapabilitySyncEngine(registry)
    await sync_engine.initialize()
    await sync_engine.synchronize_all()

    print("\n✅ Synchronization complete!")

    status = sync_engine.get_sync_status()
    print(f"\n📊 Sync Status:")
    print(f"   Active: {status['active_capabilities']}/{status['total_capabilities']}")
    print(f"   Harmony Score: {status['harmony_score']:.3f}")
    print(f"   Prosperity Flow: {status['prosperity_flow']:.2f}x")
    print(f"   Synchronized: {'✅ YES' if status['synchronized'] else '⚠️  IN PROGRESS'}")


async def cmd_monitor(registry):
    """Continuous monitoring"""
    print_header("👁️  CONTINUOUS CAPABILITY MONITORING")
    print("Press Ctrl+C to stop\n")

    sync_engine = CapabilitySyncEngine(registry)
    await sync_engine.initialize()

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n🔄 Monitoring Cycle #{cycle}")
            print("-" * 60)

            status = sync_engine.get_sync_status()

            # Get active capabilities
            active_caps = registry.get_active_capabilities()

            print(f"Active Capabilities: {len(active_caps)}/{len(registry.capabilities)}")
            print(f"Harmony Score: {status['harmony_score']:.3f}")
            print(f"Prosperity Flow: {status['prosperity_flow']:.2f}x")

            # Show category breakdown
            for cat_name, count in registry.get_status_report()['categories'].items():
                print(f"  • {cat_name}: {count}")

            await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped by user")


def print_usage():
    """Print usage information"""
    print(__doc__)


def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    # Initialize registry
    registry = UnprecedentedCapabilitiesRegistry()

    # Route to command
    if command == "list":
        cmd_list(registry)
    elif command == "status":
        cmd_status(registry)
    elif command == "sync":
        asyncio.run(cmd_sync(registry))
    elif command == "monitor":
        asyncio.run(cmd_monitor(registry))
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
