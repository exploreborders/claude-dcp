#!/bin/bash
# PreCompact hook wrapper: calls the Python transcript optimizer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check python3 is available
if ! command -v python3 &>/dev/null; then
  echo "claude-dcp: python3 is required for transcript optimization but not found" >&2
  exit 0
fi

# Forward stdin to the Python script
cat | python3 "${SCRIPT_DIR}/pre-compact-optimize.py"
