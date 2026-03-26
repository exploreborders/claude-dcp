#!/bin/bash
# PostToolUseFailure hook: Log errored tool calls for later purging

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')
TOOL_ID=$(echo "$INPUT" | jq -r '.tool_input.tool_use_id // .tool_input.id // ""')

STATE_DIR=$(get_state_dir "$SESSION_ID")
log_error "$STATE_DIR" "$TOOL_NAME" "$TOOL_INPUT" "$TOOL_ID"

exit 0
