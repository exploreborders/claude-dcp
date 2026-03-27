#!/usr/bin/env python3
"""
PostCompact hook: Re-inject context reminders after compaction.

Outputs a system message reminding Claude that context was just
pruned and to avoid redundant file reads.
"""

import json
import os
import sys

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


REMINDER = """\
[Context Refreshed — Post-Compact State]

This conversation was just compacted. The context was pruned to stay within token limits.

DCP Status:
- Previous tool outputs have been consolidated
- File contents read before compaction may need to be re-read if needed
- Tool call signatures are still tracked to prevent duplicate operations

Action items:
1. If continuing work on a task, re-read the relevant files with: `head -50 <file>` (not full file)
2. Check git status to confirm the state of the repository
3. Review any pending TODOs from the pre-compaction context
"""


def main() -> None:
    """Entry point for the PostCompact hook."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PostCompact",
            "additionalContext": REMINDER,
        }
    }
    print(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
