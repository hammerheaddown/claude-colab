"""Tests for the claude-colab CLI."""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
import pytest

from claude_colab.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestConnect:
    def test_uri_format(self, runner, tmp_config):
        result = runner.invoke(main, ["connect", "cc://tok123:key456@my-host.trycloudflare.com"])
        assert result.exit_code == 0
        assert "Connected" in result.output
        config = json.loads(tmp_config.read_text())
        assert config["url"] == "https://my-host.trycloudflare.com"
        assert config["token"] == "tok123"
        assert config["encryption_key"] == "key456"

    def test_interactive(self, runner, tmp_config):
        result = runner.invoke(main, ["connect"], input="cc://tok:key@host.com\n")
        assert result.exit_code == 0
        assert "Connected" in result.output

    def test_stdin_pipe(self, runner, tmp_config):
        result = runner.invoke(main, ["connect", "-"], input="cc://tok:key@host.com\n")
        assert result.exit_code == 0

    def test_invalid_uri(self, runner, tmp_config):
        result = runner.invoke(main, ["connect", "https://bad.com"])
        assert result.exit_code != 0
        assert "cc://" in result.output


class TestDisconnect:
    def test_clears_config(self, runner, tmp_config):
        tmp_config.write_text(json.dumps({"url": "x", "token": "x", "encryption_key": "x"}))
        result = runner.invoke(main, ["disconnect"])
        assert result.exit_code == 0
        assert not tmp_config.exists()


class TestStatus:
    @patch("claude_colab.cli._get_client")
    def test_shows_gpu(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.health.return_value = {
            "status": "ok",
            "version": "0.1.0",
            "gpu_name": "Tesla T4",
            "vram_total": 15.0,
            "vram_used": 1.2,
            "disk_free": "107GB",
            "uptime": 3600,
        }
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["status"])
        assert "Tesla T4" in result.output

    @patch("claude_colab.cli._get_client")
    def test_not_connected(self, mock_get_client, runner):
        mock_get_client.return_value = None
        result = runner.invoke(main, ["status"])
        assert result.exit_code != 0
        assert "Not connected" in result.output


class TestExec:
    @patch("claude_colab.cli._get_client")
    def test_runs_command(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.exec.return_value = {
            "stdout": "Tesla T4\n",
            "stderr": "",
            "exit_code": 0,
            "duration": 0.3,
        }
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["exec", "nvidia-smi"])
        assert "Tesla T4" in result.output


class TestVersion:
    def test_shows_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert "0.1.0" in result.output
