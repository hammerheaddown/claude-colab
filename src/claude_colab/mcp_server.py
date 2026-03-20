"""MCP server for claude-colab — exposes Colab GPU as Claude Code tools.

Run via: claude-colab mcp-serve
Registers 5 tools: colab_status, colab_exec, colab_python, colab_upload, colab_download.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional, Tuple, Union

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from claude_colab import __version__
from claude_colab.client import ColabClient, ColabError
from claude_colab.config import load_config

HEALTH_CHECK_INTERVAL = 60  # seconds
SESSION_WARN_HOURS = 10

_last_health_check: float = 0


def _get_client_and_config() -> Tuple[Optional[ColabClient], Optional[dict]]:
    """Load config and create client. Returns (client, config) or (None, None)."""
    config = load_config()
    if config is None:
        return None, None
    client = ColabClient(
        url=config["url"],
        token=config["token"],
        encryption_key=config["encryption_key"],
    )
    return client, config


def _check_session_age(connected_at_iso: str) -> Optional[str]:
    """Warn if session is old. Takes ISO 8601 string from config."""
    try:
        connected_dt = datetime.fromisoformat(connected_at_iso.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - connected_dt).total_seconds() / 3600
    except (ValueError, AttributeError):
        return None
    if age_hours > SESSION_WARN_HOURS:
        return (
            f"Warning: Colab session may expire soon "
            f"(connected {age_hours:.0f}h ago, max 12h). Consider restarting."
        )
    return None


def _ensure_healthy(client: ColabClient, last_check: Optional[float] = None) -> Optional[str]:
    """Lazy health check. Returns error/warning string or None."""
    global _last_health_check
    check_time = last_check if last_check is not None else _last_health_check
    if time.time() - check_time < HEALTH_CHECK_INTERVAL:
        return None
    try:
        health = client.health()
        _last_health_check = time.time()
        server_version = health.get("version", "unknown")
        if server_version != __version__:
            return f"Warning: version mismatch (CLI={__version__}, server={server_version})"
        return None
    except ColabError as e:
        return str(e)


def _not_connected_error() -> str:
    return "Not connected. Run: claude-colab connect cc://TOKEN:KEY@host"


def _prepare_call() -> Tuple[Optional[ColabClient], list]:
    """Common setup for all tool calls. Returns (client, warnings)."""
    client, config = _get_client_and_config()
    if client is None:
        return None, [_not_connected_error()]
    warnings = []
    health_warning = _ensure_healthy(client)
    if health_warning:
        warnings.append(health_warning)
    connected_at = config.get("connected_at", "")
    age_warning = _check_session_age(connected_at)
    if age_warning:
        warnings.append(age_warning)
    return client, warnings


def colab_status() -> Union[dict, str]:
    """Get GPU status."""
    client, warnings = _prepare_call()
    if client is None:
        return warnings[0]
    try:
        result = client.health()
        if warnings:
            result["_warnings"] = warnings
        return result
    except ColabError as e:
        return str(e)


def colab_exec(command: str, timeout: int = 300) -> Union[dict, str]:
    """Run a shell command on Colab."""
    client, warnings = _prepare_call()
    if client is None:
        return warnings[0]
    try:
        result = client.exec(command, timeout=timeout)
        if warnings:
            result["_warnings"] = warnings
        return result
    except ColabError as e:
        return str(e)


def colab_python(code: str, timeout: int = 300) -> Union[dict, str]:
    """Execute Python code on Colab."""
    client, warnings = _prepare_call()
    if client is None:
        return warnings[0]
    try:
        result = client.python(code, timeout=timeout)
        if warnings:
            result["_warnings"] = warnings
        return result
    except ColabError as e:
        return str(e)


def colab_upload(local_path: str, remote_path: str) -> Union[dict, str]:
    """Upload a file to Colab."""
    client, warnings = _prepare_call()
    if client is None:
        return warnings[0]
    try:
        result = client.upload(local_path, remote_path)
        if warnings:
            result["_warnings"] = warnings
        return result
    except ColabError as e:
        return str(e)


def colab_download(remote_path: str, local_path: str) -> Union[dict, str]:
    """Download a file from Colab."""
    client, warnings = _prepare_call()
    if client is None:
        return warnings[0]
    try:
        result = client.download(remote_path, local_path)
        if warnings:
            result["_warnings"] = warnings
        return result
    except ColabError as e:
        return str(e)


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("claude-colab")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="colab_status",
                description="Get Colab GPU status: name, VRAM, disk, uptime",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="colab_exec",
                description="Run a shell command on the Colab GPU instance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (max 600)", "default": 300},
                    },
                    "required": ["command"],
                },
            ),
            Tool(
                name="colab_python",
                description="Execute Python code on the Colab GPU instance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (max 600)", "default": 300},
                    },
                    "required": ["code"],
                },
            ),
            Tool(
                name="colab_upload",
                description="Upload a local file to the Colab GPU instance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "local_path": {"type": "string", "description": "Local file path to upload"},
                        "remote_path": {"type": "string", "description": "Destination path on Colab"},
                    },
                    "required": ["local_path", "remote_path"],
                },
            ),
            Tool(
                name="colab_download",
                description="Download a file from the Colab GPU instance to local disk",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "remote_path": {"type": "string", "description": "File path on Colab to download"},
                        "local_path": {"type": "string", "description": "Local destination path"},
                    },
                    "required": ["remote_path", "local_path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        handlers = {
            "colab_status": lambda args: colab_status(),
            "colab_exec": lambda args: colab_exec(args["command"], args.get("timeout", 300)),
            "colab_python": lambda args: colab_python(args["code"], args.get("timeout", 300)),
            "colab_upload": lambda args: colab_upload(args["local_path"], args["remote_path"]),
            "colab_download": lambda args: colab_download(args["remote_path"], args["local_path"]),
        }
        handler = handlers.get(name)
        if handler is None:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        result = handler(arguments)
        if isinstance(result, dict):
            text = json.dumps(result, indent=2)
        else:
            text = str(result)
        return [TextContent(type="text", text=text)]

    return server


async def run_server():
    """Run the MCP server over stdio."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
