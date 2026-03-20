"""Tests for the claude-colab CLI."""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
import pytest

from claude_colab.cli import main
from claude_colab.client import ColabError


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


class TestExecError:
    @patch("claude_colab.cli._get_client")
    def test_exec_stderr(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.exec.return_value = {
            "stdout": "",
            "stderr": "command not found\n",
            "exit_code": 127,
            "duration": 0.1,
        }
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["exec", "badcmd"])
        assert result.exit_code == 127

    @patch("claude_colab.cli._get_client")
    def test_exec_colab_error(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.exec.side_effect = ColabError("timed out")
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["exec", "sleep 999"])
        assert result.exit_code != 0
        assert "timed out" in result.output


class TestPython:
    @patch("claude_colab.cli._get_client")
    def test_inline_code(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.python.return_value = {
            "output": "42\n",
            "error": None,
            "return_value": 42,
            "duration": 0.1,
        }
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["python", "-c", "print(42)"])
        assert "42" in result.output

    @patch("claude_colab.cli._get_client")
    def test_inline_error(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.python.return_value = {
            "output": "",
            "error": "NameError: name 'x' is not defined",
            "return_value": None,
            "duration": 0.1,
        }
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["python", "-c", "print(x)"])
        assert "NameError" in result.output

    @patch("claude_colab.cli._get_client")
    def test_script_file(self, mock_get_client, runner, tmp_path):
        script = tmp_path / "test_script.py"
        script.write_text("print('hello')")
        mock_client = MagicMock()
        mock_client.upload.return_value = {"ok": True, "path": "/content/tmp.py", "size_bytes": 14}
        mock_client.exec.return_value = {
            "stdout": "hello\n",
            "stderr": "",
            "exit_code": 0,
            "duration": 0.1,
        }
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["python", str(script)])
        assert "hello" in result.output
        assert mock_client.upload.called
        # cleanup call (rm -f)
        assert mock_client.exec.call_count == 2

    def test_script_not_found(self, runner):
        with patch("claude_colab.cli._get_client") as mock_get:
            mock_get.return_value = MagicMock()
            result = runner.invoke(main, ["python", "nonexistent.py"])
            assert result.exit_code != 0
            assert "not found" in result.output.lower() or "not found" in (result.output + str(result.exception)).lower()

    @patch("claude_colab.cli._get_client")
    def test_python_colab_error(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.python.side_effect = ColabError("session expired")
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["python", "-c", "pass"])
        assert result.exit_code != 0


class TestUpload:
    @patch("claude_colab.cli._get_client")
    def test_uploads_file(self, mock_get_client, runner, tmp_path):
        local_file = tmp_path / "data.csv"
        local_file.write_text("a,b,c")
        mock_client = MagicMock()
        mock_client.upload.return_value = {"ok": True, "path": "/content/data.csv", "size_bytes": 5}
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["upload", str(local_file), "/content/data.csv"])
        assert "5 bytes" in result.output

    @patch("claude_colab.cli._get_client")
    def test_upload_error(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.upload.side_effect = ColabError("file too large")
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["upload", "/tmp/x", "/content/x"])
        assert result.exit_code != 0


class TestDownload:
    @patch("claude_colab.cli._get_client")
    def test_downloads_file(self, mock_get_client, runner, tmp_path):
        local_dest = tmp_path / "result.txt"
        mock_client = MagicMock()
        mock_client.download.return_value = {"content_b64": "aGVsbG8=", "path": "/content/r.txt", "size_bytes": 5}
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["download", "/content/r.txt", str(local_dest)])
        assert "5 bytes" in result.output

    @patch("claude_colab.cli._get_client")
    def test_download_error(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.download.side_effect = ColabError("not found")
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["download", "/content/x", "/tmp/x"])
        assert result.exit_code != 0


class TestStatusError:
    @patch("claude_colab.cli._get_client")
    def test_status_colab_error(self, mock_get_client, runner):
        mock_client = MagicMock()
        mock_client.health.side_effect = ColabError("connection refused")
        mock_get_client.return_value = mock_client
        result = runner.invoke(main, ["status"])
        assert result.exit_code != 0
        assert "connection refused" in result.output


class TestVersion:
    def test_shows_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert "0.1.0" in result.output
