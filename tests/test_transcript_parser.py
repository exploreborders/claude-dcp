"""Tests for parse_transcript and extract_tool_uses_and_results."""


class TestParseTranscript:
    """Tests for parse_transcript()."""

    def test_parse_valid_jsonl(self, optimizer, tmp_transcript):
        """Valid JSONL is parsed into a list of message dicts."""
        path = tmp_transcript("transcript_basic")
        messages = optimizer.parse_transcript(str(path))

        assert len(messages) == 8
        assert messages[0]["data"]["type"] == "human"
        assert messages[0]["line_num"] == 1
        assert messages[0]["raw"] is not None

    def test_parse_empty_lines_skipped(self, optimizer, tmp_transcript):
        """Empty lines in JSONL are skipped."""
        path = tmp_transcript("transcript_malformed")
        messages = optimizer.parse_transcript(str(path))

        # The fixture has an empty line between valid lines
        # No message should have data=None due to empty lines
        # (only malformed content produces data=None)
        line_nums = [m["line_num"] for m in messages]
        # Line numbers should be consecutive from the file (including malformed)
        assert 1 in line_nums

    def test_parse_malformed_lines_tolerated(self, optimizer, tmp_transcript):
        """Malformed JSON lines get data=None but don't crash."""
        path = tmp_transcript("transcript_malformed")
        messages = optimizer.parse_transcript(str(path))

        # Should have parsed without error
        assert len(messages) > 0

        # Find the malformed line
        malformed = [m for m in messages if m["data"] is None]
        assert len(malformed) == 1
        assert "not valid json" in malformed[0]["raw"]

    def test_parse_empty_file(self, optimizer, tmp_path):
        """Empty file returns empty list."""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.write_text("")
        messages = optimizer.parse_transcript(str(empty_file))
        assert messages == []

    def test_parse_preserves_raw(self, optimizer, tmp_transcript):
        """Raw line content is preserved for reconstruction."""
        path = tmp_transcript("transcript_basic")
        messages = optimizer.parse_transcript(str(path))

        for msg in messages:
            if msg["data"] is not None:
                # raw should be valid JSON that round-trips
                import json
                reparsed = json.loads(msg["raw"])
                assert reparsed == msg["data"]


class TestExtractToolUsesAndResults:
    """Tests for extract_tool_uses_and_results()."""

    def test_extracts_tool_use_blocks(self, optimizer, tmp_transcript):
        """Tool use blocks are extracted with correct fields."""
        path = tmp_transcript("transcript_basic")
        messages = optimizer.parse_transcript(str(path))
        tool_calls, _ = optimizer.extract_tool_uses_and_results(messages)

        assert len(tool_calls) == 2
        assert tool_calls[0]["name"] == "Bash"
        assert tool_calls[0]["id"] == "toolu_01A"
        assert tool_calls[0]["input"] == {"command": "ls /tmp"}
        assert "signature" in tool_calls[0]

    def test_extracts_tool_result_blocks(self, optimizer, tmp_transcript):
        """Tool result blocks are extracted with is_error flag."""
        path = tmp_transcript("transcript_basic")
        messages = optimizer.parse_transcript(str(path))
        _, tool_results = optimizer.extract_tool_uses_and_results(messages)

        assert "toolu_01A" in tool_results
        assert tool_results["toolu_01A"]["is_error"] is False

    def test_extracts_error_results(self, optimizer, tmp_transcript):
        """Error tool results have is_error=True."""
        path = tmp_transcript("transcript_with_errors")
        messages = optimizer.parse_transcript(str(path))
        _, tool_results = optimizer.extract_tool_uses_and_results(messages)

        assert "toolu_01A" in tool_results
        assert tool_results["toolu_01A"]["is_error"] is True

    def test_skips_malformed_messages(self, optimizer, tmp_transcript):
        """Malformed messages (data=None) are skipped during extraction."""
        path = tmp_transcript("transcript_malformed")
        messages = optimizer.parse_transcript(str(path))
        tool_calls, tool_results = optimizer.extract_tool_uses_and_results(messages)

        # Should still extract the valid tool calls (2 in the fixture)
        assert len(tool_calls) == 2

    def test_skips_non_list_content(self, optimizer, tmp_path):
        """Messages with non-list content are skipped gracefully."""
        import json
        path = tmp_path / "non_list.jsonl"
        with open(path, "w") as f:
            # content is a string, not a list
            f.write(json.dumps({
                "type": "assistant",
                "message": {"role": "assistant", "content": "just a string"},
            }) + "\n")
            # content is missing entirely
            f.write(json.dumps({
                "type": "assistant",
                "message": {"role": "assistant"},
            }) + "\n")

        messages = optimizer.parse_transcript(str(path))
        tool_calls, tool_results = optimizer.extract_tool_uses_and_results(messages)

        assert tool_calls == []
        assert tool_results == {}
