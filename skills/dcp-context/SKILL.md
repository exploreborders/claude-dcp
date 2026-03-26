---
description: Show current session token usage and claude-dcp optimization statistics
disable-model-invocation: true
---

# DCP Context Report

Analyze the current session's context usage and report on claude-dcp optimizations.

Steps:
1. Check if the session state directory exists at `~/.claude/plugins/data/claude-dcp/sessions/` (or `/tmp/claude-dcp/sessions/`)
2. Count tool calls logged and duplicate blocks in the current session's `tool-log.jsonl`
3. Count errors logged in `error-log.jsonl`
4. Estimate current context size from the transcript file (accessible via the `transcript_path` if known)
5. Report:
   - Estimated token usage
   - Number of duplicate tool calls blocked/logged
   - Number of errored tool inputs tracked
   - Recommendation: whether to run /compact

Present the report clearly with a summary table.
