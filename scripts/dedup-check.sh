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

# Don't block critical tools
case "$TOOL_NAME" in
  Edit|Write|ExitPlanMode|AskUserQuestion|TodoWrite)
    exit 0
    ;;
esac

STATE_DIR=$(get_state_dir "$SESSION_ID")
SIGNATURE=$(compute_signature "$TOOL_NAME" "$TOOL_INPUT")

if check_duplicate "$STATE_DIR" "$SIGNATURE"; then
  # Find the most recent occurrence to reference
  LOG_FILE="${STATE_DIR}/tool-log.jsonl"
  LAST_MATCH=$(grep "\"signature\":\"${SIGNATURE}\"" "$LOG_FILE" | tail -1)
  LAST_TS=$(echo "$LAST_MATCH" | jq -r '.ts // 0')
  NOW=$(date +%s)
  AGE=$((NOW - LAST_TS))

  # Only block if the duplicate is recent (< 60 seconds)
  # This allows intentionally re-running the same command after a while
  if [ "$AGE" -lt 60 ]; then
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
