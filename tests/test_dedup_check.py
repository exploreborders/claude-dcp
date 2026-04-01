"""Tests for dedup_check.py — find_recent_duplicate()."""

import json
import time

# lib.py writes entries with no spaces (separators=(",",":")); tests must match
SEP = (",", ":")


class TestFindRecentDuplicate:
    def test_entry_missing_ts_is_skipped(self, dedup_check, tmp_path):
        """Log entry without 'ts' field must not be treated as a match."""
        log_file = tmp_path / "tool-log.jsonl"
        sig = "abc123"
        entry = json.dumps({"signature": sig, "tool": "Bash", "id": "x"}, separators=SEP)
        log_file.write_text(entry + "\n")

        result = dedup_check.find_recent_duplicate(str(tmp_path), sig, window=60)
        assert result is False

    def test_entry_with_recent_ts_is_matched(self, dedup_check, tmp_path):
        """Log entry with a recent 'ts' is identified as a duplicate."""
        log_file = tmp_path / "tool-log.jsonl"
        sig = "abc123"
        entry = json.dumps({"signature": sig, "tool": "Bash", "id": "x", "ts": int(time.time())}, separators=SEP)
        log_file.write_text(entry + "\n")

        result = dedup_check.find_recent_duplicate(str(tmp_path), sig, window=60)
        assert result is True

    def test_entry_with_old_ts_is_not_matched(self, dedup_check, tmp_path):
        """Log entry older than the window is not treated as a duplicate."""
        log_file = tmp_path / "tool-log.jsonl"
        sig = "abc123"
        old_ts = int(time.time()) - 120
        entry = json.dumps({"signature": sig, "tool": "Bash", "id": "x", "ts": old_ts}, separators=SEP)
        log_file.write_text(entry + "\n")

        result = dedup_check.find_recent_duplicate(str(tmp_path), sig, window=60)
        assert result is False

    def test_no_log_file_returns_false(self, dedup_check, tmp_path):
        """Missing log file returns False cleanly."""
        result = dedup_check.find_recent_duplicate(str(tmp_path), "anysig", window=60)
        assert result is False

    def test_different_signature_not_matched(self, dedup_check, tmp_path):
        """Entry with a different signature is not matched."""
        log_file = tmp_path / "tool-log.jsonl"
        entry = json.dumps({"signature": "other_sig", "tool": "Bash", "id": "x", "ts": int(time.time())}, separators=SEP)
        log_file.write_text(entry + "\n")

        result = dedup_check.find_recent_duplicate(str(tmp_path), "target_sig", window=60)
        assert result is False
