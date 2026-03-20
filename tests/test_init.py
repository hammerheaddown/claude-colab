"""Tests for claude_colab package init."""


def test_version():
    from claude_colab import __version__
    assert __version__ == "0.1.0"


def test_lazy_import_colab_client():
    from claude_colab import ColabClient
    assert ColabClient is not None


def test_lazy_import_colab_error():
    from claude_colab import ColabError
    assert ColabError is not None


def test_invalid_attr():
    import pytest
    import claude_colab
    with pytest.raises(AttributeError):
        _ = claude_colab.NonexistentThing
