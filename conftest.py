"""Root conftest — shared fixtures for the entire test suite."""
import os
import pytest


def _config_writable() -> bool:
    """Check if config/org.yaml is writable (sandbox-safe)."""
    config_path = os.path.join(
        os.path.dirname(__file__), "config", "org.yaml"
    )
    return os.access(config_path, os.W_OK)


def _nexus_dir_writable() -> bool:
    """Check if ~/.nexus/ is writable."""
    return os.access(os.path.expanduser("~/.nexus"), os.W_OK | os.X_OK) if os.path.exists(os.path.expanduser("~/.nexus")) else os.access(os.path.expanduser("~"), os.W_OK)


needs_writable_config = pytest.mark.skipif(
    not _config_writable(),
    reason="config/org.yaml is not writable in this environment (sandboxed CI)",
)

needs_writable_nexus = pytest.mark.skipif(
    not _nexus_dir_writable(),
    reason="~/.nexus/ is not writable in this environment (sandboxed CI)",
)
