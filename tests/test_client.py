"""Tests for ColabClient — HTTP client with E2E encryption."""

import base64
import json

import httpx
import pytest
import respx

from claude_colab.client import ColabClient, ColabError
from claude_colab.crypto import encrypt, generate_key


@pytest.fixture
def key():
    return generate_key()


@pytest.fixture
def client(key):
    return ColabClient(
        url="https://test.trycloudflare.com",
        token="testtoken123",
        encryption_key=key,
    )


class TestHealth:
    @respx.mock
    def test_returns_gpu_info(self, client):
        health_data = {
            "status": "ok",
            "version": "0.1.0",
            "gpu_name": "Tesla T4",
            "vram_total": 15.0,
            "vram_used": 1.2,
        }
        respx.get("https://test.trycloudflare.com/health").mock(
            return_value=httpx.Response(200, json=health_data)
        )
        result = client.health()
        assert result["gpu_name"] == "Tesla T4"

    @respx.mock
    def test_auth_header_sent(self, client):
        route = respx.get("https://test.trycloudflare.com/health").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client.health()
        assert route.calls[0].request.headers["authorization"] == "Bearer testtoken123"

    @respx.mock
    def test_401_raises(self, client):
        respx.get("https://test.trycloudflare.com/health").mock(
            return_value=httpx.Response(401)
        )
        with pytest.raises(ColabError, match="Invalid token"):
            client.health()

    @respx.mock
    def test_connection_error_raises(self, client):
        respx.get("https://test.trycloudflare.com/health").mock(
            side_effect=httpx.ConnectError("refused")
        )
        with pytest.raises(ColabError, match="timed out"):
            client.health()


class TestExec:
    @respx.mock
    def test_returns_stdout(self, client, key):
        response_data = {"stdout": "Tesla T4\n", "stderr": "", "exit_code": 0, "duration": 0.5}
        encrypted_response = encrypt(key, response_data)
        respx.post("https://test.trycloudflare.com/exec").mock(
            return_value=httpx.Response(200, content=encrypted_response)
        )
        result = client.exec("nvidia-smi")
        assert result["stdout"] == "Tesla T4\n"
        assert result["exit_code"] == 0

    @respx.mock
    def test_sends_encrypted_body(self, client, key):
        response_data = {"stdout": "", "stderr": "", "exit_code": 0, "duration": 0.1}
        route = respx.post("https://test.trycloudflare.com/exec").mock(
            return_value=httpx.Response(200, content=encrypt(key, response_data))
        )
        client.exec("ls")
        body = route.calls[0].request.content
        with pytest.raises(json.JSONDecodeError):
            json.loads(body)


class TestPython:
    @respx.mock
    def test_returns_output(self, client, key):
        response_data = {"output": "42\n", "error": None, "return_value": 42, "duration": 0.1}
        respx.post("https://test.trycloudflare.com/python").mock(
            return_value=httpx.Response(200, content=encrypt(key, response_data))
        )
        result = client.python("print(42)")
        assert result["output"] == "42\n"
        assert result["return_value"] == 42


class TestUpload:
    @respx.mock
    def test_sends_file(self, client, key, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")
        response_data = {"ok": True, "path": "/content/test.py", "size_bytes": 14}
        respx.post("https://test.trycloudflare.com/upload").mock(
            return_value=httpx.Response(200, content=encrypt(key, response_data))
        )
        result = client.upload(str(test_file), "/content/test.py")
        assert result["ok"] is True


class TestDownload:
    @respx.mock
    def test_downloads_file(self, client, key, tmp_path):
        file_content = b"model weights here"
        response_data = {
            "content_b64": base64.b64encode(file_content).decode(),
            "path": "/content/model.pt",
            "size_bytes": len(file_content),
        }
        respx.post("https://test.trycloudflare.com/download").mock(
            return_value=httpx.Response(200, content=encrypt(key, response_data))
        )
        local_path = tmp_path / "model.pt"
        result = client.download("/content/model.pt", str(local_path))
        assert local_path.read_bytes() == file_content


class TestTimeout:
    @respx.mock
    def test_read_timeout_raises(self, client):
        respx.post("https://test.trycloudflare.com/exec").mock(
            side_effect=httpx.ReadTimeout("read timed out")
        )
        with pytest.raises(ColabError, match="timed out"):
            client.exec("sleep 999")
