"""Configuration management for BudAI SDK.

Supports:
- Environment variables (BUD_API_KEY, BUD_API_URL, etc.)
- Config file (~/.bud/config.toml)
- Programmatic configuration
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


DEFAULT_BASE_URL = "https://api.bud.io"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 3

CONFIG_DIR = Path.home() / ".bud"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class AuthConfig:
    """Authentication configuration from config file."""

    type: str | None = None  # "api_key", "dapr", or "jwt"
    api_key: str | None = None
    dapr_token: str | None = None
    user_id: str | None = None
    email: str | None = None
    password: str | None = None


@dataclass
class BudConfig:
    """SDK configuration."""

    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    environment: str = "production"

    # Additional settings
    debug: bool = False
    verify_ssl: bool = True

    # Auth configuration (from [auth] section)
    auth: AuthConfig = field(default_factory=AuthConfig)

    @classmethod
    def from_env(cls) -> BudConfig:
        """Load configuration from environment variables."""
        return cls(
            api_key=os.getenv("BUD_API_KEY"),
            base_url=os.getenv("BUD_API_URL", DEFAULT_BASE_URL),
            timeout=float(os.getenv("BUD_TIMEOUT", DEFAULT_TIMEOUT)),
            max_retries=int(os.getenv("BUD_MAX_RETRIES", DEFAULT_MAX_RETRIES)),
            environment=os.getenv("BUD_ENVIRONMENT", "production"),
            debug=os.getenv("BUD_DEBUG", "").lower() in ("1", "true", "yes"),
            verify_ssl=os.getenv("BUD_VERIFY_SSL", "true").lower() not in ("0", "false", "no"),
        )

    @classmethod
    def from_file(cls, path: Path | None = None) -> BudConfig:
        """Load configuration from TOML file."""
        config_path = path or CONFIG_FILE

        if not config_path.exists():
            return cls()

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Parse auth section if present
        auth_data = data.get("auth", {})
        auth_config = AuthConfig(
            type=auth_data.get("type"),
            api_key=auth_data.get("api_key"),
            dapr_token=auth_data.get("token"),
            user_id=auth_data.get("user_id"),
            email=auth_data.get("email"),
            password=auth_data.get("password"),
        )

        return cls(
            api_key=data.get("api_key"),
            base_url=data.get("api_url", DEFAULT_BASE_URL),
            timeout=float(data.get("timeout", DEFAULT_TIMEOUT)),
            max_retries=int(data.get("max_retries", DEFAULT_MAX_RETRIES)),
            environment=data.get("environment", "production"),
            debug=data.get("debug", False),
            verify_ssl=data.get("verify_ssl", True),
            auth=auth_config,
        )

    @classmethod
    def load(cls) -> BudConfig:
        """Load configuration with precedence: env > file > defaults."""
        # Start with file config
        config = cls.from_file()

        # Override with environment variables
        env_config = cls.from_env()

        if env_config.api_key:
            config.api_key = env_config.api_key
        if os.getenv("BUD_API_URL"):
            config.base_url = env_config.base_url
        if os.getenv("BUD_TIMEOUT"):
            config.timeout = env_config.timeout
        if os.getenv("BUD_MAX_RETRIES"):
            config.max_retries = env_config.max_retries
        if os.getenv("BUD_ENVIRONMENT"):
            config.environment = env_config.environment
        if os.getenv("BUD_DEBUG"):
            config.debug = env_config.debug
        if os.getenv("BUD_VERIFY_SSL"):
            config.verify_ssl = env_config.verify_ssl

        return config


def get_config_dir() -> Path:
    """Get or create the config directory."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    """Save configuration to TOML file.

    Sets restrictive file permissions (0o600) since config may contain
    sensitive credentials like API keys.
    """
    import tomli_w

    config_path = path or CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)

    # Set restrictive permissions for security (may contain API keys)
    config_path.chmod(0o600)


def get_config_value(key: str) -> Any:
    """Get a single config value."""
    config = BudConfig.load()
    # Map config file keys to object attributes
    key_mapping = {
        "api_url": "base_url",
    }
    attr_name = key_mapping.get(key, key)
    return getattr(config, attr_name, None)


def set_config_value(key: str, value: Any) -> None:
    """Set a single config value in the config file."""
    config_path = CONFIG_FILE

    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    else:
        data = {}

    data[key] = value
    save_config(data, config_path)
