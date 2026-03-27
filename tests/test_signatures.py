"""Tests for compute_signature, including cross-language consistency."""

import json
import hashlib


class TestComputeSignature:
    """Tests for Python compute_signature()."""

    def test_deterministic(self, lib):
        """Same input always produces the same hash."""
        sig1 = lib.compute_signature("Bash", {"command": "ls"})
        sig2 = lib.compute_signature("Bash", {"command": "ls"})
        assert sig1 == sig2

    def test_valid_sha256(self, lib):
        """Output is a 64-character hex string (SHA-256)."""
        sig = lib.compute_signature("Read", {"file_path": "/tmp"})
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_different_tools_different_signatures(self, lib):
        """Different tool names produce different signatures."""
        sig_bash = lib.compute_signature("Bash", {"command": "ls"})
        sig_read = lib.compute_signature("Read", {"command": "ls"})
        assert sig_bash != sig_read

    def test_different_inputs_different_signatures(self, lib):
        """Different inputs produce different signatures."""
        sig1 = lib.compute_signature("Bash", {"command": "ls"})
        sig2 = lib.compute_signature("Bash", {"command": "pwd"})
        assert sig1 != sig2

    def test_nulls_ignored(self, lib):
        """Presence/absence of null values doesn't change signature."""
        sig_with = lib.compute_signature("Bash", {"command": "ls", "timeout": None})
        sig_without = lib.compute_signature("Bash", {"command": "ls"})
        assert sig_with == sig_without

    def test_key_order_irrelevant(self, lib):
        """Key order in input doesn't affect signature (JSON is sorted)."""
        sig1 = lib.compute_signature("Bash", {"command": "ls", "timeout": 30})
        sig2 = lib.compute_signature("Bash", {"timeout": 30, "command": "ls"})
        assert sig1 == sig2


class TestCrossLanguageSignature:
    """Critical: shell and Python must produce identical signatures."""

    def test_shell_python_match_simple(self, lib, shell_compute_signature):
        """Shell and Python produce same signature for simple input."""
        tool_input = {"command": "ls -la"}
        python_sig = lib.compute_signature("Bash", tool_input)
        shell_sig = shell_compute_signature("Bash", json.dumps(tool_input))
        assert python_sig == shell_sig, (
            f"Signature mismatch!\nPython: {python_sig}\nShell:  {shell_sig}"
        )

    def test_shell_python_match_with_null(self, lib, shell_compute_signature):
        """Shell and Python both strip nulls identically."""
        tool_input = {"command": "ls", "timeout": None}
        python_sig = lib.compute_signature("Bash", tool_input)
        shell_sig = shell_compute_signature("Bash", json.dumps(tool_input))
        assert python_sig == shell_sig, (
            f"Null-handling mismatch!\nPython: {python_sig}\nShell:  {shell_sig}"
        )

    def test_shell_python_match_nested(self, lib, shell_compute_signature):
        """Shell and Python match for nested input with nulls."""
        tool_input = {
            "pattern": "TODO",
            "path": ".",
            "include": "*.py",
            "extra": {"deep": None, "value": 42},
        }
        python_sig = lib.compute_signature("Grep", tool_input)
        shell_sig = shell_compute_signature("Grep", json.dumps(tool_input))
        assert python_sig == shell_sig, (
            f"Nested mismatch!\nPython: {python_sig}\nShell:  {shell_sig}"
        )

    def test_shell_python_match_key_order(self, lib, shell_compute_signature):
        """Shell and Python both normalize key order."""
        tool_input_ordered = {"command": "ls", "timeout": 30}
        tool_input_reversed = {"timeout": 30, "command": "ls"}

        python_sig1 = lib.compute_signature("Bash", tool_input_ordered)
        python_sig2 = lib.compute_signature("Bash", tool_input_reversed)
        shell_sig = shell_compute_signature("Bash", json.dumps(tool_input_ordered))

        assert python_sig1 == python_sig2 == shell_sig
