"""Run CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table

from bud.cli._utils import get_client, get_json_flag, handle_error, output_json
from bud.dsl import load_pipeline_file
from bud.models.execution import ExecutionStatus

app = typer.Typer(help="Run pipelines.")
console = Console()


@app.command(name="pipeline")
def run_pipeline(
    ctx: typer.Context,
    target: str = typer.Argument(
        ...,
        help="Pipeline ID or path to pipeline file",
    ),
    params: Optional[list[str]] = typer.Option(
        None,
        "--param",
        "-p",
        help="Parameters in key=value format",
    ),
    env: Optional[str] = typer.Option(
        None,
        "--env",
        "-e",
        help="Environment (dev, staging, prod)",
    ),
    wait: bool = typer.Option(
        True,
        "--wait/--detach",
        help="Wait for completion or detach immediately",
    ),
    timeout: Optional[int] = typer.Option(
        None,
        "--timeout",
        "-t",
        help="Timeout in seconds (when waiting)",
    ),
) -> None:
    """Run a pipeline.

    TARGET can be either:
      - A pipeline ID (e.g., "abc123")
      - A path to a pipeline file (e.g., "deploy.py")

    Examples:
        bud run abc123 --param image=latest
        bud run deploy.py --env prod --wait
        bud run pipeline.py --detach
    """
    try:
        client = get_client()

        # Determine if target is a file or pipeline ID
        target_path = Path(target)
        if target_path.exists() and target_path.suffix == ".py":
            # Load from file and create/get pipeline
            pipeline_def = load_pipeline_file(str(target_path))

            # Create pipeline (or we could look up existing by name)
            pipeline = client.pipelines.create(
                dag=pipeline_def.to_dag(),
                name=pipeline_def.name,
                description=pipeline_def.description,
            )
            pipeline_id = pipeline.id
            console.print(f"[dim]Created pipeline: {pipeline_id}[/dim]")
        else:
            pipeline_id = target

        # Parse params
        params_dict = {}
        if params:
            for param in params:
                if "=" in param:
                    k, v = param.split("=", 1)
                    params_dict[k] = v

        # Add environment to context
        context = {}
        if env:
            context["environment"] = env

        # Create execution
        if wait:
            with Live(
                Spinner("dots", text="Starting execution..."),
                console=console,
                transient=True,
            ) as live:
                execution = client.executions.create(
                    pipeline_id,
                    params=params_dict or None,
                    context=context or None,
                    wait=False,
                )
                exec_id = execution.effective_id
                live.update(Spinner("dots", text=f"Running... ({exec_id})"))

                # Poll for completion
                while True:
                    execution = client.executions.get(exec_id)

                    # Handle status as either Enum or string
                    status_str = execution.status.value if hasattr(execution.status, "value") else str(execution.status)
                    status_upper = status_str.upper()

                    if status_upper == "COMPLETED":
                        break
                    elif status_upper in ("FAILED", "CANCELLED", "TIMED_OUT"):
                        break

                    import time
                    time.sleep(2)
        else:
            execution = client.executions.create(
                pipeline_id,
                params=params_dict or None,
                context=context or None,
                wait=False,
            )

        # Output result
        if get_json_flag(ctx):
            output_json(execution)
        else:
            # Handle status as either Enum or string
            status_str = execution.status.value if hasattr(execution.status, "value") else str(execution.status)
            status_upper = status_str.upper()
            status_color = {
                "COMPLETED": "green",
                "FAILED": "red",
                "CANCELLED": "yellow",
                "RUNNING": "blue",
                "PENDING": "dim",
                "TIMED_OUT": "red",
            }.get(status_upper, "white")

            exec_id = execution.effective_id
            pipeline_name = execution.effective_pipeline_name or "-"
            console.print(f"\n[bold]Execution:[/bold] {exec_id}")
            console.print(f"  Pipeline: {pipeline_name}")
            console.print(f"  Status: [{status_color}]{status_str}[/{status_color}]")

            if execution.duration_ms:
                duration = execution.duration_ms / 1000
                console.print(f"  Duration: {duration:.2f}s")

            if execution.error:
                console.print(f"  [red]Error:[/red] {execution.error}")

            if status_upper == "FAILED":
                raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        handle_error(e)
