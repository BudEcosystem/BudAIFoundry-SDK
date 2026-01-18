"""Tests for CLI auth commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from bud.cli.auth import app, clear_tokens, load_tokens, save_tokens

runner = CliRunner()


class TestCLIAuthTokenFunctions:
    """Test CLI auth token helper functions."""

    def test_save_and_load_tokens(self, tmp_path: Path) -> None:
        """Token save and load should work correctly."""
        tokens_file = tmp_path / "tokens.json"

        with patch("bud.cli.auth.TOKENS_FILE", tokens_file):
            with patch("bud.cli.auth.get_config_dir", return_value=tmp_path):
                save_tokens("access-123", "refresh-456", 3600)

                tokens = load_tokens()

                assert tokens is not None
                assert tokens["access_token"] == "access-123"
                assert tokens["refresh_token"] == "refresh-456"
                assert "expires_at" in tokens

    def test_clear_tokens(self, tmp_path: Path) -> None:
        """Clear tokens should empty the tokens file."""
        tokens_file = tmp_path / "tokens.json"
        tokens_file.write_text(json.dumps({"access_token": "old"}))

        with patch("bud.cli.auth.TOKENS_FILE", tokens_file):
            clear_tokens()

            content = json.loads(tokens_file.read_text())
            assert content == {}

    def test_load_tokens_nonexistent(self, tmp_path: Path) -> None:
        """Load tokens should return None for nonexistent file."""
        tokens_file = tmp_path / "nonexistent.json"

        with patch("bud.cli.auth.TOKENS_FILE", tokens_file):
            tokens = load_tokens()
            assert tokens is None


class TestCLIAuthStatus:
    """Test CLI auth status command."""

    def test_cli_auth_status_shows_authenticated(self, tmp_path: Path) -> None:
        """CLI status should show authenticated when logged in."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('api_key = "test-api-key-12345"\n')

        with (
            patch("bud.cli.auth.CONFIG_FILE", config_file),
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "authenticated" in result.output.lower()

    def test_cli_auth_status_shows_not_authenticated(self, tmp_path: Path) -> None:
        """CLI status should show not authenticated when not logged in."""
        config_file = tmp_path / "nonexistent.toml"
        tokens_file = tmp_path / "tokens.json"

        with (
            patch("bud.cli.auth.CONFIG_FILE", config_file),
            patch("bud.cli.auth.TOKENS_FILE", tokens_file),
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "not authenticated" in result.output.lower()

    def test_cli_auth_status_shows_jwt_authenticated(self, tmp_path: Path) -> None:
        """CLI status should show JWT authenticated when tokens exist."""
        import time

        config_file = tmp_path / "config.toml"
        tokens_file = tmp_path / "tokens.json"

        # Create tokens file with valid token
        tokens_file.write_text(
            json.dumps(
                {
                    "access_token": "jwt-token",
                    "refresh_token": "refresh",
                    "expires_at": time.time() + 3600,
                }
            )
        )

        with (
            patch("bud.cli.auth.CONFIG_FILE", config_file),
            patch("bud.cli.auth.TOKENS_FILE", tokens_file),
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "authenticated" in result.output.lower()
            assert "jwt" in result.output.lower()


class TestCLIAuthLogout:
    """Test CLI auth logout command."""

    def test_cli_auth_logout_not_logged_in(self, tmp_path: Path) -> None:
        """CLI logout should handle not logged in state."""
        config_file = tmp_path / "config.toml"
        tokens_file = tmp_path / "tokens.json"

        with (
            patch("bud.cli.auth.CONFIG_FILE", config_file),
            patch("bud.cli.auth.TOKENS_FILE", tokens_file),
        ):
            result = runner.invoke(app, ["logout"])

            assert result.exit_code == 0
            assert "not logged in" in result.output.lower()
