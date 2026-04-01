---
description: Show current session token usage and claude-dcp optimization statistics
disable-model-invocation: true
---

# DCP Context Report

Analyze the current session's context usage and report on claude-dcp optimizations.

Steps:
1. Check if the session state directory exists at `~/.claude/plugins/data/claude-dcp/sessions/` (or `/tmp/claude-dcp/sessions/`)
2. Count tool calls logged in the current session's `tool-log.jsonl`
3. Count errors logged in `error-log.jsonl`
4. Read cumulative optimization stats from `optimization-stats.json` (if it exists)
5. Estimate current context size from the transcript file (accessible via the `transcript_path` if known)
6. Report with the following sections:

## Token Savings Summary

Show these metrics prominently at the top:
- **Total bytes saved** (formatted as KB/MB)
- **Estimated tokens saved** (bytes / 4)
- **Total duplicates removed**
- **Total error inputs purged**
- **Number of optimizations run**

## Session Statistics

Present in a summary table:
- Estimated token usage
- Number of tool calls logged
- Number of errored tool inputs tracked
- Current turn count

## Recommendation

- Whether to run /compact based on current token usage
- Whether savings are significant or minimal

Present the report clearly with a summary table. If no optimization has run yet, indicate that savings will appear after the first compaction.
