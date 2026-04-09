"""Tests for cumulative optimization stats tracking."""

import json


class TestOptimizationStats:
    """Tests for get_optimization_stats() and update_optimization_stats()."""

    def test_initial_stats_are_zero(self, lib, tmp_path):
        """New session starts with zero stats."""
        stats = lib.get_optimization_stats(str(tmp_path))

        assert stats["total_bytes_saved"] == 0
        assert stats["total_duplicates_removed"] == 0
        assert stats["total_error_inputs_purged"] == 0
        assert stats["optimization_count"] == 0

    def test_update_stats_accumulates(self, lib, tmp_path):
        """Stats accumulate across multiple updates."""
        state_dir = str(tmp_path)

        # First optimization
        lib.update_optimization_stats(state_dir, {
            "bytes_saved": 1024,
            "deduplicated": 2,
            "error_inputs_purged": 1,
        })

        stats = lib.get_optimization_stats(state_dir)
        assert stats["total_bytes_saved"] == 1024
        assert stats["total_duplicates_removed"] == 2
        assert stats["total_error_inputs_purged"] == 1
        assert stats["optimization_count"] == 1

        # Second optimization
        lib.update_optimization_stats(state_dir, {
            "bytes_saved": 2048,
            "deduplicated": 3,
            "error_inputs_purged": 0,
        })

        stats = lib.get_optimization_stats(state_dir)
        assert stats["total_bytes_saved"] == 3072
        assert stats["total_duplicates_removed"] == 5
        assert stats["total_error_inputs_purged"] == 1
        assert stats["optimization_count"] == 2

    def test_stats_file_is_valid_json(self, lib, tmp_path):
        """Stats file is written as valid JSON."""
        state_dir = str(tmp_path)
        lib.update_optimization_stats(state_dir, {
            "bytes_saved": 500,
            "deduplicated": 1,
            "error_inputs_purged": 0,
        })

        stats_file = tmp_path / "optimization-stats.json"
        assert stats_file.exists()

        with open(stats_file) as f:
            data = json.load(f)

        assert "total_bytes_saved" in data
        assert "total_duplicates_removed" in data
        assert "total_error_inputs_purged" in data
        assert "optimization_count" in data

    def test_corrupted_stats_file_resets(self, lib, tmp_path):
        """Corrupted stats file is handled gracefully."""
        stats_file = tmp_path / "optimization-stats.json"
        stats_file.write_text("{invalid json!!!")

        stats = lib.get_optimization_stats(str(tmp_path))
        assert stats["total_bytes_saved"] == 0
        assert stats["optimization_count"] == 0

    def test_update_with_zero_stats_increments_count(self, lib, tmp_path):
        """Even zero-stats runs increment the optimization count."""
        state_dir = str(tmp_path)
        lib.update_optimization_stats(state_dir, {
            "bytes_saved": 0,
            "deduplicated": 0,
            "error_inputs_purged": 0,
        })

        stats = lib.get_optimization_stats(state_dir)
        assert stats["optimization_count"] == 1


class TestFormatBytesSaved:
    """Tests for format_bytes_saved()."""

    def test_bytes_format(self, lib):
        """Bytes under 1KB are shown as B."""
        assert lib.format_bytes_saved(500) == "500B"
        assert lib.format_bytes_saved(0) == "0B"
        assert lib.format_bytes_saved(1023) == "1023B"

    def test_kilobytes_format(self, lib):
        """Bytes between 1KB and 1MB are shown as KB."""
        assert lib.format_bytes_saved(1024) == "1.0KB"
        assert lib.format_bytes_saved(1536) == "1.5KB"
        assert lib.format_bytes_saved(10240) == "10.0KB"

    def test_megabytes_format(self, lib):
        """Bytes over 1MB are shown as MB."""
        assert lib.format_bytes_saved(1048576) == "1.0MB"
        assert lib.format_bytes_saved(1572864) == "1.5MB"


class TestSavingsSummary:
    """Tests for get_savings_summary() in context_nudge.py."""

    def test_no_session_id_returns_empty(self, context_nudge):
        """Empty session_id returns empty string."""
        result = context_nudge.get_savings_summary({})
        assert result == ""

    def test_no_stats_returns_empty(self, context_nudge, monkeypatch, tmp_path):
        """Session with no stats returns empty string."""
        monkeypatch.setattr(context_nudge, "get_state_dir", lambda sid: str(tmp_path))

        result = context_nudge.get_savings_summary({"session_id": "test"})
        assert result == ""

    def test_savings_summary_format(self, context_nudge, lib, monkeypatch, tmp_path):
        """Savings summary includes all expected information."""
        lib.update_optimization_stats(str(tmp_path), {
            "bytes_saved": 4096,
            "deduplicated": 3,
            "error_inputs_purged": 1,
        })
        monkeypatch.setattr(context_nudge, "get_state_dir", lambda sid: str(tmp_path))

        result = context_nudge.get_savings_summary({"session_id": "test"})
        assert "DCP:" in result
        assert "4.0KB saved" in result
        assert "3 dups removed" in result
        assert "1 errors purged" in result
