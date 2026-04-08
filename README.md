# Claude DCP — Dynamic Context Pruning for Claude Code

Intelligently manages conversation context to optimize token usage in Claude Code.

Inspired by [opencode-dynamic-context-pruning](https://github.com/Opencode-DCP/opencode-dynamic-context-pruning) for OpenCode, adapted for Claude Code's plugin and hooks architecture.

## What DCP Catches That Claude Code Doesn't

Claude Code has built-in compaction, but it works differently. Here's what DCP adds:

| What Happens | Without DCP | With DCP |
|------------|------------|----------|
| **Same tool call again (60s later)** | Permission prompt appears again | Blocked — "Use a different approach" |
| **Transcript before compaction** | Full duplicate outputs sent to summarizer | Early duplicates replaced with `[Output deduplicated]` |
| **Input from failed command (4 turns ago)** | Still in context | Replaced with `[input removed — error occurred X turns ago]` |
| **Context at 150K tokens** | No warning | "Context is ~150K tokens — consider /compact" |
| **After compaction** | Context refreshes silently | "Re-read files with line limits, tool signatures still tracked" |
| **Session statistics** | None visible | "DCP Savings: 2.3KB saved (~575 tokens est.)" |

DCP operates **alongside** Claude Code's native features, not replacing them. It preprocesses the transcript before native compaction runs, making that compaction more efficient.

## Features

| Feature | How It Works | Native Equivalent |
|---------|-------------|------------------|
| **Tool Deduplication** | Blocks duplicate tool calls (same tool + same args) via `PreToolUse` hook | None — Claude Code always prompts again |
| **Error Input Purging** | Removes inputs from failed tool calls after N turns via transcript optimization | None — native compaction keeps error context |
| **Transcript Pre-Optimization** | `PreCompact` hook removes duplicates BEFORE compaction runs | Native compaction summarizes everything at once |
| **Context Nudges** | Warns when context is large via `UserPromptSubmit` hook | None |
| **Post-Compact Re-Injection** | Re-injects reminders after compaction via `PostCompact` hook | None |
| **Session Statistics** | Tracks cumulative bytes/tokens saved per session | None |

### Why Pre-Optimization Matters

Native compaction (`/compact`) is **LLM-driven** — it sends the full transcript to the model and asks it to summarize. DCP runs **first** and removes obvious waste:

```
┌─────────────────────────────────────────────┐
│ Before Native Compaction                    │
├─────────────────────────────────────────────┤
│ transcript.jsonl                            │
│   ├── "git status" output (duplicate)       │ ← DCP removes this
│   ├── "git status" output (kept)            │ ← DCP keeps this
│   ├── error from "npm install" (4 turns)    │ ← DCP removes input, keeps error
│   ├── ...                                   │
└─────────────────────────────────────────────┘
                   ↓ DCP Pre-Optimization
┌─────────────────────────────────────────────┐
│ After DCP, Before Native Compaction         │
├────────────────────��───────────────────────┤
│ transcript.jsonl (now smaller)              │
│   ├── [Output deduplicated]                 │ ← Placeholder
│   ├── "git status" output (kept)            │
│   ├── [input removed — error occurred]      │ ← Error output preserved
│   ├── ...                                   │
└─────────────────────────────────────────────┘
                   ↓ Native Compaction
┌─────────────────────────────────────────────┐
│ Native Compaction Summary                   │
├─────────────────────────────────────────────┤
│ "• Ran git status—unchanged                 │
│  • npm install failed, retry needed         │
│  • ..."                                     │
└─────────────────────────────────────────────┘
```

The native summarizer sees less redundant content, produces a more accurate summary, and uses fewer tokens doing it.

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

## How Each Feature Works

### 1. Tool Deduplication (Blocks Repeats)

When Claude is about to call a tool with identical arguments to a recent call within the time window, DCP blocks it:

```
User: "Check git status"
Claude: *calls "git status"* → runs → output shown
                ↑
           logged to tool-log.jsonl

User: "What's the status?" (thinking it doesn't know)
Claude: *calls "git status"* → DCP blocks!
Output: "Duplicate tool call blocked — identical Bash call 
within the last 60s. Use a different approach."
```

- **Signature**: SHA-256 hash of `tool_name + normalized(JSON(params))`
- **Window**: Configurable (default: 60 seconds)
- **Protected tools** (never blocked): `Edit`, `Write`, `ExitPlanMode`, `TodoWrite`, `AskUserQuestion`, `Task`

**What native Claude Code does differently**: It prompts again for every tool call. Deduplication is unique to DCP.

### 2. Transcript Pre-Optimization (PreCompact)

Before native compaction runs, DCP makes two deterministic changes to the transcript file:

**Phase A — Deduplication**:
- Find tool calls with identical signatures
- Replace earlier outputs with: `[Output deduplicated — identical to a later tool call]`
- Keep the LAST occurrence intact (the most recent/contextual one)

**Phase B — Error Input Purging** (configurable with `error_purge_turns`):
- Find tool results marked as errors
- If the error is N user turns old or older:
  - Replace the tool USE input with: `[input removed — error occurred X turns ago]`
  - PRESERVE the error output itself (preserves context about what failed)

**What native Claude Code does differently**: Native compaction keeps everything and asks the LLM to summarize. DCP removes obvious waste first, making the summarizer's job easier.

### 3. Context Nudges (UserPromptSubmit)

At each user prompt submit, DCP estimates token usage and injects context when thresholds are crossed:

| Token Count | Nudge Level | Message |
|------------|------------|---------|
| 120K+ | Info | "Context is ~120K tokens — be mindful of large outputs" |
| 150K+ | Warning | "Context is ~150K tokens — consider /compact" |
| 180K+ | Urgent | "URGENT: Context is ~180K tokens — avoid large files, strongly recommend /compact" |

Also includes:
- Deduplication rule reminder: "If a tool call is blocked as a duplicate, do NOT rephrase or vary the command to work around it"
- Session savings: "DCP Savings: 2.3KB saved, 3 duplicates removed, 2 error inputs purged"

**What native Claude Code does differently**: No built-in nudge or warning system.

### 4. Post-Compact Re-Injection (PostCompact)

After native compaction completes, DCP injects a reminder:

```
[Context Refreshed — Post-Compact State]

This conversation was just compacted. The context was pruned to stay within token limits.

DCP Status:
- Previous tool outputs have been consolidated
- File contents read before compaction may need to be re-read if needed
- Tool call signatures are still tracked to prevent duplicate operations
- If a tool call is blocked as a duplicate, do NOT rephrase or vary the command to work around it — respect the block and tell the user instead

Action items:
1. If continuing work on a task, re-read relevant files using the Read tool with a line limit (not the full file)
2. Check git status to confirm the state of the repository
3. Review any pending TODOs from the pre-compaction context
```

**What native Claude Code does differently**: No post-compaction reminder or guidance.

## Configuration

Edit `config.json` in the plugin directory:

### Basic Configuration

```json
{
  "error_purge_turns": 4,
  "dedup_enabled": true,
  "error_purge_enabled": true,
  "context_nudge_enabled": true,
  "protected_tools": [
    "Write",
    "Edit",
    "ExitPlanMode",
    "TodoWrite",
    "AskUserQuestion",
    "Task"
  ],
  "info_threshold_tokens": 120000,
  "warn_threshold_tokens": 150000,
  "urgent_threshold_tokens": 180000,
  "duplicate_block_window_seconds": 60,
  "max_tool_log_entries": 500
}
```

### Environment Variables (Override Config)

| Variable | Description | Default |
|----------|-------------|---------|
| `DCP_ERROR_PURGE_TURNS` | Turns before error inputs are purged | `4` |
| `DCP_DEDUP_ENABLED` | Enable/disable deduplication | `true` |
| `DCP_ERROR_PURGE_ENABLED` | Enable/disable error purging | `true` |
| `DCP_CONTEXT_NUDGE_ENABLED` | Enable/disable context nudges | `true` |
| `DCP_WARN_THRESHOLD_TOKENS` | Token count for warning nudge | `150000` |
| `DCP_URGENT_THRESHOLD_TOKENS` | Token count for urgent nudge | `180000` |
| `DCP_DUPLICATE_BLOCK_WINDOW` | Duplicate block window in seconds | `60` |

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
│   ├── track_turn.py            # UserPromptSubmit: increment turn counter
│   ├── context_nudge.py         # UserPromptSubmit: token estimation + nudges
│   └── session_cleanup.py       # SessionEnd: cleanup state
├── skills/
│   ├── dcp-context/SKILL.md     # Context report skill
│   └── dcp-sweep/SKILL.md       # Manual cleanup skill
├── config.json                  # Default configuration
└── tests/                       # pytest test suite
```

### Hooks Pipeline

```
UserPromptSubmit
  ├── track_turn.py       → Increment turn counter
  └── context_nudge.py   → Token estimation + nudges

PreToolUse
  └── dedup_check.py    → Block duplicates within window

PostToolUse
  └── log_tool_call.py → Log tool call to tool-log.jsonl

PostToolUseFailure
  └── log_error.py      → Log error to error-log.jsonl

PreCompact
  └── pre-compact-optimize.py → Transcript pre-optimization

PostCompact
  └── post_compact_reminder.py → Re-inject context reminders

SessionEnd
  └── session_cleanup.py → Trim logs, reset turn counter
```

### State Storage

Per-session state is stored at:
- `${CLAUDE_PLUGIN_DATA}/sessions/{session_id}/` (preferred)
- `/tmp/claude-dcp/sessions/{session_id}/` (fallback on Unix)

Files:
- `tool-log.jsonl` — append-only log of tool call signatures
- `error-log.jsonl` — errored tool calls with turn numbers
- `turn-counter` — simple turn counter
- `optimization-stats.json` — cumulative optimization stats

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
- **Token estimation is rough**: Based on UTF-8 byte count (~4 bytes/token), not actual tokenization.
- **Dedup window**: Duplicates are only blocked within 60 seconds of the original call.
- **Windows native**: Hook system has known platform bugs (see [Platform Support](#platform-support) above).

## License

MIT