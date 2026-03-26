#!/bin/bash
# SessionEnd hook: Clean up per-session state to prevent unbounded growth
# Keeps state for potential resume, but trims large files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
STATE_DIR=$(get_state_dir "$SESSION_ID")

# Trim tool-log.jsonl to last 100 entries on session end
LOG_FILE="${STATE_DIR}/tool-log.jsonl"
if [ -f "$LOG_FILE" ]; then
  LINE_COUNT=$(count_lines "$LOG_FILE")
  if [ "$LINE_COUNT" -gt 100 ]; then
    tail -n 100 "$LOG_FILE" > "${LOG_FILE}.tmp"
    mv "${LOG_FILE}.tmp" "$LOG_FILE"
  fi
fi

# Reset turn counter on session end (fresh start next session)
echo "0" > "${STATE_DIR}/turn-counter"

exit 0
