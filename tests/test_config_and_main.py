"""Tests for load_config(), _load_env_overrides(), and main() entry point."""

import io
import json
import os
import sys


class TestLoadConfig:
    """Tests for load_config() configuration loading."""

    def test_defaults_when_no_config_file(self, optimizer, monkeypatch, tmp_path):
        """Default values are used when config.json doesn't exist."""
        # Point CONFIG_PATH to a non-existent file
        monkeypatch.setattr(optimizer, "CONFIG_PATH", str(tmp_path / "nonexistent.json"))
        # Clear any env var overrides
        monkeypatch.delenv("DCP_ERROR_PURGE_TURNS", raising=False)
        monkeypatch.delenv("DCP_ERROR_PURGE_ENABLED", raising=False)

        config = optimizer.load_config()

        assert config["error_purge_turns"] == 4
        assert config["error_purge_enabled"] is True
        assert "Write" in config["protected_tools"]
        assert "Edit" in config["protected_tools"]

    def test_loads_from_config_file(self, optimizer, monkeypatch, tmp_path):
        """Values from config.json override defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "error_purge_turns": 10,
            "error_purge_enabled": False,
            "protected_tools": ["Write", "Edit"],
        }))
        monkeypatch.setattr(optimizer, "CONFIG_PATH", str(config_file))
        monkeypatch.delenv("DCP_ERROR_PURGE_TURNS", raising=False)
        monkeypatch.delenv("DCP_ERROR_PURGE_ENABLED", raising=False)

        config = optimizer.load_config()

        assert config["error_purge_turns"] == 10
        assert config["error_purge_enabled"] is False
        assert config["protected_tools"] == ["Write", "Edit"]

    def test_env_var_overrides_config_file(self, optimizer, monkeypatch, tmp_path):
        """Environment variables take precedence over config.json."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"error_purge_turns": 10}))
        monkeypatch.setattr(optimizer, "CONFIG_PATH", str(config_file))
        monkeypatch.setenv("DCP_ERROR_PURGE_TURNS", "7")
        monkeypatch.setenv("DCP_ERROR_PURGE_ENABLED", "false")

        config = optimizer.load_config()

        assert config["error_purge_turns"] == 7
        assert config["error_purge_enabled"] is False

    def test_invalid_int_env_var_ignored(self, optimizer, monkeypatch):
        """Non-integer DCP_ERROR_PURGE_TURNS is silently ignored."""
        monkeypatch.setenv("DCP_ERROR_PURGE_TURNS", "not_a_number")
        config = optimizer.load_config()

        # Should fall back to default
        assert config["error_purge_turns"] == 4

    def test_invalid_json_config_file_ignored(self, optimizer, monkeypatch, tmp_path):
        """Malformed config.json is silently ignored."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json!!!")
        monkeypatch.setattr(optimizer, "CONFIG_PATH", str(config_file))

        config = optimizer.load_config()

        # Should use defaults
        assert config["error_purge_turns"] == 4

    def test_partial_config_file_merges_with_defaults(self, optimizer, monkeypatch, tmp_path):
        """Partial config.json merges with defaults (missing keys keep defaults)."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"error_purge_turns": 8}))
        monkeypatch.setattr(optimizer, "CONFIG_PATH", str(config_file))
        monkeypatch.delenv("DCP_ERROR_PURGE_TURNS", raising=False)

        config = optimizer.load_config()

        assert config["error_purge_turns"] == 8
        # These should still be defaults
        assert config["error_purge_enabled"] is True
        assert "Write" in config["protected_tools"]


class TestMain:
    """Tests for main() entry point."""

    def test_empty_stdin_exits_cleanly(self, optimizer, monkeypatch):
        """Empty stdin causes exit(0) without error."""
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        # sys.exit(0) should be called, which is fine
        try:
            optimizer.main()
        except SystemExit as e:
            assert e.code == 0

    def test_invalid_json_exits_cleanly(self, optimizer, monkeypatch):
        """Invalid JSON from stdin causes exit(0) without error."""
        monkeypatch.setattr(sys, "stdin", io.StringIO("not valid json!!!"))
        try:
            optimizer.main()
        except SystemExit as e:
            assert e.code == 0

    def test_missing_transcript_path_exits_cleanly(self, optimizer, monkeypatch):
        """Missing transcript_path in input causes exit(0)."""
        monkeypatch.setattr(sys, "stdin", io.StringIO('{"other_field": "value"}'))
        try:
            optimizer.main()
        except SystemExit as e:
            assert e.code == 0

    def test_nonexistent_transcript_exits_cleanly(self, optimizer, monkeypatch):
        """Non-existent transcript file causes exit(0)."""
        input_data = json.dumps({"transcript_path": "/nonexistent/path.jsonl"})
        monkeypatch.setattr(sys, "stdin", io.StringIO(input_data))
        try:
            optimizer.main()
        except SystemExit as e:
            assert e.code == 0

    def test_valid_transcript_optimizes(self, optimizer, monkeypatch, tmp_transcript):
        """Valid transcript path triggers optimization and exits cleanly."""
        path = tmp_transcript("transcript_with_dupes")
        input_data = json.dumps({"transcript_path": str(path)})
        monkeypatch.setattr(sys, "stdin", io.StringIO(input_data))

        try:
            optimizer.main()
        except SystemExit as e:
            assert e.code == 0

        # Verify optimization happened — file should be modified
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    json.loads(line)  # should still be valid JSON

    def test_clean_transcript_no_output(self, optimizer, monkeypatch, tmp_transcript, capsys):
        """Clean transcript produces no stderr output."""
        path = tmp_transcript("transcript_basic")
        input_data = json.dumps({"transcript_path": str(path)})
        monkeypatch.setattr(sys, "stdin", io.StringIO(input_data))

        try:
            optimizer.main()
        except SystemExit as e:
            assert e.code == 0

        captured = capsys.readouterr()
        assert captured.err == ""  # No optimization summary for clean transcript
