#!/usr/bin/env python3
"""
UserPromptSubmit hook: Estimate token usage and warn when context is large.

Outputs additional context when approaching context limits.
"""

import json
import os
import sys

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (
    CONTEXT_NUDGE_ENABLED,
    INFO_THRESHOLD_TOKENS,
    URGENT_THRESHOLD_TOKENS,
    WARN_THRESHOLD_TOKENS,
)


def estimate_tokens(hook_input: dict) -> int:
    """Estimate token count from the hook input.

    Uses character count / 4 as a rough approximation.
    """
    # Try to use transcript if available
    transcript = hook_input.get("transcript", "")
    if transcript:
        return len(transcript) // 4

    # Fallback: estimate from prompt
    prompt = hook_input.get("prompt", "")
    return len(prompt) // 4


def get_nudge_message(tokens: int):
    """Return a nudge message based on token count, or None if not needed."""
    if tokens >= URGENT_THRESHOLD_TOKENS:
        pct = min(100, int(tokens / 200_000 * 100))
        return (
            f"URGENT: Context is ~{tokens:,} tokens ({pct}% of 200K limit). "
            f"Avoid reading large files. Consider /compact."
        )
    elif tokens >= WARN_THRESHOLD_TOKENS:
        pct = int(tokens / 200_000 * 100)
        return (
            f"Context is ~{tokens:,} tokens ({pct}% of 200K limit). "
            f"Be mindful of large outputs."
        )
    elif tokens >= INFO_THRESHOLD_TOKENS:
        return f"Context: ~{tokens:,} tokens (~{int(tokens / 200_000 * 100)}%)"
    return None


def main() -> None:
    """Entry point for the UserPromptSubmit hook."""
    input_data = sys.stdin.read().strip()
    if not input_data:
        sys.exit(0)

    try:
        hook_input = json.loads(input_data)
    except json.JSONDecodeError:
        sys.exit(0)

    if not CONTEXT_NUDGE_ENABLED:
        sys.exit(0)

    tokens = estimate_tokens(hook_input)
    message = get_nudge_message(tokens)

    if message:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": message,
            }
        }
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
