#!/bin/bash
# PreToolUse hook: Detect and block duplicate tool calls
# Compares incoming tool call signature against session log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')

# Don't block protected tools
if is_protected_tool "$TOOL_NAME"; then
  exit 0
fi

# Skip if dedup is disabled
if [ "$DCP_DEDUP_ENABLED" != "true" ]; then
  exit 0
fi

STATE_DIR=$(get_state_dir "$SESSION_ID")
SIGNATURE=$(compute_signature "$TOOL_NAME" "$TOOL_INPUT")

if check_duplicate "$STATE_DIR" "$SIGNATURE"; then
  # Find the most recent occurrence to reference
  LOG_FILE="${STATE_DIR}/tool-log.jsonl"
  LAST_MATCH=$(grep -F "\"signature\":\"${SIGNATURE}\"" "$LOG_FILE" | tail -1)
  LAST_TS=$(echo "$LAST_MATCH" | jq -r '.ts // 0')
  NOW=$(date +%s)
  AGE=$((NOW - LAST_TS))

  # Only block if the duplicate is recent (within configured window)
  if [ "$AGE" -lt "$DCP_DUPLICATE_BLOCK_WINDOW" ]; then
    jq -n '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: "Duplicate tool call blocked by claude-dcp. This exact tool call with identical arguments was already executed recently. Use a different approach or modify the arguments."
      }
    }'
    exit 0
  fi
fi

# Not a duplicate (or old enough to allow) — let it proceed
exit 0
