"""Pytest fixtures for claude-dcp tests."""

import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_module(name: str, filename: str):
    """Load a Python file as a module (handles hyphenated filenames)."""
    spec = importlib.util.spec_from_file_location(
        name,
        str(SCRIPTS_DIR / filename),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def lib():
    """Load lib.py module once for all tests."""
    return _load_module("lib", "lib.py")


@pytest.fixture(scope="session")
def optimizer():
    """Load pre-compact-optimize.py as a module (hyphenated filename workaround)."""
    return _load_module("optimizer", "pre-compact-optimize.py")


@pytest.fixture
def tmp_transcript(tmp_path):
    """Create a temporary transcript file from fixture content.

    Usage:
        def test_example(tmp_transcript):
            path = tmp_transcript("transcript_basic")
            ...
    """
    def _create(fixture_name: str) -> Path:
        src = FIXTURES_DIR / f"{fixture_name}.jsonl"
        dst = tmp_path / f"{fixture_name}.jsonl"
        shutil.copy2(src, dst)
        return dst
    return _create


@pytest.fixture
def shell_compute_signature():
    """Run shell compute_signature from lib.sh and return the hash.

    Usage:
        def test_example(shell_compute_signature):
            sig = shell_compute_signature("Bash", '{"command":"ls"}')
            assert len(sig) == 64
    """
    lib_sh = str(SCRIPTS_DIR / "lib.sh")

    def _compute(tool_name: str, tool_input_json: str) -> str:
        # Source lib.sh then call compute_signature
        cmd = f'source "{lib_sh}" && compute_signature "{tool_name}" \'{tool_input_json}\''
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            raise RuntimeError(f"Shell compute_signature failed: {result.stderr}")
        return result.stdout.strip()

    return _compute
