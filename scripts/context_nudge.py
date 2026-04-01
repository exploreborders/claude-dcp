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
    format_bytes_saved,
    get_optimization_stats,
    get_state_dir,
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


def get_savings_summary(hook_input: dict) -> str:
    """Get a summary of cumulative token savings for this session.

    Returns an empty string if no savings have been recorded.
    """
    session_id = hook_input.get("session_id", "")
    if not session_id:
        return ""

    try:
        state_dir = get_state_dir(session_id)
        stats = get_optimization_stats(state_dir)
    except Exception:
        return ""

    if stats["optimization_count"] == 0:
        return ""

    saved = format_bytes_saved(stats["total_bytes_saved"])
    # Estimate tokens saved (rough: ~4 bytes per token)
    tokens_saved = stats["total_bytes_saved"] // 4
    tokens_saved_str = f"~{tokens_saved:,}" if tokens_saved > 0 else "0"

    parts = [
        f"DCP Savings: {saved} saved ({tokens_saved_str} tokens est.)",
        f"  • {stats['total_duplicates_removed']} duplicates removed",
        f"  • {stats['total_error_inputs_purged']} error inputs purged",
        f"  • {stats['optimization_count']} optimization(s) run",
    ]
    return "\n".join(parts)


def get_nudge_message(tokens: int, savings_summary: str = ""):
    """Return a nudge message based on token count, or None if not needed."""
    # Build base message
    if tokens >= URGENT_THRESHOLD_TOKENS:
        pct = min(100, int(tokens / 200_000 * 100))
        base = (
            f"URGENT: Context is ~{tokens:,} tokens ({pct}% of 200K limit). "
            f"Avoid reading large files. Consider /compact."
        )
    elif tokens >= WARN_THRESHOLD_TOKENS:
        pct = int(tokens / 200_000 * 100)
        base = (
            f"Context is ~{tokens:,} tokens ({pct}% of 200K limit). "
            f"Be mindful of large outputs."
        )
    elif tokens >= INFO_THRESHOLD_TOKENS:
        base = f"Context: ~{tokens:,} tokens (~{int(tokens / 200_000 * 100)}%)"
    else:
        base = None

    # Combine with savings summary if available
    if savings_summary:
        if base:
            return f"{base}\n{savings_summary}"
        # Even if below threshold, show savings if there are any
        return savings_summary

    return base


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
    savings_summary = get_savings_summary(hook_input)
    message = get_nudge_message(tokens, savings_summary)

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
