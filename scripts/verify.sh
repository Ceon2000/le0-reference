#!/bin/bash
set -euo pipefail

echo "[PROGRESS] Verifying Python scripts..."

# Compile check for Python files
for py_file in run_flow.py standalone_runner.py target_vllm.py fixture_loader.py; do
    if [ -f "$py_file" ]; then
        python3 -m py_compile "$py_file" || {
            echo "ERROR: $py_file failed compilation check" >&2
            exit 1
        }
    fi
done

echo "[PROGRESS] Python syntax check passed"

# Quick smoke test with NUM_FLOWS=1
if [ -n "${LE0_WHEEL:-}" ]; then
    echo "[PROGRESS] Running smoke test with NUM_FLOWS=1..."
    NUM_FLOWS=1 MODE=standalone bash run.sh > /dev/null 2>&1 || {
        echo "ERROR: Smoke test failed" >&2
        exit 1
    }
    echo "[PROGRESS] Smoke test passed"
else
    echo "[PROGRESS] Skipping smoke test (LE0_WHEEL not set)"
fi

echo "[PROGRESS] Verification complete"

