"""Tests for the OneKeySystem security module."""

import pytest
from security.one_key import OneKeySystem


class TestOneKeySystemInit:
    def test_init_with_valid_seed(self):
        key = OneKeySystem("my_secret_seed_123")
        assert key is not None

    def test_init_empty_seed_raises(self):
        with pytest.raises(ValueError, match="One Key missing"):
            OneKeySystem("")

    def test_init_none_seed_raises(self):
        with pytest.raises((ValueError, AttributeError)):
            OneKeySystem(None)  # type: ignore[arg-type]

    def test_cache_starts_empty(self):
        key = OneKeySystem("seed")
        assert key._cache == {}


class TestOneKeySystemDerive:
    def setup_method(self):
        self.key = OneKeySystem("test_master_seed_for_unit_tests")

    def test_get_credential_returns_string(self):
        cred = self.key.get_credential("DOMAIN", "SERVICE")
        assert isinstance(cred, str)

    def test_get_credential_is_deterministic(self):
        cred1 = self.key.get_credential("AI_OPS", "GITHUB_TOKEN")
        cred2 = self.key.get_credential("AI_OPS", "GITHUB_TOKEN")
        assert cred1 == cred2

    def test_get_credential_different_domains_differ(self):
        cred1 = self.key.get_credential("DOMAIN_A", "SERVICE")
        cred2 = self.key.get_credential("DOMAIN_B", "SERVICE")
        assert cred1 != cred2

    def test_get_credential_different_services_differ(self):
        cred1 = self.key.get_credential("DOMAIN", "SERVICE_A")
        cred2 = self.key.get_credential("DOMAIN", "SERVICE_B")
        assert cred1 != cred2

    def test_get_credential_is_cached(self):
        _ = self.key.get_credential("DOMAIN", "SERVICE")
        assert "DOMAIN:SERVICE" in self.key._cache

    def test_different_master_seeds_give_different_credentials(self):
        key_a = OneKeySystem("seed_a")
        key_b = OneKeySystem("seed_b")
        assert key_a.get_credential("D", "S") != key_b.get_credential("D", "S")

    def test_get_credential_hex_format(self):
        cred = self.key.get_credential("TEST", "KEY")
        # HKDF output should be a hex string (from hexdigest)
        int(cred, 16)  # raises ValueError if not valid hex


class TestOneKeySystemLock:
    def test_lock_clears_cache(self):
        key = OneKeySystem("seed")
        _ = key.get_credential("D", "S")
        assert len(key._cache) > 0
        key.lock()
        assert key._cache == {}

    def test_lock_zeroes_master(self, capsys):
        key = OneKeySystem("seed")
        key.lock()
        assert key._master == b"\x00" * 32
        captured = capsys.readouterr()
        assert "LOCKED" in captured.out
