#!/bin/bash
# claude-dcp shared utilities
# Source this file from other scripts: source "$(dirname "$0")/lib.sh"

# Ensure jq is available
if ! command -v jq &>/dev/null; then
  echo "claude-dcp: jq is required but not installed" >&2
  # Exit 0 to not block Claude Code — hooks must never be blocking
  exit 0
fi

# --- Configuration ---
# Load config.json from the plugin directory, fall back to defaults.
# Priority: environment variables > config.json > hardcoded defaults.

_dcp_plugin_root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
_dcp_config_file="${_dcp_plugin_root}/config.json"

# Defaults
DCP_ERROR_PURGE_TURNS=${DCP_ERROR_PURGE_TURNS:-4}
DCP_DEDUP_ENABLED=${DCP_DEDUP_ENABLED:-true}
DCP_ERROR_PURGE_ENABLED=${DCP_ERROR_PURGE_ENABLED:-true}
DCP_CONTEXT_NUDGE_ENABLED=${DCP_CONTEXT_NUDGE_ENABLED:-true}
DCP_INFO_THRESHOLD_TOKENS=${DCP_INFO_THRESHOLD_TOKENS:-120000}
DCP_WARN_THRESHOLD_TOKENS=${DCP_WARN_THRESHOLD_TOKENS:-150000}
DCP_URGENT_THRESHOLD_TOKENS=${DCP_URGENT_THRESHOLD_TOKENS:-180000}
DCP_DUPLICATE_BLOCK_WINDOW=${DCP_DUPLICATE_BLOCK_WINDOW:-60}
DCP_MAX_TOOL_LOG_ENTRIES=${DCP_MAX_TOOL_LOG_ENTRIES:-500}
DCP_PROTECTED_TOOLS="Write Edit ExitPlanMode TodoWrite AskUserQuestion Task"

# Load from config.json if it exists (values NOT set by env vars)
if [ -f "$_dcp_config_file" ]; then
  _cfg() {
    jq -r "$1 // empty" "$_dcp_config_file" 2>/dev/null
  }
  val=$(_cfg '.error_purge_turns');        [ -n "$val" ] && DCP_ERROR_PURGE_TURNS="$val"
  val=$(_cfg '.duplicate_block_window_seconds'); [ -n "$val" ] && DCP_DUPLICATE_BLOCK_WINDOW="$val"
  val=$(_cfg '.max_tool_log_entries');      [ -n "$val" ] && DCP_MAX_TOOL_LOG_ENTRIES="$val"
  val=$(_cfg '.info_threshold_tokens');     [ -n "$val" ] && DCP_INFO_THRESHOLD_TOKENS="$val"
  val=$(_cfg '.warn_threshold_tokens');     [ -n "$val" ] && DCP_WARN_THRESHOLD_TOKENS="$val"
  val=$(_cfg '.urgent_threshold_tokens');   [ -n "$val" ] && DCP_URGENT_THRESHOLD_TOKENS="$val"

  # Boolean fields — only override if the env var was NOT explicitly set
  for field in dedup_enabled error_purge_enabled context_nudge_enabled; do
    upper=$(echo "$field" | tr '[:lower:]' '[:upper:]')
    env_name="DCP_${upper}"
    # Check if the env var was explicitly set (not just defaulted via ${VAR:-default})
    # If printenv returns non-empty, the user set it explicitly
    if ! printenv "$env_name" >/dev/null 2>&1; then
      val=$(_cfg ".$field")
      if [ "$val" = "true" ] || [ "$val" = "false" ]; then
        declare -g "$env_name=$val"
      fi
    fi
  done

  # Protected tools from config
  val=$(_cfg '.protected_tools | join(" ")')
  if [ -n "$val" ]; then
    DCP_PROTECTED_TOOLS="$val"
  fi

  unset -f _cfg
fi

# --- Utility Functions ---

# Sanitize session_id to prevent path traversal
sanitize_session_id() {
  printf '%s' "$1" | tr -cd 'a-zA-Z0-9_-' | head -c 64
}

# Check if a tool is in the protected list
is_protected_tool() {
  local tool_name="$1"
  for t in $DCP_PROTECTED_TOOLS; do
    [ "$t" = "$tool_name" ] && return 0
  done
  return 1
}

# Get or create the session state directory
# Uses CLAUDE_PLUGIN_DATA if available, falls back to a temp-based location
get_state_dir() {
  local session_id
  session_id=$(sanitize_session_id "$1")
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

# Compute SHA-256 hash, portable across Linux (sha256sum) and macOS (shasum)
_compute_hash() {
  if command -v sha256sum &>/dev/null; then
    sha256sum | cut -d' ' -f1
  elif command -v shasum &>/dev/null; then
    shasum -a 256 | cut -d' ' -f1
  else
    echo "claude-dcp: no SHA-256 tool found (need sha256sum or shasum)" >&2
    return 1
  fi
}

# Compute a normalized signature for a tool call
# Args: tool_name, tool_input_json
# Output: sha256 hash
#
# Normalization: sort keys recursively, strip null values.
# Must match Python compute_signature for the same logical input.
compute_signature() {
  local tool_name="$1"
  local tool_input="$2"

  # Normalize: sort keys recursively, strip null values
  local normalized
  normalized=$(echo "$tool_input" | jq -cS 'del(.. | select(. == null))' 2>/dev/null || echo "$tool_input")

  # Combine tool name + normalized input and hash
  local combined="${tool_name}:${normalized}"
  echo -n "$combined" | _compute_hash
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

  # Use jq for safe JSON construction (no injection), compact format for grep
  jq -nc \
    --arg sig "$signature" \
    --arg tool "$tool_name" \
    --arg id "$tool_id" \
    --argjson ts "$timestamp" \
    '{signature: $sig, tool: $tool, id: $id, ts: $ts}' >> "$log_file"
}

# Check if a tool call signature already exists in the log
# Returns 0 if duplicate found, 1 if not
check_duplicate() {
  local state_dir="$1"
  local signature="$2"

  local log_file="${state_dir}/tool-log.jsonl"
  [ -f "$log_file" ] || return 1

  grep -F -q "\"signature\":\"${signature}\"" "$log_file"
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

  # Use jq for safe JSON construction (no injection), compact format for grep
  jq -nc \
    --arg tool "$tool_name" \
    --arg id "$tool_id" \
    --argjson turn "$turn" \
    --argjson ts "$timestamp" \
    '{tool: $tool, id: $id, turn: $turn, ts: $ts}' >> "$log_file"
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

# Trim a JSONL log file to prevent unbounded growth
# Args: log_file, max_entries
trim_log_file() {
  local log_file="$1"
  local max_entries="${2:-$DCP_MAX_TOOL_LOG_ENTRIES}"

  if [ ! -f "$log_file" ]; then
    return 0
  fi

  local line_count
  line_count=$(count_lines "$log_file")
  if [ "$line_count" -gt "$max_entries" ]; then
    local trimmed_count=$((max_entries * 6 / 10))
    tail -n "$trimmed_count" "$log_file" > "${log_file}.tmp"
    mv "${log_file}.tmp" "$log_file"
  fi
}

# Trim error-log.jsonl to prevent unbounded growth
trim_error_log() {
  local state_dir="$1"
  local max_entries="${2:-$DCP_MAX_TOOL_LOG_ENTRIES}"
  local log_file="${state_dir}/error-log.jsonl"

  trim_log_file "$log_file" "$max_entries"
}
