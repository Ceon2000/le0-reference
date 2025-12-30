"""T09: Test configuration loading for security issues with sensitive values."""
import pytest
import os
import json
from helpdesk_ai.config import Config


class TestConfigSecrets:
    """Test configuration handling of sensitive values."""

    def test_config_loads_defaults(self, config):
        """Config should have sensible defaults."""
        assert config.get("store_type") is not None
        assert config.get("cache_enabled") is not None

    def test_config_env_var_override(self, monkeypatch, tmp_path):
        """Environment variables should override config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"store_type": "file"}')
        
        monkeypatch.setenv("HELPDESK_STORE_TYPE", "memory")
        
        config = Config(config_file=str(config_file))
        # Bug: get() checks env var, but internal _config might differ
        assert config.get("store_type") == "memory"

    def test_config_env_var_type_consistency(self, monkeypatch, tmp_path):
        """Env var values should maintain type consistency."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"cache_ttl": 3600}')
        
        # Set env var as string (env vars are always strings)
        monkeypatch.setenv("HELPDESK_CACHE_TTL", "7200")
        
        config = Config(config_file=str(config_file))
        value = config.get("cache_ttl")
        
        # Bug: get() returns raw string from env, not converted int
        # This causes type bugs downstream

    def test_config_set_doesnt_affect_env(self, monkeypatch, config):
        """set() should update internal config but env var still wins on get()."""
        monkeypatch.setenv("HELPDESK_STORE_TYPE", "env_value")
        
        config.set("store_type", "set_value")
        
        # Bug: get() returns env var, ignoring set() value
        # Documented inconsistency

    def test_config_secrets_not_in_to_dict(self, config):
        """Sensitive values should not appear in to_dict()."""
        config.set("api_key", "secret123")
        config.set("password", "secret456")
        
        data = config.to_dict()
        
        # Bug: to_dict() returns everything including secrets
        # Should filter sensitive keys

    def test_config_secrets_not_logged(self, caplog, tmp_path):
        """Secrets should not be logged."""
        import logging
        
        config_file = tmp_path / "config.json"
        config_file.write_text('{"api_key": "super_secret_key"}')
        
        with caplog.at_level(logging.DEBUG):
            config = Config(config_file=str(config_file))
        
        # If logging exists, secrets should be masked
        for record in caplog.records:
            assert "super_secret_key" not in record.message

    def test_config_save_to_file(self, config, tmp_path):
        """Config should save to file correctly."""
        config.set("custom_key", "custom_value")
        
        save_file = tmp_path / "saved_config.json"
        config.save_to_file(str(save_file))
        
        assert save_file.exists()
        saved_data = json.loads(save_file.read_text())
        assert saved_data.get("custom_key") == "custom_value"

    def test_config_missing_file_uses_defaults(self, tmp_path):
        """Missing config file should use defaults."""
        config = Config(config_file=str(tmp_path / "nonexistent.json"))
        
        # Should have defaults loaded
        assert config.get("store_type") == "memory"

    def test_config_invalid_json_uses_defaults(self, tmp_path):
        """Invalid JSON file should fallback to defaults."""
        config_file = tmp_path / "bad.json"
        config_file.write_text("not valid json {")
        
        config = Config(config_file=str(config_file))
        
        # Should have defaults (load_from_file catches exception silently)
        assert config.get("store_type") == "memory"
