#!/usr/bin/env python3
"""
claude-dcp shared utilities for hook scripts.

Import this module to get config loading, state management,
signature computation, and logging functions.

Cross-platform: works on macOS, Linux, and Windows (with Python 3.9+).
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

# --- Configuration ---

PLUGIN_ROOT = os.path.normpath(
    os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
    )
)
CONFIG_PATH = os.path.join(PLUGIN_ROOT, "config.json")

# Defaults
_DEFAULTS: dict[str, Any] = {
    "error_purge_turns": 4,
    "dedup_enabled": True,
    "error_purge_enabled": True,
    "context_nudge_enabled": True,
    "info_threshold_tokens": 120_000,
    "warn_threshold_tokens": 150_000,
    "urgent_threshold_tokens": 180_000,
    "duplicate_block_window_seconds": 60,
    "max_tool_log_entries": 500,
    "protected_tools": [
        "Write", "Edit", "ExitPlanMode", "TodoWrite", "AskUserQuestion", "Task",
    ],
}

# Map config keys → env var names
_ENV_MAP: dict[str, str] = {
    "error_purge_turns": "DCP_ERROR_PURGE_TURNS",
    "dedup_enabled": "DCP_DEDUP_ENABLED",
    "error_purge_enabled": "DCP_ERROR_PURGE_ENABLED",
    "context_nudge_enabled": "DCP_CONTEXT_NUDGE_ENABLED",
    "info_threshold_tokens": "DCP_INFO_THRESHOLD_TOKENS",
    "warn_threshold_tokens": "DCP_WARN_THRESHOLD_TOKENS",
    "urgent_threshold_tokens": "DCP_URGENT_THRESHOLD_TOKENS",
    "duplicate_block_window_seconds": "DCP_DUPLICATE_BLOCK_WINDOW",
    "max_tool_log_entries": "DCP_MAX_TOOL_LOG_ENTRIES",
}


def _load_config() -> dict[str, Any]:
    """Load config from config.json + env var overrides.

    Priority: env vars > config.json > defaults.
    """
    config = dict(_DEFAULTS)

    # Load from config.json
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                file_config = json.load(f)
            for key in _DEFAULTS:
                if key in file_config:
                    config[key] = file_config[key]
        except (json.JSONDecodeError, OSError):
            pass

    # Env var overrides
    for key, env_name in _ENV_MAP.items():
        if env_name not in os.environ:
            continue
        val = os.environ[env_name]
        if isinstance(_DEFAULTS[key], bool):
            config[key] = val.lower() == "true"
        elif isinstance(_DEFAULTS[key], int):
            try:
                config[key] = int(val)
            except ValueError:
                pass

    return config


CFG = _load_config()

# Convenience accessors
ERROR_PURGE_TURNS: int = CFG["error_purge_turns"]
DEDUP_ENABLED: bool = CFG["dedup_enabled"]
ERROR_PURGE_ENABLED: bool = CFG["error_purge_enabled"]
CONTEXT_NUDGE_ENABLED: bool = CFG["context_nudge_enabled"]
INFO_THRESHOLD_TOKENS: int = CFG["info_threshold_tokens"]
WARN_THRESHOLD_TOKENS: int = CFG["warn_threshold_tokens"]
URGENT_THRESHOLD_TOKENS: int = CFG["urgent_threshold_tokens"]
DUPLICATE_BLOCK_WINDOW: int = CFG["duplicate_block_window_seconds"]
MAX_TOOL_LOG_ENTRIES: int = CFG["max_tool_log_entries"]
PROTECTED_TOOLS: set[str] = set(CFG["protected_tools"])


# --- Utility Functions ---


def sanitize_session_id(session_id: str) -> str:
    """Sanitize session_id to prevent path traversal."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "", session_id)[:64]


def is_protected_tool(tool_name: str) -> bool:
    """Check if a tool is in the protected list."""
    return tool_name in PROTECTED_TOOLS


def get_state_dir(session_id: str) -> str:
    """Get or create the session state directory.

    Uses CLAUDE_PLUGIN_DATA if available, falls back to a temp-based location.
    """
    safe_id = sanitize_session_id(session_id)

    if os.environ.get("CLAUDE_PLUGIN_DATA"):
        base_dir = os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], "sessions")
    else:
        base_dir = os.path.join(os.sep, "tmp", "claude-dcp", "sessions")

    state_dir = os.path.join(base_dir, safe_id)
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    return state_dir


# --- Signature Computation ---


def _strip_nulls(obj: Any) -> Any:
    """Recursively strip null values from dicts and lists.

    Matches shell jq behavior: 'del(.. | select(. == null))'
    """
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_strip_nulls(v) for v in obj if v is not None]
    return obj


def normalize_input(tool_input: Any) -> str:
    """Normalize tool input for consistent comparison.

    Strips null values and sorts keys recursively to match
    shell compute_signature normalization (jq -cS 'del(.. | select(. == null))').
    """
    cleaned = _strip_nulls(tool_input)
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"))


def compute_signature(tool_name: str, tool_input: Any) -> str:
    """Compute a hash signature for a tool call.

    Cross-platform: uses hashlib (no shell dependencies).
    """
    normalized = normalize_input(tool_input)
    combined = f"{tool_name}:{normalized}"
    return hashlib.sha256(combined.encode()).hexdigest()


# --- Logging ---


def log_tool_call(
    state_dir: str,
    tool_name: str,
    tool_input: Any,
    tool_id: str = "",
) -> str:
    """Log a tool call to the session state file.

    Returns:
        The computed signature.
    """
    signature = compute_signature(tool_name, tool_input)
    log_file = os.path.join(state_dir, "tool-log.jsonl")
    entry = json.dumps(
        {"signature": signature, "tool": tool_name, "id": tool_id, "ts": int(time.time())},
        separators=(",", ":"),
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    return signature


def check_duplicate(state_dir: str, signature: str) -> bool:
    """Check if a tool call signature already exists in the log.

    Returns:
        True if duplicate found.
    """
    log_file = os.path.join(state_dir, "tool-log.jsonl")
    if not os.path.isfile(log_file):
        return False

    marker = f'"signature":"{signature}"'
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if marker in line:
                return True
    return False


def log_error(
    state_dir: str,
    tool_name: str,
    tool_input: Any,
    tool_id: str = "",
) -> None:
    """Log an error with turn counter."""
    turn = get_turn(state_dir)
    log_file = os.path.join(state_dir, "error-log.jsonl")
    entry = json.dumps(
        {"tool": tool_name, "id": tool_id, "turn": turn, "ts": int(time.time())},
        separators=(",", ":"),
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


# --- Turn Counter ---


def get_turn(state_dir: str) -> int:
    """Get current turn counter."""
    turn_file = os.path.join(state_dir, "turn-counter")
    if os.path.isfile(turn_file):
        try:
            return int(Path(turn_file).read_text().strip())
        except (ValueError, OSError):
            return 0
    return 0


def increment_turn(state_dir: str) -> int:
    """Increment and return the turn counter."""
    current = get_turn(state_dir)
    next_turn = current + 1
    turn_file = os.path.join(state_dir, "turn-counter")
    with open(turn_file, "w") as f:
        f.write(str(next_turn))
    return next_turn


# --- Log Trimming ---


def count_lines(file_path: str) -> int:
    """Count lines in a file safely."""
    if not os.path.isfile(file_path):
        return 0
    count = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for _ in f:
            count += 1
    return count


def trim_log_file(log_file: str, max_entries: Optional[int] = None) -> None:
    """Trim a JSONL log file to prevent unbounded growth."""
    if max_entries is None:
        max_entries = MAX_TOOL_LOG_ENTRIES
    if not os.path.isfile(log_file):
        return

    line_count = count_lines(log_file)
    if line_count > max_entries:
        keep = int(max_entries * 0.6)
        lines: list[str] = []
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(log_file, "w", encoding="utf-8") as f:
            f.writelines(lines[-keep:])


def trim_error_log(state_dir: str, max_entries: Optional[int] = None) -> None:
    """Trim error-log.jsonl to prevent unbounded growth."""
    trim_log_file(os.path.join(state_dir, "error-log.jsonl"), max_entries)
