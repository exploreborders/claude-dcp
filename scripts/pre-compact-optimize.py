#!/usr/bin/env python3
"""
PreCompact hook: Optimize transcript before compaction.

Reads the transcript JSONL file and:
1. Deduplicates tool outputs (keeps the last result for identical tool calls)
2. Purges inputs from errored tools older than N turns
3. Writes the optimized transcript back

This runs BEFORE compaction, so Claude Code reads the pruned version.
"""

import json
import os
import sys
from collections import defaultdict
from typing import Any

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import (
    ERROR_PURGE_ENABLED,
    ERROR_PURGE_TURNS,
    PROTECTED_TOOLS,
    compute_signature,
)


def parse_transcript(transcript_path: str) -> list[dict[str, Any]]:
    """Parse JSONL transcript into structured messages."""
    messages: list[dict[str, Any]] = []
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                messages.append({"line_num": line_num, "data": msg, "raw": line})
            except json.JSONDecodeError:
                messages.append({"line_num": line_num, "data": None, "raw": line})
    return messages


def extract_tool_uses_and_results(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Extract all tool_use and tool_result blocks from the transcript.

    Returns:
        tool_calls: list of {id, name, input, signature, msg_idx, content_idx}
        tool_results: dict of tool_use_id -> {msg_idx, content_idx, is_error}
    """
    tool_calls: list[dict[str, Any]] = []
    tool_results: dict[str, dict[str, Any]] = {}

    for msg_idx, msg in enumerate(messages):
        data = msg["data"]
        if data is None:
            continue

        message = data.get("message", {})
        content = message.get("content", [])

        if not isinstance(content, list):
            continue

        _extract_from_content(content, msg_idx, tool_calls, tool_results)

    return tool_calls, tool_results


def _extract_from_content(
    content: list[Any],
    msg_idx: int,
    tool_calls: list[dict[str, Any]],
    tool_results: dict[str, dict[str, Any]],
) -> None:
    """Extract tool_use and tool_result blocks from a message content array."""
    for content_idx, block in enumerate(content):
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if block_type == "tool_use":
            tool_name = block.get("name", "")
            tool_input = block.get("input", {})
            tool_id = block.get("id", "")
            signature = compute_signature(tool_name, tool_input)
            tool_calls.append({
                "id": tool_id,
                "name": tool_name,
                "input": tool_input,
                "signature": signature,
                "msg_idx": msg_idx,
                "content_idx": content_idx,
            })
        elif block_type == "tool_result":
            tool_use_id = block.get("tool_use_id", "")
            if tool_use_id:
                tool_results[tool_use_id] = {
                    "msg_idx": msg_idx,
                    "content_idx": content_idx,
                    "is_error": block.get("is_error", False),
                }


def count_turns_between(messages: list[dict[str, Any]], idx1: int, idx2: int) -> int:
    """Count user messages (turns) between two transcript indices."""
    count = 0
    for i in range(min(idx1, idx2), max(idx1, idx2) + 1):
        data = messages[i].get("data")
        if data and data.get("type") == "human":
            count += 1
    return count


def _deduplicate_tool_calls(
    tool_calls: list[dict[str, Any]],
    tool_results: dict[str, dict[str, Any]],
) -> dict[tuple[int, int], dict[str, Any]]:
    """Phase 1: Find duplicate tool calls and create replacement targets.

    Groups tool calls by signature, keeps the last occurrence,
    and marks earlier ones for deduplication.
    """
    sig_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tc in tool_calls:
        sig_groups[tc["signature"]].append(tc)

    dedup_targets: dict[tuple[int, int], dict[str, Any]] = {}

    for _sig, calls in sig_groups.items():
        if len(calls) <= 1:
            continue

        # Sort by position in transcript (keep the LAST one)
        calls.sort(key=lambda c: (c["msg_idx"], c["content_idx"]))

        for call in calls[:-1]:
            if call["name"] in PROTECTED_TOOLS:
                continue

            dedup_targets[(call["msg_idx"], call["content_idx"])] = {
                "type": "tool_use",
                "id": call["id"],
                "name": call["name"],
                "input": {},
            }

            # Also mark the corresponding result for trimming
            result_info = tool_results.get(call["id"])
            if result_info:
                result_key = (result_info["msg_idx"], result_info["content_idx"])
                if result_key not in dedup_targets:
                    dedup_targets[result_key] = {
                        "type": "tool_result",
                        "tool_use_id": call["id"],
                        "content": "[Output deduplicated — identical to a later tool call]",
                        "is_error": False,
                    }

    return dedup_targets


def _purge_error_inputs(
    tool_calls: list[dict[str, Any]],
    tool_results: dict[str, dict[str, Any]],
    messages: list[dict[str, Any]],
    dedup_targets: dict[tuple[int, int], dict[str, Any]],
) -> dict[tuple[int, int], dict[str, Any]]:
    """Phase 2: Purge inputs from errored tools older than N turns.

    Only purges the input, not the error output (preserves error context).
    """
    error_targets: dict[tuple[int, int], dict[str, Any]] = {}
    last_msg_idx = len(messages) - 1

    for tc in tool_calls:
        result_info = tool_results.get(tc["id"])
        if not result_info or not result_info.get("is_error"):
            continue
        if tc["name"] in PROTECTED_TOOLS:
            continue

        turn_age = count_turns_between(messages, result_info["msg_idx"], last_msg_idx)
        if turn_age >= ERROR_PURGE_TURNS:
            key = (tc["msg_idx"], tc["content_idx"])
            if key not in dedup_targets:
                error_targets[key] = {
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": {"_dcp_note": f"input removed — error occurred {turn_age} turns ago"},
                }

    return error_targets


def _apply_transcript_changes(
    messages: list[dict[str, Any]],
    dedup_targets: dict[tuple[int, int], dict[str, Any]],
    transcript_path: str,
) -> int:
    """Phase 3: Apply dedup/purge changes and write optimized transcript.

    Uses atomic write (write to .tmp, then os.replace) to prevent corruption.

    Returns:
        Number of bytes saved.
    """
    bytes_saved = 0

    for (msg_idx, content_idx), replacement in dedup_targets.items():
        data = messages[msg_idx]["data"]
        if data is None:
            continue
        content = data.get("message", {}).get("content", [])
        if content_idx < len(content):
            original_size = len(json.dumps(content[content_idx]))
            replacement_size = len(json.dumps(replacement))
            bytes_saved += max(0, original_size - replacement_size)

            content[content_idx] = replacement
            messages[msg_idx]["raw"] = json.dumps(data, separators=(",", ":"))

    # Atomic write: write to .tmp then replace
    tmp_path = f"{transcript_path}.dcp-tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(msg["raw"])
                f.write("\n")
        os.replace(tmp_path, transcript_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return bytes_saved


def optimize_transcript(transcript_path: str) -> dict[str, int]:
    """Optimize a transcript JSONL file.

    Runs three phases:
    1. Deduplication of identical tool calls
    2. Error input purging for old failed calls
    3. Apply changes with atomic write

    Returns a dict with optimization stats.
    """
    messages = parse_transcript(transcript_path)
    tool_calls, tool_results = extract_tool_uses_and_results(messages)

    stats: dict[str, int] = {
        "total_tool_calls": len(tool_calls),
        "deduplicated": 0,
        "error_inputs_purged": 0,
        "bytes_saved": 0,
    }

    # Phase 1: Deduplication
    dedup_targets = _deduplicate_tool_calls(tool_calls, tool_results)
    stats["deduplicated"] = len([
        t for t in dedup_targets.values() if t.get("type") == "tool_use"
    ])

    # Phase 2: Error Input Purging
    if ERROR_PURGE_ENABLED:
        error_targets = _purge_error_inputs(tool_calls, tool_results, messages, dedup_targets)
        dedup_targets.update(error_targets)
        stats["error_inputs_purged"] = len(error_targets)

    # Phase 3: Apply Changes
    if not dedup_targets:
        return stats

    stats["bytes_saved"] = _apply_transcript_changes(messages, dedup_targets, transcript_path)

    return stats


def main() -> None:
    """Entry point for the PreCompact hook."""
    input_data = sys.stdin.read().strip()
    if not input_data:
        sys.exit(0)

    try:
        hook_input = json.loads(input_data)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path or not os.path.exists(transcript_path):
        sys.exit(0)

    try:
        stats = optimize_transcript(transcript_path)
    except Exception as e:
        # Don't block compaction on errors — just log and continue
        print(f"claude-dcp: transcript optimization error: {e}", file=sys.stderr)
        sys.exit(0)

    if stats["deduplicated"] > 0 or stats["error_inputs_purged"] > 0:
        saved_kb = stats["bytes_saved"] / 1024
        summary = (
            f"claude-dcp: optimized transcript — "
            f"{stats['deduplicated']} duplicates removed, "
            f"{stats['error_inputs_purged']} error inputs purged, "
            f"~{saved_kb:.1f}KB saved"
        )
        print(summary, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
