"""Tests for track_turn.py — dedicated UserPromptSubmit turn counter hook."""

import io
import json
import sys


class TestTrackTurn:
    def test_increments_turn_on_valid_session(self, track_turn, lib, monkeypatch, tmp_path):
        """Valid session_id causes turn counter to increment by 1."""
        monkeypatch.setattr(track_turn, "get_state_dir", lambda sid: str(tmp_path))
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": "s1"})))

        assert lib.get_turn(str(tmp_path)) == 0
        try:
            track_turn.main()
        except SystemExit:
            pass
        assert lib.get_turn(str(tmp_path)) == 1

    def test_increments_multiple_turns(self, track_turn, lib, monkeypatch, tmp_path):
        """Turn counter increments correctly across successive calls."""
        monkeypatch.setattr(track_turn, "get_state_dir", lambda sid: str(tmp_path))

        for expected in range(1, 4):
            monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": "s1"})))
            try:
                track_turn.main()
            except SystemExit:
                pass
            assert lib.get_turn(str(tmp_path)) == expected

    def test_missing_session_id_exits_cleanly(self, track_turn, monkeypatch):
        """Missing session_id exits 0 without error."""
        monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
        try:
            track_turn.main()
        except SystemExit as e:
            assert e.code == 0

    def test_empty_stdin_exits_cleanly(self, track_turn, monkeypatch):
        """Empty stdin exits 0 cleanly."""
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        try:
            track_turn.main()
        except SystemExit as e:
            assert e.code == 0

    def test_invalid_json_exits_cleanly(self, track_turn, monkeypatch):
        """Invalid JSON stdin exits 0 cleanly."""
        monkeypatch.setattr(sys, "stdin", io.StringIO("{not json}"))
        try:
            track_turn.main()
        except SystemExit as e:
            assert e.code == 0
