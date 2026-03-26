#!/bin/bash
# UserPromptSubmit hook: Estimate token usage and nudge toward compaction
# Injects context warnings when the transcript is getting large

set -euo pipefail

INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Count lines as a rough proxy for context size
LINE_COUNT=$(wc -l < "$TRANSCRIPT_PATH" | tr -d ' ')

# Estimate tokens: ~4 chars per token, average ~200 chars per JSONL line
# This is a rough heuristic but good enough for nudging
ESTIMATED_TOKENS=$((LINE_COUNT * 50))

# Thresholds (rough estimates for common context windows)
# Sonnet: 200K, Opus: 200K, Haiku: 200K
WARN_THRESHOLD=150000    # ~75% of 200K
URGENT_THRESHOLD=180000  # ~90% of 200K

if [ "$ESTIMATED_TOKENS" -ge "$URGENT_THRESHOLD" ]; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: "[claude-dcp WARNING] Context is very large (~'"$((ESTIMATED_TOKENS / 1000))"'K tokens estimated from '"$LINE_COUNT"' transcript lines). Consider using /compact now to free up context space. Stale context may cause degraded responses."
    }
  }'
  exit 0
elif [ "$ESTIMATED_TOKENS" -ge "$WARN_THRESHOLD" ]; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: "[claude-dcp] Context is getting large (~'"$((ESTIMATED_TOKENS / 1000))"'K tokens estimated). You may want to use /compact soon to free space."
    }
  }'
  exit 0
fi

# Context is fine — no nudge needed
exit 0
