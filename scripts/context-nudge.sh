#!/bin/bash
# UserPromptSubmit hook: Estimate token usage and nudge toward compaction
# Injects context warnings when the transcript is getting large

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# Skip if context nudges are disabled
if [ "$DCP_CONTEXT_NUDGE_ENABLED" != "true" ]; then
  exit 0
fi

INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Estimate tokens from actual character count, not just line count
CHAR_COUNT=$(wc -c < "$TRANSCRIPT_PATH" | tr -d ' ')

# Average ~4 chars per token for JSONL (structured data with quotes, braces, etc.)
ESTIMATED_TOKENS=$((CHAR_COUNT / 4))

if [ "$ESTIMATED_TOKENS" -ge "$DCP_URGENT_THRESHOLD_TOKENS" ]; then
  jq -n \
    --arg msg "[claude-dcp WARNING] Context is very large (~$((ESTIMATED_TOKENS / 1000))K tokens estimated). Consider using /compact now to free up context space. Stale context may cause degraded responses." \
    '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $msg}}'
  exit 0
elif [ "$ESTIMATED_TOKENS" -ge "$DCP_WARN_THRESHOLD_TOKENS" ]; then
  jq -n \
    --arg msg "[claude-dcp] Context is getting large (~$((ESTIMATED_TOKENS / 1000))K tokens estimated). You may want to use /compact soon to free space." \
    '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $msg}}'
  exit 0
fi

# Context is fine — no nudge needed
exit 0
