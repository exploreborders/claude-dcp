#!/usr/bin/env python3
"""
PreToolUse hook: Block duplicate tool calls within the time window.

Reads hook JSON from stdin, computes signature of the tool call,
checks if it was already made within the block window,
and blocks (permissionDecision: deny) if a duplicate is found.
"""

import json
import os
import sys
import time

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (
    DEDUP_ENABLED,
    DUPLICATE_BLOCK_WINDOW,
    PROTECTED_TOOLS,
    compute_signature,
    get_state_dir,
)


def find_recent_duplicate(state_dir: str, signature: str, window: int) -> bool:
    """Check if a duplicate exists within the time window.

    Args:
        state_dir: Session state directory.
        signature: Tool call signature to check.
        window: Time window in seconds.

    Returns:
        True if a recent duplicate was found.
    """
    log_file = os.path.join(state_dir, "tool-log.jsonl")
    if not os.path.isfile(log_file):
        return False

    marker = f'"signature":"{signature}"'
    now = time.time()

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if marker not in line:
                continue
            try:
                entry = json.loads(line.strip())
                if now - entry.get("ts", 0) < window:
                    return True
            except (json.JSONDecodeError, KeyError):
                continue

    return False


def main() -> None:
    """Entry point for the PreToolUse hook."""
    input_data = sys.stdin.read().strip()
    if not input_data:
        sys.exit(0)

    try:
        hook_input = json.loads(input_data)
    except json.JSONDecodeError:
        sys.exit(0)

    if not DEDUP_ENABLED:
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if not session_id or not tool_name:
        sys.exit(0)

    # Skip protected tools
    if tool_name in PROTECTED_TOOLS:
        sys.exit(0)

    state_dir = get_state_dir(session_id)
    signature = compute_signature(tool_name, tool_input)

    if find_recent_duplicate(state_dir, signature, DUPLICATE_BLOCK_WINDOW):
        # Output decision to block the tool call
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Duplicate tool call blocked — identical {tool_name} call "
                    f"within the last {DUPLICATE_BLOCK_WINDOW}s. Use a different approach."
                ),
            }
        }
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
