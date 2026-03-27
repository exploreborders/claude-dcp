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

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** | Fully supported | Requires Python 3.9+ |
| **Linux** | Fully supported | Requires Python 3.9+ |
| **Windows (WSL2)** | Fully supported | Run Claude Code inside WSL2 |
| **Windows (native)** | Limited | See note below |

> **Windows native note**: Claude Code's hook system currently has known issues on Windows
> native ([#19012](https://github.com/anthropics/claude-code/issues/19012),
> [#25832](https://github.com/anthropics/claude-code/issues/25832)).
> This affects **all** plugins with hooks, including official Anthropic plugins.
> Hooks may fail silently or fire intermittently. Use WSL2 for full functionality.

## Requirements

- Python 3.9+
- Claude Code CLI

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

This runs on both auto-compaction and manual `/compact`.

### Context Nudges

The `UserPromptSubmit` hook estimates token usage from transcript character count (~4 chars/token heuristic) and warns:
- **120K+ tokens**: Info — context is growing
- **150K+ tokens**: Warn — suggests compaction
- **180K+ tokens**: Urgent — strongly recommends compaction

## Configuration

Edit `config.json` in the plugin directory:

```json
{
  "error_purge_turns": 4,
  "dedup_enabled": true,
  "error_purge_enabled": true,
  "context_nudge_enabled": true,
  "protected_tools": ["Write", "Edit", "ExitPlanMode", "TodoWrite", "AskUserQuestion", "Task"],
  "info_threshold_tokens": 120000,
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
| `DCP_CONTEXT_NUDGE_ENABLED` | Enable/disable context nudges | `true` |
| `DCP_WARN_THRESHOLD_TOKENS` | Token count for warning nudge | `150000` |
| `DCP_URGENT_THRESHOLD_TOKENS` | Token count for urgent nudge | `180000` |

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
│   └── hooks.json               # Hook registrations (Python commands)
├── scripts/
│   ├── lib.py                   # Shared Python utilities
│   ├── log_tool_call.py         # PostToolUse: track tool signatures
│   ├── dedup_check.py           # PreToolUse: block duplicates
│   ├── log_error.py             # PostToolUseFailure: track errors
│   ├── pre-compact-optimize.py  # PreCompact: transcript optimizer
│   ├── post_compact_reminder.py # PostCompact: context re-injection
│   ├── context_nudge.py         # UserPromptSubmit: token estimation
│   └── session_cleanup.py       # SessionEnd: cleanup state
├── skills/
│   ├── dcp-context/SKILL.md     # Context report skill
│   └── dcp-sweep/SKILL.md       # Manual cleanup skill
├── config.json                  # Default configuration
└── tests/                       # pytest test suite
```

### State Storage

Per-session state is stored at:
- `${CLAUDE_PLUGIN_DATA}/sessions/{session_id}/` (preferred)
- `/tmp/claude-dcp/sessions/{session_id}/` (fallback on Unix)

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
- **Token estimation is rough**: Based on character count (~4 chars/token), not actual tokenization.
- **Dedup window**: Duplicates are only blocked within 60 seconds of the original call.
- **Windows native**: Hook system has known platform bugs (see [Platform Support](#platform-support) above).

## License

MIT
