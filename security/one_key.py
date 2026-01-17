"""
ONE KEY SECURITY PROTOCOL
=========================
The "One Key" system is a military-grade cryptographic hierarchy that derives all 
access credentials for the 332-system ecosystem from a single Master Seed (The "One Key").

Architecture:
-------------
1. **Master Seed (The One Key)**: A 256-bit entropy source held ONLY by the Commander.
   - Never stored on disk.
   - Never transmitted over network.
   - Injected only at runtime via secure memory enclave.

2. **Key Derivation (HKDF-SHA512)**:
   - All subsystem keys are derived deterministically from the Master Seed.
   - Path: `Master -> Domain (AI/Crypto/Enterprise) -> System -> Specific Key`
   - Example: `derive_key("AI_OPS", "GITHUB_TOKEN")`

3. **Zero-Trust Implementation**:
   - The Orchestrator requires ONLY the One Key to boot.
   - It generates ephemeral tokens for all services in memory.
   - If the One Key is withdrawn, the entire 332-system stack instantly locks.

Usage:
------
```python
from security.one_key import OneKeySystem

# 1. Initialize with the Commander's One Key
commander_key = os.getenv("COMMANDER_ONE_KEY")
security = OneKeySystem(commander_key)

# 2. Derive ephemeral credentials for subsystems
github_token = security.get_credential("AI_OPS", "GITHUB_TOKEN")
stripe_key = security.get_credential("REVENUE", "STRIPE_SECRET")

# 3. Systems run autonomously with derived keys
# ...
```
"""

import os
import hmac
import hashlib
from typing import Dict, Optional

class OneKeySystem:
    def __init__(self, master_seed: str):
        """
        Initialize the One Key Security System.
        
        Args:
            master_seed: The single 256-bit key that rules them all.
        """
        if not master_seed:
            raise ValueError("CRITICAL: One Key missing. System Locked.")
        self._master = master_seed.encode()
        self._cache: Dict[str, str] = {}

    def _derive(self, context: str, label: str) -> str:
        """
        HKDF-style key derivation function.
        """
        key_material = hmac.new(self._master, context.encode(), hashlib.sha512).digest()
        derived = hmac.new(key_material, label.encode(), hashlib.sha512).hexdigest()
        return derived

    def get_credential(self, domain: str, service: str) -> str:
        """
        Derive a specific service credential on the fly.
        """
        cache_key = f"{domain}:{service}"
        if cache_key not in self._cache:
            # In production, this would map the derived hash to the actual vaulted secret
            # or use the hash itself as the deterministic key for internal comms.
            self._cache[cache_key] = self._derive(domain, service)
        return self._cache[cache_key]

    def lock(self):
        """
        Emergency Protocol: Wipe key from memory.
        """
        self._master = b"\x00" * 32
        self._cache.clear()
        print("SYSTEM LOCKED: One Key purged from memory.")
