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
import hashlib
from collections import defaultdict
from pathlib import Path

# Configuration
ERROR_PURGE_TURNS = int(os.environ.get("DCP_ERROR_PURGE_TURNS", "4"))
PROTECTED_TOOLS = {"Write", "Edit", "ExitPlanMode", "TodoWrite", "AskUserQuestion", "Task"}


def normalize_input(tool_input):
    """Normalize tool input for consistent comparison."""
    return json.dumps(tool_input, sort_keys=True, separators=(",", ":"))


def compute_signature(tool_name, tool_input):
    """Compute a hash signature for a tool call."""
    normalized = normalize_input(tool_input)
    combined = f"{tool_name}:{normalized}"
    return hashlib.sha256(combined.encode()).hexdigest()


def parse_transcript(transcript_path):
    """Parse JSONL transcript into structured messages."""
    messages = []
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


def extract_tool_uses_and_results(messages):
    """
    Extract all tool_use and tool_result blocks from the transcript.
    Returns:
        tool_calls: list of {id, name, input, signature, msg_idx, content_idx}
        tool_results: dict of tool_use_id -> {msg_idx, content_idx}
    """
    tool_calls = []
    tool_results = {}

    for msg_idx, msg in enumerate(messages):
        data = msg["data"]
        if data is None:
            continue

        msg_type = data.get("type", "")
        message = data.get("message", {})
        content = message.get("content", [])

        if not isinstance(content, list):
            continue

        for content_idx, block in enumerate(content):
            if not isinstance(block, dict):
                continue

            if block.get("type") == "tool_use":
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

            elif block.get("type") == "tool_result":
                tool_use_id = block.get("tool_use_id", "")
                if tool_use_id:
                    tool_results[tool_use_id] = {
                        "msg_idx": msg_idx,
                        "content_idx": content_idx,
                        "is_error": block.get("is_error", False),
                    }

    return tool_calls, tool_results


def count_turns_between(messages, idx1, idx2):
    """Count user messages (turns) between two transcript indices."""
    count = 0
    for i in range(min(idx1, idx2), max(idx1, idx2) + 1):
        data = messages[i].get("data")
        if data and data.get("type") == "human":
            count += 1
    return count


def optimize_transcript(transcript_path, error_purge_turns=ERROR_PURGE_TURNS):
    """
    Optimize a transcript JSONL file.

    Returns a dict with optimization stats.
    """
    messages = parse_transcript(transcript_path)
    tool_calls, tool_results = extract_tool_uses_and_results(messages)

    stats = {
        "total_tool_calls": len(tool_calls),
        "deduplicated": 0,
        "error_inputs_purged": 0,
        "bytes_saved": 0,
    }

    # --- Phase 1: Deduplication ---
    # Group tool calls by signature
    sig_groups = defaultdict(list)
    for tc in tool_calls:
        sig_groups[tc["signature"]].append(tc)

    # For each group with duplicates, mark earlier ones for dedup
    dedup_targets = {}  # (msg_idx, content_idx) -> replacement block
    for sig, calls in sig_groups.items():
        if len(calls) <= 1:
            continue

        # Sort by position in transcript (keep the LAST one)
        calls.sort(key=lambda c: (c["msg_idx"], c["content_idx"]))
        keep_last = calls[-1]

        for call in calls[:-1]:
            if call["name"] in PROTECTED_TOOLS:
                continue

            original_size = len(json.dumps(call["input"]))

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

            stats["deduplicated"] += 1
            stats["bytes_saved"] += original_size

    # --- Phase 2: Error Input Purging ---
    last_msg_idx = len(messages) - 1
    for tc in tool_calls:
        result_info = tool_results.get(tc["id"])
        if not result_info or not result_info.get("is_error"):
            continue
        if tc["name"] in PROTECTED_TOOLS:
            continue

        # Count turns between the error and now
        turn_age = count_turns_between(messages, result_info["msg_idx"], last_msg_idx)
        if turn_age >= error_purge_turns:
            key = (tc["msg_idx"], tc["content_idx"])
            if key not in dedup_targets:  # Don't double-process
                original_size = len(json.dumps(tc["input"]))

                dedup_targets[key] = {
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": {"_dcp_note": f"input removed — error occurred {turn_age} turns ago"},
                }

                stats["error_inputs_purged"] += 1
                stats["bytes_saved"] += original_size

    # --- Phase 3: Apply Changes ---
    if not dedup_targets:
        return stats

    for (msg_idx, content_idx), replacement in dedup_targets.items():
        data = messages[msg_idx]["data"]
        if data is None:
            continue
        content = data.get("message", {}).get("content", [])
        if content_idx < len(content):
            content[content_idx] = replacement
            # Update the raw line
            messages[msg_idx]["raw"] = json.dumps(data, separators=(",", ":"))

    # Write back
    with open(transcript_path, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(msg["raw"])
            f.write("\n")

    return stats


def main():
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
