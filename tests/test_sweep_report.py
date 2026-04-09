"""Tests for sweep_report.py."""

import json
import os
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
def sweep_report():
    return _load_module("sweep_report", "sweep_report.py")


class TestPerformSweep:
    def test_trims_tool_log(self, sweep_report, tmp_path):
        tool_log = tmp_path / "tool-log.jsonl"
        with open(tool_log, "w") as f:
            for i in range(600):
                f.write('{"sig":"' + str(i) + '"}\n')

        result = sweep_report.perform_sweep(str(tmp_path))
        assert result["tool_calls_trimmed"] > 0
        assert result["tool_calls_after"] < result["tool_calls_before"]

    def test_resets_turn_counter(self, sweep_report, tmp_path):
        turn_file = tmp_path / "turn-counter"
        turn_file.write_text("10")

        result = sweep_report.perform_sweep(str(tmp_path))
        assert result["turns_reset"] is True

        new_turn = turn_file.read_text().strip()
        assert new_turn == "0"


class TestFormatReport:
    def test_includes_cleanup_results(self, sweep_report):
        stats = {
            "tool_calls_before": 100,
            "tool_calls_after": 60,
            "tool_calls_trimmed": 40,
            "errors_before": 10,
            "errors_after": 6,
            "errors_trimmed": 4,
            "turns_reset": True,
            "bytes_saved": 1000,
        }
        report = sweep_report.format_report(stats, full=False)
        assert "40" in report
        assert "4" in report

    def test_full_mode_adds_note(self, sweep_report):
        stats = {
            "tool_calls_before": 10,
            "tool_calls_after": 10,
            "tool_calls_trimmed": 0,
            "errors_before": 2,
            "errors_after": 2,
            "errors_trimmed": 0,
            "turns_reset": True,
            "bytes_saved": 0,
        }
        report = sweep_report.format_report(stats, full=True)
        assert "Full Mode" in report


class TestMain:
    def test_exits_cleanly_with_no_data(self, sweep_report, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(sweep_report, "find_plugin_data_dir", lambda: None)
        result = sweep_report.main()
        assert result == 0
        output = capsys.readouterr()
        assert "No DCP session data found" in output.err