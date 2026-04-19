#!/usr/bin/env bash
set -euo pipefail
echo "=== Audio Device Check ==="
uv run python -c "
import sounddevice as sd
print('Available audio devices:')
print(sd.query_devices())
print()
print('Default input device:')
print(sd.default.device)
"
