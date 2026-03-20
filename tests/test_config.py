"""Tests for config file read/write."""

import json
import os
import stat

import pytest

from claude_colab.config import (
    clear_config,
    config_path,
    load_config,
    parse_uri,
    save_config,
)


class TestConfigPath:
    def test_returns_path_in_home(self):
        path = config_path()
        assert path.name == ".claude-colab.json"
        assert str(path).startswith(os.path.expanduser("~"))


class TestParseUri:
    def test_valid_uri(self):
        url, token, key = parse_uri("cc://mytoken:mykey@abc-xyz.trycloudflare.com")
        assert url == "https://abc-xyz.trycloudflare.com"
        assert token == "mytoken"
        assert key == "mykey"

    def test_invalid_scheme(self):
        with pytest.raises(ValueError, match="must start with cc://"):
            parse_uri("https://example.com")

    def test_missing_key(self):
        with pytest.raises(ValueError, match="Invalid"):
            parse_uri("cc://tokenonly@host.com")

    def test_missing_host(self):
        with pytest.raises(ValueError, match="Invalid"):
            parse_uri("cc://token:key@")


class TestSaveLoad:
    def test_round_trip(self, tmp_config, sample_config):
        save_config(
            sample_config["url"],
            sample_config["token"],
            sample_config["encryption_key"],
        )
        loaded = load_config()
        assert loaded["url"] == sample_config["url"]
        assert loaded["token"] == sample_config["token"]
        assert loaded["encryption_key"] == sample_config["encryption_key"]
        assert "connected_at" in loaded

    def test_file_permissions(self, tmp_config):
        save_config("https://x.com", "tok", "key")
        mode = oct(os.stat(tmp_config).st_mode & 0o777)
        assert mode == "0o600"

    def test_load_missing_file(self, tmp_config):
        result = load_config()
        assert result is None


class TestClearConfig:
    def test_clears_existing(self, tmp_config, sample_config):
        save_config(
            sample_config["url"],
            sample_config["token"],
            sample_config["encryption_key"],
        )
        clear_config()
        assert not tmp_config.exists()

    def test_clear_nonexistent_no_error(self, tmp_config):
        clear_config()
