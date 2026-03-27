#!/usr/bin/env python3
"""
SessionEnd hook: Trim state files and reset turn counter.

Performs cleanup at session end to prevent state files from growing unbounded.
"""

import json
import os
import sys

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (
    get_state_dir,
    trim_error_log,
    trim_log_file,
)


def main() -> None:
    """Entry point for the SessionEnd hook."""
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

    state_dir = get_state_dir(session_id)

    # Trim logs
    trim_log_file(os.path.join(state_dir, "tool-log.jsonl"))
    trim_error_log(state_dir)

    # Reset turn counter
    turn_file = os.path.join(state_dir, "turn-counter")
    try:
        with open(turn_file, "w") as f:
            f.write("0")
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
