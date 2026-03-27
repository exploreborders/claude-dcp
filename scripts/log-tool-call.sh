#!/bin/bash
# PostToolUse hook: Log tool call signatures for dedup detection
# Reads tool info from stdin (JSON), appends to session state

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')
TOOL_ID=$(echo "$INPUT" | jq -r '.tool_input.tool_use_id // .tool_input.id // ""')

STATE_DIR=$(get_state_dir "$SESSION_ID")

# Increment turn counter on each tool call
increment_turn "$STATE_DIR" > /dev/null

# Log the tool call
log_tool_call "$STATE_DIR" "$TOOL_NAME" "$TOOL_INPUT" "$TOOL_ID"

# Trim tool log to prevent unbounded growth
LOG_FILE="${STATE_DIR}/tool-log.jsonl"
trim_log_file "$LOG_FILE" "$DCP_MAX_TOOL_LOG_ENTRIES"

exit 0
