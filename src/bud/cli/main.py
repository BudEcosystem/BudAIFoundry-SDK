"""Main CLI entry point."""

from __future__ import annotations

import typer
from rich.console import Console

from bud._version import __version__
from bud.cli import action, auth, config, execution, pipeline, run

app = typer.Typer(
    name="bud",
    help="BudAI CLI - Pipeline orchestration made simple.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

# Register sub-commands
app.add_typer(pipeline.app, name="pipeline", help="Pipeline management")
app.add_typer(run.app, name="run", help="Run pipelines")
app.add_typer(execution.app, name="execution", help="Execution management")
app.add_typer(action.app, name="action", help="Action management")
app.add_typer(auth.app, name="auth", help="Authentication")
app.add_typer(config.app, name="config", help="Configuration management")


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"bud-sdk version {__version__}")


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format",
        is_eager=True,
    ),
) -> None:
    """BudAI CLI - Pipeline orchestration made simple."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output


# Shell completion command
@app.command(name="completion")
def completion(
    shell: str = typer.Argument(
        ...,
        help="Shell type (bash, zsh, fish)",
    ),
) -> None:
    """Generate shell completion script.

    Example:
        bud completion bash >> ~/.bashrc
        bud completion zsh >> ~/.zshrc
        bud completion fish > ~/.config/fish/completions/bud.fish
    """
    import subprocess
    import sys

    if shell not in ("bash", "zsh", "fish"):
        console.print(f"[red]Unsupported shell: {shell}[/red]")
        console.print("Supported shells: bash, zsh, fish")
        raise typer.Exit(1)

    # Use typer's built-in completion
    result = subprocess.run(
        [sys.executable, "-m", "bud", "--show-completion", shell],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print(result.stdout)
    else:
        # Fallback message
        console.print("# Add this to your shell config:")
        console.print(f'eval "$(bud --show-completion {shell})"')


if __name__ == "__main__":
    app()
