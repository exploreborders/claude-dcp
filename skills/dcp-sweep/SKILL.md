---
description: Manually trigger cleanup of the current session — deduplicate tool outputs and purge old error inputs
disable-model-invocation: true
---

# DCP Sweep

Manually trigger context optimization for the current session by running:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sweep_report.py
```

If the `--full` argument is provided, include it in the command:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sweep_report.py --full
```

Present the output to the user in a clear format.
