#!/usr/bin/env python3
"""
PostToolUseFailure hook: Track errored tool calls for later purging.

Reads hook JSON from stdin, extracts tool info, logs the error
with the current turn counter for age-based purging.
"""

import json
import os
import sys

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (
    get_state_dir,
    log_error,
    trim_error_log,
)


def main() -> None:
    """Entry point for the PostToolUseFailure hook."""
    input_data = sys.stdin.read().strip()
    if not input_data:
        sys.exit(0)

    try:
        hook_input = json.loads(input_data)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    tool_name = hook_input.get("tool_name", "")
    tool_id = hook_input.get("tool_use_id", "")

    if not session_id or not tool_name:
        sys.exit(0)

    state_dir = get_state_dir(session_id)

    # Log the error with turn counter
    log_error(state_dir, tool_name, tool_id)

    # Trim error log to prevent unbounded growth
    trim_error_log(state_dir)

    sys.exit(0)


if __name__ == "__main__":
    main()
