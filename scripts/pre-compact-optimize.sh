#!/bin/bash
# PreCompact hook wrapper: calls the Python transcript optimizer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Forward stdin to the Python script
cat | python3 "${SCRIPT_DIR}/pre-compact-optimize.py"
