"""
Configuration management for helpdesk service.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """
    Configuration manager with support for environment variables and config files.
    
    BUG: Config precedence inconsistency - environment variables override file config
    in some methods but not others. The load_from_file method doesn't respect
    existing env vars, and get() method checks env first but set() only updates
    internal dict, not env vars.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize config manager."""
        self.config_file = config_file
        self._config: Dict[str, Any] = {}
        self._load_defaults()
        
        if config_file and Path(config_file).exists():
            self.load_from_file(config_file)
        
        # BUG: Environment variables should override file config, but this
        # only happens in get(), not during initialization
        self._load_from_env()
    
    def _load_defaults(self) -> None:
        """Load default configuration values."""
        self._config = {
            "store_type": "memory",
            "store_path": "./data",
            "cache_enabled": True,
            "cache_ttl": 3600,
            "escalation_threshold_hours": 24,
            "auto_escalate_critical": True,
            "max_ticket_title_length": 200,
            "max_ticket_description_length": 10000,
            "default_priority": "medium",
            "log_level": "INFO",
        }
    
    def load_from_file(self, config_file: str) -> None:
        """Load configuration from JSON file."""
        path = Path(config_file)
        if not path.exists():
            return
        
        try:
            with open(path, "r") as f:
                file_config = json.load(f)
            
            # BUG: This overwrites everything, including values that might
            # have been set via environment variables
            self._config.update(file_config)
        except Exception:
            pass
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        env_mapping = {
            "HELPDESK_STORE_TYPE": "store_type",
            "HELPDESK_STORE_PATH": "store_path",
            "HELPDESK_CACHE_ENABLED": "cache_enabled",
            "HELPDESK_CACHE_TTL": "cache_ttl",
            "HELPDESK_ESCALATION_THRESHOLD": "escalation_threshold_hours",
            "HELPDESK_LOG_LEVEL": "log_level",
        }
        
        for env_var, config_key in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                # BUG: Type conversion is inconsistent - some values are strings,
                # some are converted, but not all env vars are handled
                if config_key in ["cache_enabled", "auto_escalate_critical"]:
                    self._config[config_key] = value.lower() in ["true", "1", "yes"]
                elif config_key in ["cache_ttl", "escalation_threshold_hours", "max_ticket_title_length"]:
                    try:
                        self._config[config_key] = int(value)
                    except ValueError:
                        pass
                else:
                    self._config[config_key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        BUG: Checks env var first, but if env var exists, it returns string
        even if the config file had a different type. Type consistency is broken.
        """
        # BUG: Environment variable check happens here, but env vars might
        # have different types than config file values
        env_key = f"HELPDESK_{key.upper()}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return env_value
        
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        # BUG: This only updates internal dict, doesn't update env vars
        # So subsequent get() calls might return env var instead
        self._config[key] = value
    
    def save_to_file(self, config_file: Optional[str] = None) -> None:
        """Save configuration to file."""
        file_path = config_file or self.config_file
        if not file_path:
            return
        
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(self._config, f, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return self._config.copy()

