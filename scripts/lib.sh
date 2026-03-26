#!/bin/bash
# claude-dcp shared utilities
# Source this file from other scripts: source "$(dirname "$0")/lib.sh"

# Ensure jq is available
if ! command -v jq &>/dev/null; then
  echo "claude-dcp: jq is required but not installed" >&2
  exit 0
fi

# Get or create the session state directory
# Uses CLAUDE_PLUGIN_DATA if available, falls back to a temp-based location
get_state_dir() {
  local session_id="$1"
  local base_dir

  if [ -n "$CLAUDE_PLUGIN_DATA" ]; then
    base_dir="${CLAUDE_PLUGIN_DATA}/sessions"
  else
    base_dir="/tmp/claude-dcp/sessions"
  fi

  local state_dir="${base_dir}/${session_id}"
  mkdir -p "$state_dir"
  echo "$state_dir"
}

# Compute a normalized signature for a tool call
# Args: tool_name, tool_input_json
# Output: sha256 hash
compute_signature() {
  local tool_name="$1"
  local tool_input="$2"

  # Normalize: sort keys recursively, strip null/undefined values
  local normalized
  normalized=$(echo "$tool_input" | jq -cS 'del(.. | .empty?)' 2>/dev/null || echo "$tool_input")

  # Combine tool name + normalized input and hash
  local combined="${tool_name}:${normalized}"
  echo -n "$combined" | shasum -a 256 | cut -d' ' -f1
}

# Log a tool call to the session state file
log_tool_call() {
  local state_dir="$1"
  local tool_name="$2"
  local tool_input="$3"
  local tool_id="${4:-}"

  local signature
  signature=$(compute_signature "$tool_name" "$tool_input")

  local log_file="${state_dir}/tool-log.jsonl"
  local timestamp
  timestamp=$(date +%s)

  printf '{"signature":"%s","tool":"%s","id":"%s","ts":%d}\n' \
    "$signature" "$tool_name" "$tool_id" "$timestamp" >> "$log_file"
}

# Check if a tool call signature already exists in the log
# Returns 0 if duplicate found, 1 if not
check_duplicate() {
  local state_dir="$1"
  local signature="$2"

  local log_file="${state_dir}/tool-log.jsonl"
  [ -f "$log_file" ] || return 1

  grep -q "\"signature\":\"${signature}\"" "$log_file"
}

# Log an error with turn counter
log_error() {
  local state_dir="$1"
  local tool_name="$2"
  local tool_input="$3"
  local tool_id="${4:-}"

  local turn
  turn=$(get_turn "$state_dir")

  local log_file="${state_dir}/error-log.jsonl"
  local timestamp
  timestamp=$(date +%s)

  # Truncate tool_input to avoid huge log files
  local truncated_input
  truncated_input=$(echo "$tool_input" | jq -c '.' 2>/dev/null | head -c 500)

  printf '{"tool":"%s","id":"%s","turn":%d,"ts":%d}\n' \
    "$tool_name" "$tool_id" "$turn" "$timestamp" >> "$log_file"
}

# Get current turn counter
get_turn() {
  local state_dir="$1"
  local turn_file="${state_dir}/turn-counter"
  if [ -f "$turn_file" ]; then
    cat "$turn_file"
  else
    echo 0
  fi
}

# Increment and return the turn counter
increment_turn() {
  local state_dir="$1"
  local turn_file="${state_dir}/turn-counter"
  local current
  current=$(get_turn "$state_dir")
  local next=$((current + 1))
  echo "$next" > "$turn_file"
  echo "$next"
}

# Count lines in a file safely
count_lines() {
  local file="$1"
  if [ -f "$file" ]; then
    wc -l < "$file" | tr -d ' '
  else
    echo 0
  fi
}
