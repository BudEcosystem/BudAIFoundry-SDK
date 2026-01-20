"""CLI utilities."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from bud.client import BudClient
from bud.exceptions import AuthenticationError, BudError

console = Console()
error_console = Console(stderr=True)


def get_client() -> BudClient:
    """Get an authenticated BudClient.

    Checks for stored JWT tokens from `bud auth login` and uses them
    if available. Falls back to environment variables and config file.
    """
    from bud._config import BudConfig
    from bud.auth import JWTAuth
    from bud.cli.auth import load_tokens

    try:
        # Check for stored JWT tokens first
        tokens = load_tokens()
        if tokens and tokens.get("access_token"):
            config = BudConfig.load()
            # Create JWTAuth with stored tokens
            auth = JWTAuth(
                email=config.auth.email if config.auth else "",
                password="",  # Not needed when tokens are available
            )
            auth._access_token = tokens["access_token"]
            auth._refresh_token = tokens.get("refresh_token")
            auth._expires_at = tokens.get("expires_at", 0)
            return BudClient(auth=auth, base_url=config.base_url)

        # Fall back to normal auth resolution
        return BudClient()
    except AuthenticationError as e:
        error_console.print(f"[red]Authentication error:[/red] {e}")
        error_console.print("\nTo authenticate, run:")
        error_console.print("  bud auth login")
        raise typer.Exit(1) from None


def output_json(data: Any) -> None:
    """Output data as JSON."""
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
        data = [item.model_dump(mode="json") for item in data]

    console.print_json(json.dumps(data, default=str))


def output_table(
    data: list[Any],
    columns: list[tuple[str, str]],
    title: str | None = None,
) -> None:
    """Output data as a Rich table.

    Args:
        data: List of objects
        columns: List of (field_name, header) tuples
        title: Optional table title
    """
    table = Table(title=title, show_header=True, header_style="bold")

    for _, header in columns:
        table.add_column(header)

    for item in data:
        row = []
        for field, _ in columns:
            if hasattr(item, field):
                value = getattr(item, field)
            elif isinstance(item, dict):
                value = item.get(field, "")
            else:
                value = ""

            # Format special types
            if value is None:
                value = "-"
            elif isinstance(value, bool):
                value = "Yes" if value else "No"
            elif hasattr(value, "isoformat"):
                value = value.strftime("%Y-%m-%d %H:%M:%S")

            row.append(str(value))

        table.add_row(*row)

    console.print(table)


def handle_error(e: Exception) -> None:
    """Handle and display an error."""
    if isinstance(e, BudError):
        error_console.print(f"[red]Error:[/red] {e.message}")
    else:
        error_console.print(f"[red]Error:[/red] {e}")

    raise typer.Exit(1)


def confirm_action(message: str, default: bool = False) -> bool:
    """Prompt user for confirmation."""
    return typer.confirm(message, default=default)


def get_json_flag(ctx: typer.Context) -> bool:
    """Get JSON output flag from context."""
    return ctx.obj.get("json", False) if ctx.obj else False
