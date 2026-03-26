# Claude DCP — Dynamic Context Pruning for Claude Code

Intelligently manages conversation context to optimize token usage in Claude Code.

Inspired by [opencode-dynamic-context-pruning](https://github.com/Opencode-DCP/opencode-dynamic-context-pruning) for OpenCode, adapted for Claude Code's plugin and hooks architecture.

## Features

| Feature | How It Works |
|---------|-------------|
| **Tool Deduplication** | Blocks duplicate tool calls (same tool + same args) via `PreToolUse` hook |
| **Error Input Purging** | Removes inputs from failed tool calls after N turns via transcript optimization |
| **Transcript Optimization** | `PreCompact` hook prunes the transcript before compaction runs |
| **Context Nudges** | Warns when context is getting large via `UserPromptSubmit` hook |
| **Post-Compact Reminders** | Re-injects key context after compaction via `PostCompact` hook |

## Installation

### From Plugin Directory (Development)

```bash
claude --plugin-dir /path/to/claude-dcp
```

### Install Permanently

```bash
# Copy to your plugins directory
cp -r /path/to/claude-dcp ~/.claude/plugins/claude-dcp

# Or symlink for development
ln -s /path/to/claude-dcp ~/.claude/plugins/claude-dcp
```

Then enable in your settings:

```json
// ~/.claude/settings.json or .claude/settings.json
{
  "enabledPlugins": ["claude-dcp"]
}
```

## How It Works

### Deduplication

When Claude is about to call a tool with identical arguments to a recent call, the `PreToolUse` hook blocks it and tells Claude to try a different approach. The signature is computed from `tool_name + normalized(JSON(params))`.

Blocked tools are only those executed within the last 60 seconds. Intentionally re-running the same command after a delay is still allowed.

**Protected tools** (never blocked): `Edit`, `Write`, `ExitPlanMode`, `TodoWrite`, `AskUserQuestion`, `Task`

### Transcript Optimization (PreCompact)

Before Claude Code runs compaction, the `PreCompact` hook optimizes the transcript file:

1. **Deduplication**: Finds tool calls with identical signatures and replaces earlier outputs with `[Output deduplicated]`
2. **Error Purging**: Replaces inputs from errored tools older than N turns with `[input removed]` (error output preserved)

This runs on auto-compaction only (not manual `/compact`).

### Context Nudges

The `UserPromptSubmit` hook estimates token usage from transcript line count and warns:
- **150K+ tokens**: Suggests compaction
- **180K+ tokens**: Urgently recommends compaction

## Configuration

Edit `config.json` in the plugin directory:

```json
{
  "error_purge_turns": 4,
  "dedup_enabled": true,
  "error_purge_enabled": true,
  "context_nudge_enabled": true,
  "protected_tools": ["Write", "Edit", "ExitPlanMode", "TodoWrite", "AskUserQuestion", "Task"],
  "warn_threshold_tokens": 150000,
  "urgent_threshold_tokens": 180000,
  "duplicate_block_window_seconds": 60,
  "max_tool_log_entries": 500
}
```

Environment variables (override config):

| Variable | Description | Default |
|----------|-------------|---------|
| `DCP_ERROR_PURGE_TURNS` | Turns before error inputs are purged | `4` |
| `DCP_DEDUP_ENABLED` | Enable/disable deduplication | `true` |
| `DCP_ERROR_PURGE_ENABLED` | Enable/disable error purging | `true` |

## Skills

| Skill | Description |
|-------|-------------|
| `/claude-dcp:context` | Show current session token usage and DCP statistics |
| `/claude-dcp:sweep` | Manually trigger session cleanup |

## Architecture

```
claude-dcp/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── hooks/
│   └── hooks.json               # Hook registrations
├── scripts/
│   ├── lib.sh                   # Shared utilities
│   ├── log-tool-call.sh         # PostToolUse: track tool signatures
│   ├── dedup-check.sh           # PreToolUse: block duplicates
│   ├── log-error.sh             # PostToolUseFailure: track errors
│   ├── pre-compact-optimize.sh  # PreCompact: transcript optimizer (wrapper)
│   ├── pre-compact-optimize.py  # PreCompact: transcript optimizer (logic)
│   ├── post-compact-reminder.sh # PostCompact: context re-injection
│   └── context-nudge.sh         # UserPromptSubmit: token estimation
├── skills/
│   ├── dcp-context/SKILL.md     # Context report skill
│   └── dcp-sweep/SKILL.md       # Manual cleanup skill
└── config.json                  # Default configuration
```

### State Storage

Per-session state is stored at:
- `${CLAUDE_PLUGIN_DATA}/sessions/{session_id}/` (preferred)
- `/tmp/claude-dcp/sessions/{session_id}/` (fallback)

Files:
- `tool-log.jsonl` — append-only log of tool call signatures
- `error-log.jsonl` — errored tool calls with turn numbers
- `turn-counter` — simple turn counter

## Differences from OpenCode DCP

| Feature | OpenCode DCP | Claude DCP |
|---------|-------------|------------|
| Custom tools | Registers `compress` tool | Not possible (no tool API) |
| Message transform | In-process hook modifies message array | PreCompact modifies transcript file on disk |
| Compression | LLM-driven range/message compression | Leverages Claude Code's built-in `/compact` |
| Nudges | Injected during LLM calls | Injected via UserPromptSubmit hook |
| Config | `dcp.jsonc` | `config.json` + env vars |

## Limitations

- **No custom compress tool**: Claude Code doesn't support custom tool registration. Use `/compact` or let auto-compaction trigger optimization.
- **Transcript format dependency**: The optimizer assumes a specific JSONL format. Claude Code updates may change this format.
- **Token estimation is rough**: Based on line count heuristics, not actual tokenization.
- **Dedup window**: Duplicates are only blocked within 60 seconds of the original call.

## License

MIT
