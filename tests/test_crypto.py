"""Tests for Fernet E2E encryption."""

from cryptography.fernet import Fernet, InvalidToken
import pytest

from claude_colab.crypto import decrypt, encrypt, generate_key


class TestGenerateKey:
    def test_returns_valid_fernet_key(self):
        key = generate_key()
        Fernet(key)

    def test_returns_bytes(self):
        key = generate_key()
        assert isinstance(key, bytes)

    def test_unique_each_call(self):
        assert generate_key() != generate_key()


class TestEncryptDecrypt:
    def test_round_trip(self):
        key = generate_key()
        data = {"command": "nvidia-smi", "timeout": 300}
        ciphertext = encrypt(key, data)
        assert decrypt(key, ciphertext) == data

    def test_ciphertext_is_bytes(self):
        key = generate_key()
        ciphertext = encrypt(key, {"hello": "world"})
        assert isinstance(ciphertext, bytes)

    def test_wrong_key_raises(self):
        key1 = generate_key()
        key2 = generate_key()
        ciphertext = encrypt(key1, {"secret": "data"})
        with pytest.raises(InvalidToken):
            decrypt(key2, ciphertext)

    def test_tampered_ciphertext_raises(self):
        key = generate_key()
        ciphertext = encrypt(key, {"x": 1})
        tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 0xFF])
        with pytest.raises(InvalidToken):
            decrypt(key, tampered)

    def test_empty_dict(self):
        key = generate_key()
        assert decrypt(key, encrypt(key, {})) == {}

    def test_nested_data(self):
        key = generate_key()
        data = {"result": {"stdout": "hello\nworld", "exit_code": 0}}
        assert decrypt(key, encrypt(key, data)) == data
