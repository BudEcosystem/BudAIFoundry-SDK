"""Action CLI commands."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from bud.cli._utils import (
    get_client,
    get_json_flag,
    handle_error,
    output_json,
)

app = typer.Typer(help="Action management commands.")
console = Console()


@app.command("list")
def list_actions(
    ctx: typer.Context,
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category",
    ),
) -> None:
    """List available actions."""
    try:
        client = get_client()
        actions = client.actions.list()

        # Filter by category if specified
        if category:
            actions = [a for a in actions if a.category and category.lower() in a.category.lower()]

        if get_json_flag(ctx):
            output_json(actions)
        else:
            if not actions:
                console.print("[dim]No actions found.[/dim]")
                return

            table = Table(title="Available Actions", show_header=True, header_style="bold")
            table.add_column("Type")
            table.add_column("Name")
            table.add_column("Category")
            table.add_column("Description")

            for action in actions:
                table.add_row(
                    action.type,
                    action.name,
                    action.category or "-",
                    (action.description[:50] + "...") if action.description and len(action.description) > 50 else (action.description or "-"),
                )

            console.print(table)

    except Exception as e:
        handle_error(e)


@app.command("describe")
def describe(
    ctx: typer.Context,
    action_type: str = typer.Argument(..., help="Action type (e.g., 'llm_call', 'aggregate')"),
) -> None:
    """Show action details."""
    try:
        client = get_client()
        action = client.actions.get(action_type)

        if get_json_flag(ctx):
            output_json(action)
        else:
            console.print(f"[bold]{action.name}[/bold] ({action.type})")
            console.print(f"  Category: {action.category or '-'}")
            console.print(f"  Version: {action.version or '-'}")
            if action.description:
                console.print(f"  Description: {action.description}")

            if action.params:
                console.print("\n  [bold]Parameters:[/bold]")
                for param in action.params:
                    required = "[red]*[/red]" if param.required else ""
                    default = f" (default: {param.default})" if param.default is not None else ""
                    console.print(f"    {required}{param.name} [{param.type}]{default}")
                    if param.description:
                        console.print(f"      {param.description}")
                    if param.options:
                        options_str = ", ".join(o.get("value", str(o)) for o in param.options[:5])
                        if len(param.options) > 5:
                            options_str += f", ... ({len(param.options)} total)"
                        console.print(f"      Options: {options_str}")

    except Exception as e:
        handle_error(e)
