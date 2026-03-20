"""Config file management for claude-colab.

Stores connection details in ~/.claude-colab.json with 0600 permissions.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


def config_path() -> Path:
    """Return path to the config file."""
    return Path.home() / ".claude-colab.json"


def parse_uri(uri: str) -> Tuple[str, str, str]:
    """Parse a cc://TOKEN:KEY@host URI into (url, token, encryption_key).

    Raises ValueError if the URI is malformed.
    """
    if not uri.startswith("cc://"):
        raise ValueError("Connection string must start with cc://")

    rest = uri[5:]  # strip cc://
    if "@" not in rest:
        raise ValueError("Invalid connection string: missing @host")

    credentials, host = rest.rsplit("@", 1)
    if not host:
        raise ValueError("Invalid connection string: empty host")

    if ":" not in credentials:
        raise ValueError("Invalid connection string: must be cc://TOKEN:KEY@host")

    token, key = credentials.split(":", 1)
    if not token or not key:
        raise ValueError("Invalid connection string: empty token or key")

    url = f"https://{host}"
    return url, token, key


def save_config(url: str, token: str, encryption_key: str) -> Path:
    """Save connection config to disk with secure permissions."""
    path = config_path()
    data = {
        "url": url,
        "token": token,
        "encryption_key": encryption_key,
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)
    return path


def load_config() -> Optional[dict]:
    """Load connection config from disk. Returns None if file doesn't exist."""
    path = config_path()
    if not path.exists():
        return None
    return json.loads(path.read_text())


def clear_config() -> None:
    """Remove the config file."""
    path = config_path()
    if path.exists():
        path.unlink()
