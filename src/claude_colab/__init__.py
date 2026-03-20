"""claude-colab — Give Claude Code GPU access via Google Colab."""

__version__ = "0.1.0"


def __getattr__(name):
    """Lazy imports for public API."""
    if name in ("ColabClient", "ColabError"):
        from claude_colab.client import ColabClient, ColabError
        return {"ColabClient": ColabClient, "ColabError": ColabError}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
