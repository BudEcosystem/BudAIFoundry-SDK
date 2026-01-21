"""Execution CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console

from bud.cli._utils import (
    get_client,
    get_json_flag,
    handle_error,
    output_json,
    output_table,
)

app = typer.Typer(help="Execution management commands.")
console = Console()


@app.command("list")
def list_executions(
    ctx: typer.Context,
    pipeline_id: str | None = typer.Option(
        None,
        "--pipeline",
        "-p",
        help="Filter by pipeline ID",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (pending, running, completed, failed, cancelled)",
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of results"),
) -> None:
    """List executions."""
    try:
        client = get_client()
        executions = client.executions.list(
            pipeline_id=pipeline_id,
            status=status,
            per_page=limit,
        )

        if get_json_flag(ctx):
            output_json(executions)
        else:
            if not executions:
                console.print("[dim]No executions found.[/dim]")
                return

            output_table(
                executions,
                columns=[
                    ("effective_id", "ID"),
                    ("effective_pipeline_name", "Pipeline"),
                    ("status", "Status"),
                    ("effective_duration_sec", "Duration (s)"),
                    ("created_at", "Created"),
                ],
                title="Executions",
            )

    except Exception as e:
        handle_error(e)


@app.command("describe")
def describe(
    ctx: typer.Context,
    execution_id: str = typer.Argument(..., help="Execution ID"),
) -> None:
    """Show execution details."""
    try:
        client = get_client()
        execution = client.executions.get(execution_id)

        if get_json_flag(ctx):
            output_json(execution)
        else:
            # Handle status as either Enum or string
            status_str = (
                execution.status.value
                if hasattr(execution.status, "value")
                else str(execution.status)
            )
            status_upper = status_str.upper()
            status_color = {
                "COMPLETED": "green",
                "FAILED": "red",
                "CANCELLED": "yellow",
                "RUNNING": "blue",
                "PENDING": "dim",
                "TIMED_OUT": "red",
            }.get(status_upper, "white")

            console.print(f"[bold]Execution: {execution.id}[/bold]")
            pipeline_name = execution.pipeline_name or "-"
            pipeline_id = execution.pipeline_id or "-"
            console.print(f"  Pipeline: {pipeline_name} ({pipeline_id})")
            console.print(f"  Status: [{status_color}]{status_str}[/{status_color}]")

            if execution.started_at:
                console.print(f"  Started: {execution.started_at}")
            if execution.completed_at:
                console.print(f"  Completed: {execution.completed_at}")
            if execution.duration_ms:
                console.print(f"  Duration: {execution.duration_ms / 1000:.2f}s")

            if execution.error:
                console.print(f"  [red]Error:[/red] {execution.error}")

            if execution.params:
                console.print("\n  Parameters:")
                for k, v in execution.params.items():
                    console.print(f"    {k}: {v}")

            if execution.steps:
                console.print("\n  Steps:")
                for step in execution.steps:
                    step_status = (
                        step.status.value if hasattr(step.status, "value") else str(step.status)
                    )
                    step_color = {
                        "completed": "green",
                        "failed": "red",
                        "running": "blue",
                        "pending": "dim",
                        "skipped": "yellow",
                    }.get(step_status.lower(), "white")
                    console.print(f"    - {step.name}: [{step_color}]{step_status}[/{step_color}]")

    except Exception as e:
        handle_error(e)


@app.command("cancel")
def cancel(
    execution_id: str = typer.Argument(..., help="Execution ID"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation",
    ),
) -> None:
    """Cancel a running execution."""
    try:
        client = get_client()

        if not force and not typer.confirm(f"Cancel execution {execution_id}?"):
            raise typer.Abort()

        execution = client.executions.cancel(execution_id)
        console.print(f"[yellow]Cancelled execution:[/yellow] {execution.id}")

    except typer.Abort:
        console.print("[dim]Cancelled.[/dim]")
    except Exception as e:
        handle_error(e)


@app.command("retry")
def retry(
    ctx: typer.Context,
    execution_id: str = typer.Argument(..., help="Execution ID"),
    wait: bool = typer.Option(
        False,
        "--wait",
        "-w",
        help="Wait for completion",
    ),
) -> None:
    """Retry a failed execution."""
    try:
        client = get_client()
        execution = client.executions.retry(execution_id)

        if wait and execution.id:
            console.print(f"[dim]Retrying execution... ({execution.id})[/dim]")
            execution = client.executions.get(execution.id)
            # Wait loop would go here

        if get_json_flag(ctx):
            output_json(execution)
        else:
            console.print(f"[green]Created retry execution:[/green] {execution.id}")

    except Exception as e:
        handle_error(e)


@app.command("progress")
def progress(
    ctx: typer.Context,
    execution_id: str = typer.Argument(..., help="Execution ID"),
) -> None:
    """Show execution progress."""
    try:
        client = get_client()
        prog = client.executions.get_progress(execution_id)

        if get_json_flag(ctx):
            output_json(prog)
        else:
            console.print("[bold]Execution Progress[/bold]")
            console.print(f"  Completed: {prog.completed_steps}/{prog.total_steps}")
            console.print(f"  Running: {prog.running_steps}")
            console.print(f"  Pending: {prog.pending_steps}")
            console.print(f"  Failed: {prog.failed_steps}")
            console.print(f"  Progress: {prog.percent_complete:.1f}%")

    except Exception as e:
        handle_error(e)
