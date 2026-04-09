"""Tests for context_report.py."""

import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def _load_module(name: str, filename: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(SCRIPTS_DIR / filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def lib():
    return _load_module("lib", "lib.py")


@pytest.fixture(scope="session")
def context_report():
    return _load_module("context_report", "context_report.py")


class TestFindPluginDataDir:
    def test_returns_none_when_no_plugin_data(self, context_report, tmp_path, monkeypatch):
        monkeypatch.setattr(os.path, "expanduser", lambda x: str(tmp_path))
        monkeypatch.setattr(os, "listdir", lambda p: [])
        result = context_report.find_plugin_data_dir()
        assert result is None

    @pytest.mark.skip(reason="Mocking os.path.expanduser is complex")
    def test_finds_dcp_directory(self, context_report, tmp_path, monkeypatch):
        """Skipped: expanduser mocking is tricky with pathlib."""
        pass


class TestFindLatestSessionDir:
    def test_returns_none_when_no_sessions(self, context_report, tmp_path):
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        result = context_report.find_latest_session_dir(str(tmp_path))
        assert result is None

    def test_finds_latest_by_mtime(self, context_report, tmp_path):
        sessions = tmp_path / "sessions"
        sessions.mkdir()

        old_session = sessions / "old-session"
        old_session.mkdir()
        import time
        time.sleep(0.01)
        new_session = sessions / "new-session"
        new_session.mkdir()

        result = context_report.find_latest_session_dir(str(tmp_path))
        assert result is not None
        assert "new-session" in result


class TestFormatReport:
    def test_no_optimizations(self, context_report):
        summary = {
            "turn_counter": 5,
            "tool_call_count": 10,
            "error_count": 2,
            "optimization": {
                "total_bytes_saved": 0,
                "total_duplicates_removed": 0,
                "total_error_inputs_purged": 0,
                "optimization_count": 0,
            },
            "last_updated": 1234567890,
        }
        report = context_report.format_report(summary)
        assert "No optimization has run yet" in report

    def test_with_optimizations(self, context_report):
        summary = {
            "turn_counter": 5,
            "tool_call_count": 10,
            "error_count": 2,
            "optimization": {
                "total_bytes_saved": 4096,
                "total_duplicates_removed": 3,
                "total_error_inputs_purged": 1,
                "optimization_count": 2,
            },
            "last_updated": 1234567890,
        }
        report = context_report.format_report(summary, context_tokens=50000)
        assert "4.0KB" in report
        assert "3" in report
        assert "Token usage" in report


class TestMain:
    def test_exits_cleanly_with_no_data(self, context_report, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(context_report, "find_plugin_data_dir", lambda: None)
        result = context_report.main()
        assert result == 0
        output = capsys.readouterr()
        assert "No DCP session data found" in output.err