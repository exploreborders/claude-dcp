"""Tests for _deduplicate_tool_calls, _purge_error_inputs, and optimize_transcript."""

import json
import os


class TestDeduplicateToolCalls:
    """Tests for _deduplicate_tool_calls()."""

    def test_finds_duplicates(self, optimizer, tmp_transcript):
        """Duplicate tool calls (same signature) are detected."""
        path = tmp_transcript("transcript_with_dupes")
        messages = optimizer.parse_transcript(str(path))
        tool_calls, tool_results = optimizer.extract_tool_uses_and_results(messages)

        dedup_targets = optimizer._deduplicate_tool_calls(tool_calls, tool_results)

        # 3 Bash calls with same input → 2 should be deduped (keep last)
        dedupped_tool_uses = [
            t for t in dedup_targets.values() if t.get("type") == "tool_use"
        ]
        assert len(dedupped_tool_uses) == 2

    def test_keeps_last_occurrence(self, optimizer, tmp_transcript):
        """The LAST occurrence of a duplicate is kept, earlier ones deduped."""
        path = tmp_transcript("transcript_with_dupes")
        messages = optimizer.parse_transcript(str(path))
        tool_calls, tool_results = optimizer.extract_tool_uses_and_results(messages)

        dedup_targets = optimizer._deduplicate_tool_calls(tool_calls, tool_results)

        # The 3rd Bash call (toolu_03C) should NOT be in dedup targets
        dedupped_ids = {t["id"] for t in dedup_targets.values() if t.get("type") == "tool_use"}
        assert "toolu_03C" not in dedupped_ids  # last one kept
        assert "toolu_01A" in dedupped_ids       # first one deduped
        assert "toolu_02B" in dedupped_ids       # second one deduped

    def test_respects_protected_tools(self, optimizer):
        """Protected tools (Write, Edit, etc.) are never deduped."""
        tool_calls = [
            {"id": "t1", "name": "Write", "input": {"file_path": "/a", "content": "x"},
             "signature": "sig1", "msg_idx": 0, "content_idx": 0},
            {"id": "t2", "name": "Write", "input": {"file_path": "/a", "content": "x"},
             "signature": "sig1", "msg_idx": 1, "content_idx": 0},
        ]
        tool_results = {}

        dedup_targets = optimizer._deduplicate_tool_calls(tool_calls, tool_results)
        assert len(dedup_targets) == 0

    def test_no_duplicates_returns_empty(self, optimizer, tmp_transcript):
        """Transcript with no duplicates returns empty dedup targets."""
        path = tmp_transcript("transcript_basic")
        messages = optimizer.parse_transcript(str(path))
        tool_calls, tool_results = optimizer.extract_tool_uses_and_results(messages)

        dedup_targets = optimizer._deduplicate_tool_calls(tool_calls, tool_results)
        assert len(dedup_targets) == 0

    def test_empty_input(self, optimizer):
        """Empty tool_calls returns empty dedup targets."""
        dedup_targets = optimizer._deduplicate_tool_calls([], {})
        assert dedup_targets == {}

    def test_dedup_also_trims_results(self, optimizer, tmp_transcript):
        """Deduped tool calls also get their results trimmed."""
        path = tmp_transcript("transcript_with_dupes")
        messages = optimizer.parse_transcript(str(path))
        tool_calls, tool_results = optimizer.extract_tool_uses_and_results(messages)

        dedup_targets = optimizer._deduplicate_tool_calls(tool_calls, tool_results)

        # Should have both tool_use and tool_result replacements
        tool_result_replacements = [
            t for t in dedup_targets.values() if t.get("type") == "tool_result"
        ]
        assert len(tool_result_replacements) > 0
        for tr in tool_result_replacements:
            assert "deduplicated" in tr["content"].lower()


class TestPurgeErrorInputs:
    """Tests for _purge_error_inputs()."""

    def test_purges_old_errors(self, optimizer, tmp_transcript):
        """Error inputs older than N turns are purged."""
        path = tmp_transcript("transcript_with_errors")
        messages = optimizer.parse_transcript(str(path))
        tool_calls, tool_results = optimizer.extract_tool_uses_and_results(messages)

        # The error is on toolu_01A, and there are 4+ user turns after it
        error_targets = optimizer._purge_error_inputs(
            tool_calls, tool_results, messages, {}
        )

        assert len(error_targets) == 1
        target = list(error_targets.values())[0]
        assert target["name"] == "Bash"
        assert "_dcp_note" in target["input"]

    def test_skips_recent_errors(self, optimizer):
        """Recent errors (within N turns) are NOT purged."""
        # Build a transcript where error is only 1 turn old
        messages = [
            {"data": {"type": "human", "message": {"role": "user", "content": "go"}}},
            {"data": {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "fail"}}
            ]}}},
            {"data": {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "error", "is_error": True}
            ]}}},
            {"data": {"type": "human", "message": {"role": "user", "content": "next"}}},
        ]
        tool_calls = [
            {"id": "t1", "name": "Bash", "input": {"command": "fail"},
             "signature": "sig1", "msg_idx": 1, "content_idx": 0},
        ]
        tool_results = {"t1": {"msg_idx": 2, "content_idx": 0, "is_error": True}}

        error_targets = optimizer._purge_error_inputs(
            tool_calls, tool_results, messages, {}
        )
        # Only 1 turn after error, needs >= ERROR_PURGE_TURNS (default 4)
        assert len(error_targets) == 0

    def test_skips_protected_tools(self, optimizer):
        """Errors in protected tools are never purged."""
        messages = [
            {"data": {"type": "human", "message": {"role": "user", "content": "go"}}},
            {"data": {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Write", "input": {"file_path": "/a"}}
            ]}}},
            {"data": {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "error", "is_error": True}
            ]}}},
        ] + [{"data": {"type": "human", "message": {"role": "user", "content": f"turn {i}"}}} for i in range(10)]

        tool_calls = [
            {"id": "t1", "name": "Write", "input": {"file_path": "/a"},
             "signature": "sig1", "msg_idx": 1, "content_idx": 0},
        ]
        tool_results = {"t1": {"msg_idx": 2, "content_idx": 0, "is_error": True}}

        error_targets = optimizer._purge_error_inputs(
            tool_calls, tool_results, messages, {}
        )
        assert len(error_targets) == 0

    def test_skips_non_errors(self, optimizer):
        """Successful tool calls are not purged regardless of age."""
        messages = [
            {"data": {"type": "human", "message": {"role": "user", "content": "go"}}},
            {"data": {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}
            ]}}},
            {"data": {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "ok", "is_error": False}
            ]}}},
        ] + [{"data": {"type": "human", "message": {"role": "user", "content": f"turn {i}"}}} for i in range(10)]

        tool_calls = [
            {"id": "t1", "name": "Bash", "input": {"command": "ls"},
             "signature": "sig1", "msg_idx": 1, "content_idx": 0},
        ]
        tool_results = {"t1": {"msg_idx": 2, "content_idx": 0, "is_error": False}}

        error_targets = optimizer._purge_error_inputs(
            tool_calls, tool_results, messages, {}
        )
        assert len(error_targets) == 0


class TestOptimizeTranscriptEndToEnd:
    """Integration tests for optimize_transcript() with real files."""

    def test_dedup_in_real_transcript(self, optimizer, tmp_transcript):
        """Duplicate tool calls are deduped in a real transcript file."""
        path = tmp_transcript("transcript_with_dupes")
        stats = optimizer.optimize_transcript(str(path))

        assert stats["deduplicated"] == 2  # 2 of 3 Bash calls deduped
        assert stats["bytes_saved"] > 0

    def test_optimized_file_is_valid_jsonl(self, optimizer, tmp_transcript):
        """After optimization, the file is still valid JSONL."""
        path = tmp_transcript("transcript_with_dupes")
        optimizer.optimize_transcript(str(path))

        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    json.loads(line)  # should not raise

    def test_dedup_replaces_tool_use_input(self, optimizer, tmp_transcript):
        """Deduped tool_use blocks have their input replaced with empty dict."""
        path = tmp_transcript("transcript_with_dupes")
        optimizer.optimize_transcript(str(path))

        messages = optimizer.parse_transcript(str(path))
        tool_calls, _ = optimizer.extract_tool_uses_and_results(messages)

        # The first 2 Bash calls should now have empty input
        bash_calls = [tc for tc in tool_calls if tc["name"] == "Bash"]
        assert bash_calls[0]["input"] == {}
        assert bash_calls[1]["input"] == {}
        assert bash_calls[2]["input"] != {}  # last one kept

    def test_no_changes_for_clean_transcript(self, optimizer, tmp_transcript):
        """A transcript with no dupes/errors produces zero stats."""
        path = tmp_transcript("transcript_basic")
        stats = optimizer.optimize_transcript(str(path))

        assert stats["deduplicated"] == 0
        assert stats["error_inputs_purged"] == 0
        assert stats["bytes_saved"] == 0

    def test_atomic_write_no_tmp_file_left(self, optimizer, tmp_transcript):
        """No .dcp-tmp file is left after optimization."""
        path = tmp_transcript("transcript_with_dupes")
        optimizer.optimize_transcript(str(path))

        tmp_file = Path(str(path) + ".dcp-tmp")
        assert not tmp_file.exists()

    def test_error_purge_in_real_transcript(self, optimizer, tmp_transcript):
        """Old error inputs are purged in a real transcript file."""
        path = tmp_transcript("transcript_with_errors")
        stats = optimizer.optimize_transcript(str(path))

        # The error on toolu_01A should be purged (4+ turns old)
        assert stats["error_inputs_purged"] >= 1

    def test_bytes_saved_is_positive(self, optimizer, tmp_transcript):
        """Bytes saved is positive when optimization occurs."""
        path = tmp_transcript("transcript_with_dupes")
        stats = optimizer.optimize_transcript(str(path))

        assert stats["bytes_saved"] > 0


# Need Path import for the atomic write test
from pathlib import Path
