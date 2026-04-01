#!/usr/bin/env python3
"""
UserPromptSubmit hook: Increment turn counter once per user message.

Runs before context_nudge.py so the turn count is current when the nudge
hook reads it. Keeping this separate means turn counting works regardless
of whether CONTEXT_NUDGE_ENABLED is true or false.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import get_state_dir, increment_turn


def main() -> None:
    """Entry point for the UserPromptSubmit turn-counter hook."""
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

    try:
        state_dir = get_state_dir(session_id)
        increment_turn(state_dir)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
