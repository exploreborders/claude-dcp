"""Pytest fixtures for claude-dcp tests."""

import importlib.util
import shutil
from pathlib import Path

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



