"""Shared test fixtures for claude-colab."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_config(tmp_path):
    """Provide a temporary config file path and clean up after."""
    config_path = tmp_path / ".claude-colab.json"
    with patch("claude_colab.config.config_path", return_value=config_path):
        yield config_path


@pytest.fixture
def sample_config():
    """Return a valid config dict."""
    from cryptography.fernet import Fernet

    return {
        "url": "https://test-abc.trycloudflare.com",
        "token": "a" * 64,
        "encryption_key": Fernet.generate_key().decode(),
        "connected_at": "2026-03-20T14:30:00Z",
    }
