"""Tests for context_nudge.py — estimate_tokens() with UTF-8 byte counting."""


class TestEstimateTokens:
    def test_ascii_content_unchanged(self, context_nudge):
        """ASCII transcript: character count and byte count are equal, result is same."""
        text = "hello world " * 100  # 1200 chars, 1200 bytes
        result = context_nudge.estimate_tokens({"transcript": text})
        assert result == len(text.encode("utf-8")) // 4

    def test_cjk_uses_byte_count(self, context_nudge):
        """CJK chars (3 bytes each) give higher estimate than character count."""
        text = "你好世界" * 100  # 400 chars, 1200 UTF-8 bytes
        result = context_nudge.estimate_tokens({"transcript": text})
        assert result == len(text.encode("utf-8")) // 4  # 300, not 100

    def test_emoji_uses_byte_count(self, context_nudge):
        """Emoji (4 bytes each) give higher estimate than character count."""
        text = "🎉" * 100  # 100 chars, 400 UTF-8 bytes
        result = context_nudge.estimate_tokens({"transcript": text})
        assert result == len(text.encode("utf-8")) // 4  # 100, not 25

    def test_fallback_to_prompt_uses_bytes(self, context_nudge):
        """Fallback to 'prompt' field also uses UTF-8 byte count."""
        text = "你好" * 50  # 100 chars, 300 bytes
        result = context_nudge.estimate_tokens({"prompt": text})
        assert result == len(text.encode("utf-8")) // 4

    def test_empty_input_returns_zero(self, context_nudge):
        """Empty hook input returns 0."""
        assert context_nudge.estimate_tokens({}) == 0
