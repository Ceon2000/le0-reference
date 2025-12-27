#!/bin/bash
set -euo pipefail

# Progress logging function (prints to stderr with [PROGRESS] prefix unless QUIET=1)
log() {
    if [ "${QUIET:-0}" != "1" ]; then
        echo "[PROGRESS] $*" >&2
    fi
}

# Parse NUM_FLOWS (defaults to 25, clamped to 1-25)
NUM_FLOWS="${NUM_FLOWS:-25}"
NUM_FLOWS=$((NUM_FLOWS < 1 ? 1 : (NUM_FLOWS > 25 ? 25 : NUM_FLOWS)))

# Parse MODE (defaults to le0)
MODE="${MODE:-le0}"
if [ "$MODE" != "standalone" ] && [ "$MODE" != "le0" ] && [ "$MODE" != "both" ]; then
    echo "ERROR: MODE must be 'standalone', 'le0', or 'both'"
    echo "Usage: MODE=standalone bash run.sh"
    echo "       MODE=le0 LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh"
    echo "       MODE=both LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh"
    exit 1
fi

# Check LE0_WHEEL for modes that require it
if [ "$MODE" = "le0" ] && [ -z "${LE0_WHEEL:-}" ]; then
    echo "ERROR: LE0_WHEEL environment variable is required for MODE=le0" >&2
    echo "Usage: MODE=le0 LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh" >&2
    exit 1
fi

if [ "$MODE" = "both" ] && [ -z "${LE0_WHEEL:-}" ]; then
    echo "ERROR: LE0_WHEEL environment variable is required for MODE=both" >&2
    echo "Usage: MODE=both LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh" >&2
    exit 1
fi

# Print banner (exact format required) - goes to stdout
if [ "$MODE" = "standalone" ]; then
    echo "vLLM Standalone"
elif [ "$MODE" = "le0" ]; then
    echo "vLLM+LE-0"
elif [ "$MODE" = "both" ]; then
    # Banner will be printed in helper functions
    :
fi

# Set default model if not provided
export MODEL="${MODEL:-allenai/Olmo-3-7B-Think}"

# Suppress vLLM and torch internal logs
export VLLM_LOGGING_LEVEL=ERROR
export TOKENIZERS_PARALLELISM=false
export TRANSFORMERS_VERBOSITY=error

# Configure pip progress bar based on QUIET
if [ "${QUIET:-0}" = "1" ]; then
    export PIP_PROGRESS_BAR=off
    PIP_QUIET_FLAG="-q"
else
    export PIP_PROGRESS_BAR=on
    PIP_QUIET_FLAG=""
fi

# Create virtual environment
log "Creating virtual environment..."
python3 -m venv venv > /dev/null 2>&1
source venv/bin/activate
log "Virtual environment activated"

# Install requirements
if [ "${QUIET:-0}" != "1" ]; then
    echo "[PROGRESS] Installing python deps (this may take a few minutes)" >&2
fi
./venv/bin/pip install $PIP_QUIET_FLAG -r requirements.txt
log "Requirements installed"

# Install LE-0 wheel for modes that need it
if [ "$MODE" = "le0" ] || [ "$MODE" = "both" ]; then
    if [ "${QUIET:-0}" != "1" ]; then
        echo "[PROGRESS] Installing LE-0 wheel (this may take a few minutes)" >&2
    fi
    ./venv/bin/pip install --force-reinstall $PIP_QUIET_FLAG "$LE0_WHEEL"
    log "LE-0 wheel installed"
    
    # Set LE-0 target entrypoint
    export LE0_TARGET="${LE0_TARGET:-target_vllm:run}"
    
    # Set reference flows directory for target
    export LE0_REF_FLOWS_DIR="${LE0_REF_FLOWS_DIR:-flows}"
    
    # Use venv binary for LE-0
    LE0_CMD="./venv/bin/le0"
fi

# Helper function to capture metrics from stderr
capture_metrics() {
    local output_file="$1"
    ./venv/bin/python - "$output_file" <<'PYTHON_SCRIPT'
import re
import sys

prompt_tokens_total = 0
latency_ms_total = 0.0
count_steps = 0

# Match [TARGET] lines from stderr (flow= can be 0 for standalone)
pattern = r'\[TARGET\] flow=\d+ step=\S+ latency_ms=([0-9.]+) prompt_tokens=([0-9]+)'

try:
    with open(sys.argv[1], 'r') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                latency_ms = float(match.group(1))
                prompt_tokens = int(match.group(2))
                latency_ms_total += latency_ms
                prompt_tokens_total += prompt_tokens
                count_steps += 1
except Exception as e:
    sys.stderr.write(f"Error reading metrics: {e}\n")
    sys.exit(1)

print(f"{prompt_tokens_total} {latency_ms_total:.2f} {count_steps}")
PYTHON_SCRIPT
}

# Helper function to run standalone mode
run_standalone() {
    echo "vLLM Standalone"
    log "Generating $NUM_FLOWS expanded flows from prompt suite..."
    ./venv/bin/python run_flow.py flows/three_step.json --num-flows "$NUM_FLOWS"
    log "Flows generated"
    log "Starting standalone execution ($NUM_FLOWS workflows)..."
    
    # Capture stderr to temp file for metrics, but also display it
    local temp_output=$(mktemp)
    trap "rm -f $temp_output" EXIT
    
    # Capture stderr (stdout goes to terminal naturally)
    if NUM_FLOWS="$NUM_FLOWS" ./venv/bin/python standalone_runner.py 2> "$temp_output"; then
        log "Standalone execution completed"
        # Display stderr
        cat "$temp_output" >&2
    else
        local exit_code=$?
        log "Standalone failed (engine died). Suggest lowering NUM_FLOWS or decode tokens." >&2
        cat "$temp_output" >&2
        rm -f "$temp_output"
        return $exit_code
    fi
    
    # Extract metrics
    STANDALONE_METRICS=$(capture_metrics "$temp_output")
    rm -f "$temp_output"
}

# Helper function to run LE-0 mode
run_le0() {
    echo "vLLM+LE-0"
    
    # Generate flows first (target needs them)
    log "Generating $NUM_FLOWS expanded flows from prompt suite..."
    ./venv/bin/python run_flow.py flows/three_step.json --num-flows "$NUM_FLOWS"
    log "Flows generated"
    
    log "Starting LE-0 execution ($NUM_FLOWS workflows)..."
    
    # Capture stdout and stderr separately
    local temp_stdout=$(mktemp)
    local temp_stderr=$(mktemp)
    trap "rm -f $temp_stdout $temp_stderr" EXIT
    
    # Run LE-0: stdout (hash-only) goes to console, stderr (metrics) goes to temp file
    if "$LE0_CMD" --num_flows "$NUM_FLOWS" > "$temp_stdout" 2> "$temp_stderr"; then
        log "LE-0 execution completed"
        # Display stdout (hash-only)
        cat "$temp_stdout"
        # Display stderr (metrics)
        cat "$temp_stderr" >&2
    else
        local exit_code=$?
        log "LE-0 execution failed" >&2
        cat "$temp_stdout" >&2
        cat "$temp_stderr" >&2
        rm -f "$temp_stdout" "$temp_stderr"
        return $exit_code
    fi
    
    # Extract metrics from stderr
    LE0_METRICS=$(capture_metrics "$temp_stderr")
    rm -f "$temp_stdout" "$temp_stderr"
}

# Execute based on mode
STANDALONE_METRICS=""
LE0_METRICS=""

if [ "$MODE" = "standalone" ]; then
    run_standalone
    if [ -n "$STANDALONE_METRICS" ]; then
        read -r prompt_tokens latency_ms steps <<< "$STANDALONE_METRICS"
        log "SUMMARY vLLM Standalone: steps=$steps prompt_tokens_total=$prompt_tokens latency_ms_total=${latency_ms%.*}"
    fi
elif [ "$MODE" = "le0" ]; then
    run_le0
    if [ -n "$LE0_METRICS" ]; then
        read -r prompt_tokens latency_ms steps <<< "$LE0_METRICS"
        expected_steps=$((NUM_FLOWS * 3))
        if [ "$steps" -eq "$expected_steps" ]; then
            log "SUMMARY vLLM+LE-0:       steps=$steps prompt_tokens_total=$prompt_tokens latency_ms_total=${latency_ms%.*}"
        else
            log "SUMMARY vLLM+LE-0:       steps=$steps (expected $expected_steps) prompt_tokens_total=$prompt_tokens latency_ms_total=${latency_ms%.*}"
        fi
    else
        log "SUMMARY vLLM+LE-0: unavailable (no metrics captured)"
    fi
elif [ "$MODE" = "both" ]; then
    run_standalone || true  # Continue even if standalone fails
    echo ""
    run_le0 || true  # Continue even if LE-0 fails
    
    # Print comparison summary
    if [ -n "$STANDALONE_METRICS" ]; then
        read -r standalone_prompt standalone_latency standalone_steps <<< "$STANDALONE_METRICS"
        log "SUMMARY vLLM Standalone: steps=$standalone_steps prompt_tokens_total=$standalone_prompt latency_ms_total=${standalone_latency%.*}"
    fi
    
    if [ -n "$LE0_METRICS" ]; then
        read -r le0_prompt le0_latency le0_steps <<< "$LE0_METRICS"
        expected_steps=$((NUM_FLOWS * 3))
        if [ "$le0_steps" -eq "$expected_steps" ]; then
            log "SUMMARY vLLM+LE-0:       steps=$le0_steps prompt_tokens_total=$le0_prompt latency_ms_total=${le0_latency%.*}"
            
            # Calculate deltas if both metrics available
            if [ -n "$STANDALONE_METRICS" ]; then
                delta_result=$(./venv/bin/python -c "print(int($standalone_prompt) - int($le0_prompt), float($standalone_latency) - float($le0_latency))")
                read -r prompt_delta latency_delta <<< "$delta_result"
                log "DELTA: prompt_tokens_total=$prompt_delta latency_ms_total=${latency_delta%.*}"
            fi
        else
            log "SUMMARY vLLM+LE-0:       steps=$le0_steps (expected $expected_steps) prompt_tokens_total=$le0_prompt latency_ms_total=${le0_latency%.*}"
        fi
    else
        log "SUMMARY vLLM+LE-0: unavailable (no metrics captured)"
    fi
fi
