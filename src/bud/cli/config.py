"""Configuration CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console

from bud._config import (
    CONFIG_FILE,
    BudConfig,
    get_config_value,
    set_config_value,
)

app = typer.Typer(help="Configuration management.")
console = Console()


@app.command("get")
def get(
    key: str = typer.Argument(..., help="Configuration key"),
) -> None:
    """Get a configuration value.

    Example:
        bud config get api_url
    """
    value = get_config_value(key)

    if value is None:
        console.print(f"[dim]No value set for '{key}'[/dim]")
    else:
        # Mask sensitive values
        if key == "api_key" and value:
            value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
        console.print(value)


@app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
) -> None:
    """Set a configuration value.

    Example:
        bud config set api_url https://api.custom.bud.io
        bud config set timeout 120
    """
    # Convert value types
    if value.lower() in ("true", "false"):
        typed_value: str | bool | int | float = value.lower() == "true"
    elif value.isdigit():
        typed_value = int(value)
    elif value.replace(".", "", 1).isdigit():
        typed_value = float(value)
    else:
        typed_value = value

    set_config_value(key, typed_value)
    console.print(f"[green]Set {key} = {value}[/green]")


@app.command("list")
def list_config() -> None:
    """List all configuration values."""
    config = BudConfig.load()

    console.print("[bold]Current Configuration[/bold]\n")

    # Core settings
    console.print("  api_key:", end=" ")
    if config.api_key:
        masked = (
            config.api_key[:8] + "..." + config.api_key[-4:] if len(config.api_key) > 12 else "***"
        )
        console.print(masked)
    else:
        console.print("[dim]not set[/dim]")

    console.print(f"  api_url: {config.base_url}")
    console.print(f"  timeout: {config.timeout}")
    console.print(f"  max_retries: {config.max_retries}")
    console.print(f"  environment: {config.environment}")
    console.print(f"  debug: {config.debug}")
    console.print(f"  verify_ssl: {config.verify_ssl}")

    console.print(f"\n[dim]Config file: {CONFIG_FILE}[/dim]")


@app.command("path")
def show_path() -> None:
    """Show configuration file path."""
    console.print(str(CONFIG_FILE))


@app.command("edit")
def edit() -> None:
    """Open configuration file in editor."""
    import os
    import subprocess

    editor = os.environ.get("EDITOR", "vim")

    if not CONFIG_FILE.exists():
        # Create default config
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            "# BudAI SDK Configuration\n"
            "# See: https://docs.budecosystem.com/sdk/configuration\n\n"
            '# api_key = "your-api-key"\n'
            '# api_url = "https://api.bud.io"\n'
            "# timeout = 60\n"
            "# max_retries = 3\n"
        )

    try:
        subprocess.run([editor, str(CONFIG_FILE)])
    except FileNotFoundError:
        console.print(f"[red]Editor not found: {editor}[/red]")
        console.print("Set EDITOR environment variable or edit manually:")
        console.print(f"  {CONFIG_FILE}")
        raise typer.Exit(1)
