#!/usr/bin/env python3
"""
Generate a DCP context report for the current session.

This script outputs a formatted Markdown report showing:
- Token savings summary
- Session statistics
- Recommendations

Designed to be called from a skill with a single Bash command,
minimizing permission prompts to just 1 instead of 4-6.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (
    format_bytes_saved,
    read_session_summary,
    get_state_dir,
)


PLUGIN_ROOT = os.path.normpath(
    os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
    )
)


def find_plugin_data_dir() -> Optional[str]:
    """Find the DCP plugin data directory."""
    base_paths = [
        os.path.expanduser("~/.claude/plugins/data"),
        os.path.join(PLUGIN_ROOT, ".cache"),
    ]

    for base in base_paths:
        if not os.path.isdir(base):
            continue
        for entry in os.listdir(base):
            if "dcp" in entry.lower():
                return os.path.join(base, entry)
    return None


def find_latest_session_dir(plugin_data_dir: str) -> Optional[str]:
    """Find the most recent session directory."""
    sessions_dir = os.path.join(plugin_data_dir, "sessions")
    if not os.path.isdir(sessions_dir):
        return None

    sessions = []
    for entry in os.listdir(sessions_dir):
        session_path = os.path.join(sessions_dir, entry)
        if os.path.isdir(session_path):
            mtime = os.path.getmtime(session_path)
            sessions.append((mtime, entry))

    if not sessions:
        return None

    sessions.sort(key=lambda x: x[0], reverse=True)
    return os.path.join(sessions_dir, sessions[0][1])


def get_transcript_path(session_dir: str) -> Optional[str]:
    """Get the transcript path for a session if available."""
    for name in ["transcript.jsonl", "transcript.json", "transcript"]:
        path = os.path.join(session_dir, name)
        if os.path.isfile(path):
            return path
    return None


def estimate_context_size(session_dir: str) -> int:
    """Estimate context size in tokens from transcript file."""
    transcript = get_transcript_path(session_dir)
    if not transcript or not os.path.isfile(transcript):
        return 0

    try:
        size = os.path.getsize(transcript)
        return size // 4
    except OSError:
        return 0


def format_report(summary: dict[str, Any], context_tokens: int = 0) -> str:
    """Format the session summary as a Markdown report."""
    opt = summary.get("optimization", {})
    turn_count = summary.get("turn_counter", 0)
    tool_count = summary.get("tool_call_count", 0)
    error_count = summary.get("error_count", 0)

    bytes_saved = opt.get("total_bytes_saved", 0)
    tokens_saved = bytes_saved // 4
    dupes_removed = opt.get("total_duplicates_removed", 0)
    errors_purged = opt.get("total_error_inputs_purged", 0)
    opt_count = opt.get("optimization_count", 0)

    saved_str = format_bytes_saved(bytes_saved)
    pct = min(100, int(context_tokens / 200_000 * 100)) if context_tokens else 0

    lines = [
        "## Token Savings Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Total bytes saved** | {saved_str} |",
        f"| **Estimated tokens saved** | ~{tokens_saved:,} |",
        f"| **Total duplicates removed** | {dupes_removed} |",
        f"| **Total error inputs purged** | {errors_purged} |",
        f"| **Number of optimizations run** | {opt_count} |",
        "",
        "## Session Statistics",
        "",
        f"| Stat | Value |",
        f"|------|-------|",
        f"| Turn count | {turn_count} |",
        f"| Tool calls logged | {tool_count} |",
        f"| Errored tool inputs | {error_count} |",
        "",
    ]

    if opt_count == 0:
        lines.extend([
            "## Recommendation",
            "",
            "No optimization has run yet in this session. Token savings will appear",
            "after the first `/compact` operation triggers the PreCompact hook.",
            "",
        ])
    else:
        lines.extend([
            "## Recommendation",
            "",
            f"**Token usage**: ~{pct}% of 200K limit. ",
        ])
        if pct >= 75:
            lines.append("Consider running `/compact` to free up context space.")
        elif pct >= 50:
            lines.append("Context is moderate — continue working, but watch for large outputs.")
        else:
            lines.append("Context is healthy — no action needed.")

    return "\n".join(lines)


def main() -> int:
    """Generate and print the context report."""
    plugin_data_dir = find_plugin_data_dir()
    if not plugin_data_dir:
        print("## DCP Context Report", file=sys.stderr)
        print("", file=sys.stderr)
        print("No DCP session data found. This is expected if this is the first", file=sys.stderr)
        print("interaction with Claude Code in this session.", file=sys.stderr)
        return 0

    session_dir = find_latest_session_dir(plugin_data_dir)
    if not session_dir:
        print("## DCP Context Report", file=sys.stderr)
        print("", file=sys.stderr)
        print("DCP plugin data directory found but no sessions yet.", file=sys.stderr)
        return 0

    summary = read_session_summary(session_dir)
    context_tokens = estimate_context_size(session_dir)
    report = format_report(summary, context_tokens)

    print("## DCP Context Report", file=sys.stdout)
    print("", file=sys.stdout)
    print(report, file=sys.stdout)

    return 0


if __name__ == "__main__":
    sys.exit(main())