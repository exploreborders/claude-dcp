#!/usr/bin/env python3
"""
PostToolUse hook: Track tool call signatures for dedup detection.

Reads hook JSON from stdin, extracts tool name/input, computes signature,
and logs it to session state.
"""

import json
import os
import sys
import time

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (
    get_state_dir,
    log_tool_call,
    trim_log_file,
    write_session_summary,
)

_summary_cache_time = 0
_summary_cache_interval = 10


def _maybe_update_summary(state_dir: str) -> None:
    """Update session summary at most once per interval seconds."""
    global _summary_cache_time
    now = time.time()
    if now - _summary_cache_time >= _summary_cache_interval:
        write_session_summary(state_dir)
        _summary_cache_time = now


def main() -> None:
    """Entry point for the PostToolUse hook."""
    input_data = sys.stdin.read().strip()
    if not input_data:
        sys.exit(0)

    try:
        hook_input = json.loads(input_data)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    if not session_id:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_id = hook_input.get("tool_use_id", "")

    state_dir = get_state_dir(session_id)

    log_tool_call(state_dir, tool_name, tool_input, tool_id)

    log_file = os.path.join(state_dir, "tool-log.jsonl")
    trim_log_file(log_file)

    _maybe_update_summary(state_dir)

    sys.exit(0)


if __name__ == "__main__":
    main()
