"""claude-colab CLI — human-friendly commands for Colab GPU access."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Optional

import click

from claude_colab import __version__
from claude_colab.client import ColabClient, ColabError
from claude_colab.config import clear_config, load_config, parse_uri, save_config


def _get_client() -> Optional[ColabClient]:
    """Load config and return a ColabClient, or None if not connected."""
    config = load_config()
    if config is None:
        return None
    return ColabClient(
        url=config["url"],
        token=config["token"],
        encryption_key=config["encryption_key"],
    )


def _require_client() -> ColabClient:
    """Get client or exit with error."""
    client = _get_client()
    if client is None:
        click.echo(
            "Error: Not connected. Run: claude-colab connect cc://TOKEN:KEY@host",
            err=True,
        )
        raise SystemExit(1)
    return client


@click.group()
@click.version_option(__version__)
def main():
    """claude-colab — Give Claude Code GPU access via Google Colab."""


@main.command()
@click.argument("uri", required=False)
def connect(uri: Optional[str]):
    """Save Colab connection details.

    URI format: cc://TOKEN:KEY@hostname

    Three ways to connect:
      claude-colab connect cc://TOKEN:KEY@host
      claude-colab connect        (interactive prompt)
      echo "cc://..." | claude-colab connect -   (stdin pipe)
    """
    if uri is None:
        uri = click.prompt("Connection string")
    elif uri == "-":
        uri = sys.stdin.readline().strip()

    try:
        url, token, key = parse_uri(uri)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    save_config(url, token, key)
    click.echo(f"Connected to {url}")


@main.command()
def disconnect():
    """Clear saved connection."""
    clear_config()
    click.echo("Disconnected.")


@main.command()
def status():
    """Show GPU status, memory, and uptime."""
    client = _require_client()
    try:
        info = client.health()
    except ColabError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"GPU:     {info.get('gpu_name', 'unknown')}")
    click.echo(f"VRAM:    {info.get('vram_used', '?')}/{info.get('vram_total', '?')} GB")
    click.echo(f"Disk:    {info.get('disk_free', '?')} free")
    click.echo(f"Uptime:  {info.get('uptime', '?')}s")
    click.echo(f"Version: {info.get('version', '?')}")


@main.command("exec")
@click.argument("command")
@click.option("--timeout", default=300, help="Timeout in seconds (max 600)")
def exec_cmd(command: str, timeout: int):
    """Run a shell command on Colab."""
    client = _require_client()
    try:
        result = client.exec(command, timeout=timeout)
    except ColabError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if result["stdout"]:
        click.echo(result["stdout"], nl=False)
    if result["stderr"]:
        click.echo(result["stderr"], err=True, nl=False)
    raise SystemExit(result["exit_code"])


@main.command("python")
@click.argument("source")
@click.option("-c", "inline", is_flag=True, help="Execute SOURCE as inline code")
@click.option("--timeout", default=300, help="Timeout in seconds (max 600)")
def python_cmd(source: str, inline: bool, timeout: int):
    """Execute Python code or a script on Colab.

    Inline:  claude-colab python -c "print(42)"
    Script:  claude-colab python myscript.py
    """
    client = _require_client()
    try:
        if inline:
            result = client.python(source, timeout=timeout)
            if result.get("output"):
                click.echo(result["output"], nl=False)
            if result.get("error"):
                click.echo(result["error"], err=True)
        else:
            script_path = Path(source)
            if not script_path.exists():
                click.echo(f"Error: File not found: {source}", err=True)
                raise SystemExit(1)

            remote_name = f"_claude_colab_{uuid.uuid4().hex[:8]}.py"
            remote_path = f"/content/{remote_name}"
            client.upload(str(script_path), remote_path)
            result = client.exec(f"python {remote_path}", timeout=timeout)
            client.exec(f"rm -f {remote_path}", timeout=30)

            if result["stdout"]:
                click.echo(result["stdout"], nl=False)
            if result["stderr"]:
                click.echo(result["stderr"], err=True, nl=False)
            raise SystemExit(result["exit_code"])
    except ColabError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("local_path")
@click.argument("remote_path")
def upload(local_path: str, remote_path: str):
    """Upload a local file to Colab."""
    client = _require_client()
    try:
        result = client.upload(local_path, remote_path)
        click.echo(f"Uploaded {result['size_bytes']} bytes -> {result['path']}")
    except ColabError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("remote_path")
@click.argument("local_path")
def download(remote_path: str, local_path: str):
    """Download a file from Colab."""
    client = _require_client()
    try:
        result = client.download(remote_path, local_path)
        click.echo(f"Downloaded {result['size_bytes']} bytes -> {local_path}")
    except ColabError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
