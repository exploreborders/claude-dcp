#!/bin/bash
# PostCompact hook: Re-inject context reminders after compaction
# Compaction may have summarized important details, so remind Claude

set -euo pipefail

cat <<'REMINDER'
[claude-dcp] Context was just compacted. Key reminders:
- Review what was summarized — important implementation details may have been compressed
- If working on a specific task, verify you're still on track
- Use /claude-dcp:context to check current token usage
REMINDER

exit 0
