"""Authentication CLI commands."""

from __future__ import annotations

import json
import os
import sys
import time

import typer
from rich.console import Console

from bud._config import CONFIG_DIR, CONFIG_FILE, BudConfig, get_config_dir, save_config

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

app = typer.Typer(help="Authentication commands.")
console = Console()

# Token storage file
TOKENS_FILE = CONFIG_DIR / "tokens.json"


def save_tokens(
    access_token: str,
    refresh_token: str,
    expires_in: int,
) -> None:
    """Save tokens to tokens file."""
    get_config_dir()  # Ensure directory exists
    tokens = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in,
    }
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
    # Set restrictive permissions
    TOKENS_FILE.chmod(0o600)


def load_tokens() -> dict | None:
    """Load tokens from tokens file."""
    if not TOKENS_FILE.exists():
        return None
    try:
        return json.loads(TOKENS_FILE.read_text())
    except Exception:
        return None


def clear_tokens() -> None:
    """Clear stored tokens."""
    if TOKENS_FILE.exists():
        TOKENS_FILE.write_text("{}")


@app.command("login")
def login(
    email: str | None = typer.Option(
        None,
        "--email",
        "-e",
        help="Email address for JWT authentication",
    ),
    password: str | None = typer.Option(
        None,
        "--password",
        "-p",
        help="Password for JWT authentication",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="API key for token-based authentication",
    ),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="API URL (default: https://api.bud.io)",
    ),
) -> None:
    """Authenticate with BudAI.

    Supports two authentication methods:

    1. Email/Password (JWT):
       bud auth login --email user@example.com --password secret

    2. API Token:
       bud auth login --token YOUR_TOKEN

    If no options provided, will prompt interactively.
    """
    # Load base_url from config if not provided
    if not api_url:
        config = BudConfig.load()
        base_url = config.base_url
    else:
        base_url = api_url

    # Determine auth method
    if token:
        # API key authentication
        _login_with_token(token, base_url)
    elif email and password:
        # JWT authentication
        _login_with_jwt(email, password, base_url)
    else:
        # Interactive mode - prompt for email/password
        console.print("BudAI Authentication")
        console.print("=" * 40)
        console.print()

        if not email:
            email = typer.prompt("Email")
        if not password:
            password = typer.prompt("Password", hide_input=True)

        _login_with_jwt(email, password, base_url)


def _login_with_token(token: str, base_url: str) -> None:
    """Login with API token."""
    try:
        from bud.client import BudClient

        client = BudClient(
            api_key=token,
            base_url=base_url,
        )
        # Verify token works
        client.pipelines.list()
        client.close()
    except Exception as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        raise typer.Exit(1)

    # Save to config
    _save_auth_config(api_key=token, base_url=base_url)
    console.print("[green]Authentication successful![/green]")
    console.print(f"Config saved to: {CONFIG_FILE}")


def _login_with_jwt(email: str, password: str, base_url: str) -> None:
    """Login with email/password (JWT)."""
    import httpx

    try:
        response = httpx.post(
            f"{base_url}/auth/login",
            json={"email": email, "password": password},
            timeout=30.0,
        )

        if response.status_code == 401:
            console.print("[red]Invalid email or password.[/red]")
            raise typer.Exit(1)

        response.raise_for_status()
        data = response.json()

        # Handle nested token response (API returns tokens under 'token' key)
        token_data = data.get("token", data)
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        expires_in = token_data.get("expires_in", 3600)

        # Save tokens
        save_tokens(access_token, refresh_token, expires_in)

        # Save config (base_url and auth method)
        _save_auth_config(base_url=base_url, auth_method="jwt", email=email)

        console.print("[green]Authentication successful![/green]")
        console.print(f"  Logged in as: {email}")
        console.print(f"  Tokens saved to: {TOKENS_FILE}")

    except httpx.HTTPStatusError as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Connection error:[/red] {e}")
        raise typer.Exit(1)


def _save_auth_config(
    api_key: str | None = None,
    base_url: str | None = None,
    auth_method: str | None = None,
    email: str | None = None,
) -> None:
    """Save authentication config."""
    config_data = {}

    # Load existing config
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            config_data = tomllib.load(f)

    # Update values
    if api_key:
        config_data["api_key"] = api_key
    if base_url:
        config_data["api_url"] = base_url

    # Save auth section for JWT
    if auth_method == "jwt":
        config_data["auth"] = {
            "type": "jwt",
            "email": email,
        }
        # Remove api_key if switching to JWT
        config_data.pop("api_key", None)

    save_config(config_data)


@app.command("logout")
def logout() -> None:
    """Log out and remove stored credentials."""
    cleared_something = False

    # Clear tokens file
    if TOKENS_FILE.exists():
        clear_tokens()
        cleared_something = True

    # Clear api_key from config
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            config = tomllib.load(f)

        if "api_key" in config or "auth" in config:
            config.pop("api_key", None)
            config.pop("auth", None)
            save_config(config)
            cleared_something = True

    if cleared_something:
        console.print("[green]Logged out successfully.[/green]")
    else:
        console.print("[dim]Not logged in.[/dim]")


@app.command("status")
def status() -> None:
    """Show current authentication status."""
    config = BudConfig.load()
    tokens = load_tokens()

    # Check for API key
    if config.api_key:
        masked = (
            config.api_key[:8] + "..." + config.api_key[-4:] if len(config.api_key) > 12 else "***"
        )

        console.print("[green]Authenticated[/green] (API Key)")
        console.print(f"  Token: {masked}")
        console.print(f"  API URL: {config.base_url}")

        if os.getenv("BUD_API_KEY"):
            console.print("  Source: Environment variable (BUD_API_KEY)")
        else:
            console.print(f"  Source: Config file ({CONFIG_FILE})")
        return

    # Check for JWT tokens
    if tokens and tokens.get("access_token"):
        expires_at = tokens.get("expires_at", 0)
        is_expired = time.time() > expires_at

        console.print("[green]Authenticated[/green] (JWT)")

        if config.auth and config.auth.email:
            console.print(f"  Email: {config.auth.email}")

        if is_expired:
            console.print("  Status: [yellow]Token expired (will auto-refresh)[/yellow]")
        else:
            remaining = int(expires_at - time.time())
            console.print(f"  Status: Valid ({remaining}s remaining)")

        console.print(f"  API URL: {config.base_url}")
        return

    # Not authenticated
    console.print("[yellow]Not authenticated[/yellow]")
    console.print("\nTo authenticate, run:")
    console.print("  bud auth login --email YOUR_EMAIL --password YOUR_PASSWORD")
    console.print("  or")
    console.print("  bud auth login --token YOUR_API_KEY")


@app.command("token")
def show_token() -> None:
    """Display the current access token (use with caution)."""
    config = BudConfig.load()
    tokens = load_tokens()

    token = None
    if config.api_key:
        token = config.api_key
    elif tokens and tokens.get("access_token"):
        token = tokens["access_token"]

    if not token:
        console.print("[yellow]Not authenticated[/yellow]")
        raise typer.Exit(1)

    if not typer.confirm("This will display your token. Continue?", default=False):
        raise typer.Abort()

    console.print(token)


@app.command("refresh")
def refresh() -> None:
    """Manually refresh JWT tokens."""
    tokens = load_tokens()

    if not tokens or not tokens.get("refresh_token"):
        console.print("[yellow]No refresh token available.[/yellow]")
        console.print("Please login again with: bud auth login")
        raise typer.Exit(1)

    config = BudConfig.load()
    base_url = config.base_url

    import httpx

    try:
        response = httpx.post(
            f"{base_url}/auth/refresh-token",
            json={"refresh_token": tokens["refresh_token"]},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        save_tokens(
            data["access_token"],
            data["refresh_token"],
            data.get("expires_in", 3600),
        )

        console.print("[green]Tokens refreshed successfully![/green]")

    except httpx.HTTPStatusError:
        console.print("[red]Failed to refresh tokens.[/red]")
        console.print("Please login again with: bud auth login")
        raise typer.Exit(1)
