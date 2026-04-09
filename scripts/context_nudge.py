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
    read_session_summary,
)


DEDUP_RULE = (
    "DCP rule: if a tool call is blocked as a duplicate, "
    "do NOT rephrase or vary the command to work around it — "
    "respect the block and tell the user instead."
)


def estimate_tokens(hook_input: dict) -> int:
    """Estimate token count from the hook input.

    Uses character count / 4 as a rough approximation.
    """
    transcript = hook_input.get("transcript", "")
    if transcript:
        return len(transcript.encode("utf-8")) // 4

    prompt = hook_input.get("prompt", "")
    return len(prompt.encode("utf-8")) // 4


def get_savings_summary(hook_input: dict) -> str:
    """Get a summary of cumulative token savings for this session.

    Returns an empty string if no savings have been recorded.
    """
    session_id = hook_input.get("session_id", "")
    if not session_id:
        return ""

    try:
        state_dir = get_state_dir(session_id)
        summary = read_session_summary(state_dir)
    except Exception:
        return ""

    opt = summary.get("optimization", {})
    if opt.get("optimization_count", 0) == 0:
        return ""

    bytes_saved = opt.get("total_bytes_saved", 0)
    saved = format_bytes_saved(bytes_saved)
    tokens_saved = bytes_saved // 4
    tokens_saved_str = f"~{tokens_saved:,}" if tokens_saved > 0 else "0"

    parts = [
        f"DCP: {saved} saved ({tokens_saved_str} tokens est.)",
        f"  • {opt.get('total_duplicates_removed', 0)} dups removed",
        f"  • {opt.get('total_error_inputs_purged', 0)} errors purged",
    ]
    return "\n".join(parts)


def get_nudge_message(tokens: int, savings_summary: str = ""):
    """Return a nudge message based on token count, or None if not needed."""
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

    if savings_summary:
        if base:
            return f"{base}\n{savings_summary}"
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
    nudge = get_nudge_message(tokens, savings_summary)

    context_parts = [DEDUP_RULE]
    if nudge:
        context_parts.append(nudge)

    result = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n".join(context_parts),
        }
    }
    print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
