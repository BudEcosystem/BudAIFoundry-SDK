"""Pipeline CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from bud.cli._utils import (
    get_client,
    get_json_flag,
    handle_error,
    output_json,
    output_table,
)
from bud.dsl import load_pipeline_file

app = typer.Typer(help="Pipeline management commands.")
console = Console()


@app.command("create")
def create(
    ctx: typer.Context,
    file: Path = typer.Argument(
        ...,
        help="Pipeline definition file (Python)",
        exists=True,
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Pipeline name (overrides file definition)",
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        "-d",
        help="Pipeline description",
    ),
    tags: list[str] | None = typer.Option(
        None,
        "--tag",
        "-t",
        help="Tags in key=value format",
    ),
) -> None:
    """Create a pipeline from a Python file."""
    try:
        # Load pipeline from file
        pipeline_def = load_pipeline_file(str(file))

        # Parse tags
        tags_dict = {}
        if tags:
            for tag in tags:
                if "=" in tag:
                    k, v = tag.split("=", 1)
                    tags_dict[k] = v

        # Create via API
        client = get_client()
        pipeline = client.pipelines.create(
            dag=pipeline_def.to_dag(),
            name=name or pipeline_def.name,
            description=description or pipeline_def.description,
            tags=tags_dict or None,
        )

        if get_json_flag(ctx):
            output_json(pipeline)
        else:
            console.print(f"[green]Created pipeline:[/green] {pipeline.id}")
            console.print(f"  Name: {pipeline.name}")
            console.print(f"  Version: {pipeline.version}")

    except Exception as e:
        handle_error(e)


@app.command("list")
def list_pipelines(
    ctx: typer.Context,
    include_system: bool = typer.Option(
        False,
        "--include-system",
        help="Include system pipelines",
    ),
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    per_page: int = typer.Option(20, "--per-page", help="Items per page"),
) -> None:
    """List all pipelines."""
    try:
        client = get_client()
        pipelines = client.pipelines.list(
            include_system=include_system,
            page=page,
            per_page=per_page,
        )

        if get_json_flag(ctx):
            output_json(pipelines)
        else:
            if not pipelines:
                console.print("[dim]No pipelines found.[/dim]")
                return

            output_table(
                pipelines,
                columns=[
                    ("id", "ID"),
                    ("name", "Name"),
                    ("version", "Version"),
                    ("is_active", "Active"),
                    ("created_at", "Created"),
                ],
                title="Pipelines",
            )

    except Exception as e:
        handle_error(e)


@app.command("describe")
def describe(
    ctx: typer.Context,
    pipeline_id: str = typer.Argument(..., help="Pipeline ID"),
) -> None:
    """Show pipeline details."""
    try:
        client = get_client()
        pipeline = client.pipelines.get(pipeline_id)

        if get_json_flag(ctx):
            output_json(pipeline)
        else:
            console.print(f"[bold]Pipeline: {pipeline.name}[/bold]")
            console.print(f"  ID: {pipeline.id}")
            console.print(f"  Description: {pipeline.description or '-'}")
            console.print(f"  Version: {pipeline.version}")
            console.print(f"  Active: {'Yes' if pipeline.is_active else 'No'}")
            console.print(f"  Created: {pipeline.created_at}")

            if pipeline.tags:
                console.print("  Tags:")
                for k, v in pipeline.tags.items():
                    console.print(f"    {k}: {v}")

            # Handle DAG as either PipelineDAG object or dict
            if pipeline.dag:
                if hasattr(pipeline.dag, "nodes"):
                    nodes = pipeline.dag.nodes
                else:
                    # Handle different DAG structures from API (dict)
                    nodes = pipeline.dag.get("nodes", pipeline.dag.get("steps", []))

                console.print(f"\n  DAG: {len(nodes)} nodes/steps")
                for node in nodes:
                    if isinstance(node, dict):
                        node_id = node.get("id", "?")
                        node_type = node.get("type", node.get("action", "?"))
                        deps = node.get("depends_on", [])
                    else:
                        node_id = node.id
                        node_type = (
                            node.type.value if hasattr(node.type, "value") else str(node.type)
                        )
                        deps = node.depends_on if hasattr(node, "depends_on") else []
                    deps_str = ", ".join(deps) if deps else "none"
                    console.print(f"    - {node_id} ({node_type}) -> depends on: {deps_str}")

    except Exception as e:
        handle_error(e)


@app.command("validate")
def validate(
    ctx: typer.Context,
    file: Path = typer.Argument(
        ...,
        help="Pipeline definition file (Python)",
        exists=True,
    ),
) -> None:
    """Validate a pipeline definition."""
    try:
        # Load pipeline from file
        pipeline_def = load_pipeline_file(str(file))
        dag = pipeline_def.to_dag()

        client = get_client()
        result = client.pipelines.validate(dag)

        if get_json_flag(ctx):
            output_json(result)
        else:
            if result.valid:
                console.print("[green]Pipeline is valid.[/green]")
                if result.step_count is not None:
                    console.print(f"  Steps: {result.step_count}")
            else:
                console.print("[red]Pipeline validation failed:[/red]")
                for error in result.errors:
                    # Handle both string and object errors
                    if isinstance(error, str):
                        console.print(f"  - {error}")
                    else:
                        console.print(f"  - {error.path}: {error.message}")

            if result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in result.warnings:
                    # Handle both string and object warnings
                    if isinstance(warning, str):
                        console.print(f"  - {warning}")
                    else:
                        console.print(f"  - {warning.path}: {warning.message}")

    except Exception as e:
        handle_error(e)


@app.command("delete")
def delete(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation",
    ),
) -> None:
    """Delete a pipeline."""
    try:
        client = get_client()

        if not force:
            pipeline = client.pipelines.get(pipeline_id)
            if not typer.confirm(f"Delete pipeline '{pipeline.name}'?"):
                raise typer.Abort()

        client.pipelines.delete(pipeline_id)
        console.print(f"[green]Deleted pipeline:[/green] {pipeline_id}")

    except typer.Abort:
        console.print("[dim]Cancelled.[/dim]")
    except Exception as e:
        handle_error(e)
