#!/usr/bin/env python3
"""
Generate a DCP sweep report and perform manual cleanup.

This script:
- Trims tool log and error log to 60% of max entries
- Resets turn counter
- Reports what was cleaned up

Designed to be called from a skill with a single Bash command,
minimizing permission prompts to just 1 instead of 2-3.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (
    format_bytes_saved,
    get_optimization_stats,
    trim_log_file,
    trim_error_log,
    MAX_TOOL_LOG_ENTRIES,
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


def count_lines(file_path: str) -> int:
    """Count lines in a file safely."""
    if not os.path.isfile(file_path):
        return 0
    count = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for _ in f:
            count += 1
    return count


def perform_sweep(session_dir: str, full: bool = False) -> dict[str, Any]:
    """Perform the sweep operation and return stats."""
    tool_log = os.path.join(session_dir, "tool-log.jsonl")
    error_log = os.path.join(session_dir, "error-log.jsonl")
    turn_file = os.path.join(session_dir, "turn-counter")

    before_tool_count = count_lines(tool_log)
    before_error_count = count_lines(error_log)

    keep = int(MAX_TOOL_LOG_ENTRIES * 0.6)
    trim_log_file(tool_log, MAX_TOOL_LOG_ENTRIES)
    trim_error_log(session_dir, MAX_TOOL_LOG_ENTRIES)

    after_tool_count = count_lines(tool_log)
    after_error_count = count_lines(error_log)

    try:
        with open(turn_file, "w") as f:
            f.write("0")
    except OSError:
        pass

    bytes_saved = (before_tool_count - after_tool_count) * 100
    if before_error_count > after_error_count:
        bytes_saved += (before_error_count - after_error_count) * 50

    return {
        "tool_calls_before": before_tool_count,
        "tool_calls_after": after_tool_count,
        "tool_calls_trimmed": before_tool_count - after_tool_count,
        "errors_before": before_error_count,
        "errors_after": after_error_count,
        "errors_trimmed": before_error_count - after_error_count,
        "turns_reset": True,
        "bytes_saved": bytes_saved,
    }


def format_report(stats: dict[str, Any], full: bool) -> str:
    """Format the sweep results as a Markdown report."""
    bytes_saved = format_bytes_saved(stats["bytes_saved"])
    tool_trimmed = stats["tool_calls_trimmed"]
    error_trimmed = stats["errors_trimmed"]

    lines = [
        "## DCP Sweep Complete",
        "",
        f"**Bytes saved**: ~{bytes_saved}",
        "",
        "### Cleanup Results",
        "",
        f"| Action | Before | After | Trimmed |",
        f"|--------|--------|-------|---------|",
        f"| Tool log entries | {stats['tool_calls_before']} | {stats['tool_calls_after']} | {tool_trimmed} |",
        f"| Error log entries | {stats['errors_before']} | {stats['errors_after']} | {error_trimmed} |",
        f"| Turn counter | - | 0 | reset |",
        "",
    ]

    if tool_trimmed > 0 or error_trimmed > 0:
        lines.append("Logs were trimmed to 60% of maximum capacity to free up space.")
    else:
        lines.append("Logs were already within the target size. No trimming needed.")

    if full:
        lines.extend([
            "",
            "### Full Mode",
            "",
            "Full transcript optimization was requested but is handled by the",
            "PreCompact hook during `/compact`. The sweep just handles log cleanup.",
        ])

    lines.extend([
        "",
        "### Recommendation",
        "",
        "After a sweep, it's a good time to consider running `/compact` if",
        "context is still large. The compaction will work on a cleaner slate.",
    ])

    return "\n".join(lines)


def main() -> int:
    """Generate and print the sweep report."""
    full_mode = "--full" in sys.argv

    plugin_data_dir = find_plugin_data_dir()
    if not plugin_data_dir:
        print("## DCP Sweep Report", file=sys.stderr)
        print("", file=sys.stderr)
        print("No DCP session data found. This is expected if this is the first", file=sys.stderr)
        print("interaction with Claude Code in this session.", file=sys.stderr)
        return 0

    session_dir = find_latest_session_dir(plugin_data_dir)
    if not session_dir:
        print("## DCP Sweep Report", file=sys.stderr)
        print("", file=sys.stderr)
        print("DCP plugin data directory found but no sessions yet.", file=sys.stderr)
        return 0

    stats = perform_sweep(session_dir, full_mode)
    report = format_report(stats, full_mode)

    print("## DCP Sweep Report", file=sys.stdout)
    print("", file=sys.stdout)
    print(report, file=sys.stdout)

    return 0


if __name__ == "__main__":
    sys.exit(main())