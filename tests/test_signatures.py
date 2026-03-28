"""Tests for compute_signature."""


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

