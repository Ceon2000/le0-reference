#!/bin/bash
set -euo pipefail

echo "[PROGRESS] Verifying Python scripts..."

# Syntax check
for py_file in run_flow.py standalone_runner.py target_vllm.py fixture_loader.py; do
    if [ -f "$py_file" ]; then
        python3 -m py_compile "$py_file" || {
            echo "ERROR: $py_file failed compilation check" >&2
            exit 1
        }
    fi
done

echo "[PROGRESS] Python syntax check passed"

# Standalone smoke test
echo "[PROGRESS] Running standalone smoke test with NUM_FLOWS=1..."
if NUM_FLOWS=1 MODE=standalone bash run.sh > /tmp/standalone_stdout.log 2> /tmp/standalone_stderr.log; then
    echo "[PROGRESS] Standalone smoke test passed"
else
    echo "ERROR: Standalone smoke test failed" >&2
    echo "STDOUT:" >&2
    cat /tmp/standalone_stdout.log >&2
    echo "STDERR:" >&2
    cat /tmp/standalone_stderr.log >&2
    exit 1
fi

# LE-0 smoke test (requires wheel)
if [ -n "${LE0_WHEEL:-}" ]; then
    if [ -f "$LE0_WHEEL" ]; then
        echo "[PROGRESS] Running LE-0 smoke test with NUM_FLOWS=1..."
        if NUM_FLOWS=1 MODE=le0 LE0_WHEEL="$LE0_WHEEL" bash run.sh > /tmp/le0_stdout.log 2> /tmp/le0_stderr.log; then
            echo "[PROGRESS] LE-0 smoke test passed"
            # Verify we got 3 [TARGET] lines (3 steps * 1 flow)
            target_count=$(grep -c "\[TARGET\]" /tmp/le0_stderr.log || echo "0")
            if [ "$target_count" -eq 3 ]; then
                echo "[PROGRESS] Verified 3 [TARGET] lines in stderr"
            else
                echo "WARNING: Expected 3 [TARGET] lines, found $target_count" >&2
            fi
        else
            echo "ERROR: LE-0 smoke test failed" >&2
            echo "STDOUT:" >&2
            cat /tmp/le0_stdout.log >&2
            echo "STDERR:" >&2
            cat /tmp/le0_stderr.log >&2
            exit 1
        fi
    else
        echo "[PROGRESS] LE0_WHEEL file not found: $LE0_WHEEL, skipping LE-0 smoke test"
    fi
else
    echo "[PROGRESS] LE0_WHEEL not set, skipping LE-0 smoke test"
fi

echo "[PROGRESS] Verification complete"
