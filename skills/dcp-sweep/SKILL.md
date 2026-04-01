---
description: Manually trigger cleanup of the current session — deduplicate tool outputs and purge old error inputs
disable-model-invocation: true
---

# DCP Sweep

Manually trigger context optimization for the current session.

This is useful when you want to clean up without waiting for automatic compaction.

Steps:
1. Discover the plugin data directory dynamically:
   - Run `ls ~/.claude/plugins/data/` and find the directory matching `*dcp*` (e.g. `claude-dcp-inline`)
   - The session state directory is `~/.claude/plugins/data/<matched-dir>/sessions/`
   - Fallback: `/tmp/claude-dcp/sessions/`
2. If `--full` argument is provided, also attempt to optimize the transcript:
   - Find the transcript path from the most recent session
   - Run deduplication: identify repeated tool calls with identical arguments
   - Report what would be cleaned up
3. Reset the tool log, error log, and turn counter for the current session (trims each log to 60% of max_tool_log_entries, default 300, resets counter to 0)
4. Report the cleanup results

After cleanup, suggest running /compact if context is still large.
