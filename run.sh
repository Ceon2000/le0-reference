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
pip install $PIP_QUIET_FLAG -r requirements.txt
log "Requirements installed"

# Install LE-0 wheel for modes that need it
if [ "$MODE" = "le0" ] || [ "$MODE" = "both" ]; then
    if [ "${QUIET:-0}" != "1" ]; then
        echo "[PROGRESS] Installing LE-0 wheel (this may take a few minutes)" >&2
    fi
    pip install $PIP_QUIET_FLAG "$LE0_WHEEL"
    log "LE-0 wheel installed"
    
    # Set LE-0 target entrypoint
    export LE0_TARGET="${LE0_TARGET:-target_vllm:run}"
    
    # Determine LE-0 CLI entrypoint
    LE0_CMD=""
    if command -v le0 &> /dev/null; then
        LE0_CMD="le0"
    elif command -v le0-runtime &> /dev/null; then
        LE0_CMD="le0-runtime"
    elif python -m le0 --help &> /dev/null 2>&1; then
        LE0_CMD="python -m le0"
    else
        echo "ERROR: Could not find LE-0 CLI entrypoint." >&2
        echo "Tried: le0, le0-runtime, python -m le0" >&2
        echo "Please ensure LE-0 wheel is correctly installed." >&2
        exit 1
    fi
    
    # Detect LE-0 flow flag by parsing help output
    LE0_HELP=$("$LE0_CMD" -h 2>&1 || "$LE0_CMD" --help 2>&1)
    LE0_FLOW_FLAG=""
    for flag in --flow --workflow --workflow_path --spec --config; do
        if echo "$LE0_HELP" | grep -q "$flag"; then
            LE0_FLOW_FLAG="$flag"
            break
        fi
    done
    
    # Check if LE-0 supports --num_flows
    LE0_SUPPORTS_NUM_FLOWS=0
    if echo "$LE0_HELP" | grep -q -- "--num_flows"; then
        LE0_SUPPORTS_NUM_FLOWS=1
    fi
    
    if [ -z "$LE0_FLOW_FLAG" ]; then
        echo "[PROGRESS] LE-0 CLI does not accept a flow file flag; update wrapper to match this LE-0 version." >&2
        echo "$LE0_HELP" >&2
        exit 1
    fi
fi

# Helper function to capture metrics from stdout
capture_metrics() {
    local output_file="$1"
    python3 - "$output_file" <<'PYTHON_SCRIPT'
import re
import sys

prompt_tokens_total = 0
latency_ms_total = 0.0
count_steps = 0

pattern = r'\[TARGET\] step=\S+ latency_ms=([0-9.]+) prompt_tokens=([0-9]+)'

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
    python3 run_flow.py flows/three_step.json --num-flows "$NUM_FLOWS"
    log "Flows generated"
    log "Starting standalone execution ($NUM_FLOWS workflows)..."
    
    # Capture stdout to temp file for metrics, but also display it
    local temp_output=$(mktemp)
    trap "rm -f $temp_output" EXIT
    
    # Capture stdout (stderr goes to terminal naturally)
    if NUM_FLOWS="$NUM_FLOWS" python3 standalone_runner.py | tee "$temp_output"; then
        log "Standalone execution completed"
    else
        local exit_code=$?
        log "Standalone failed (engine died). Suggest lowering NUM_FLOWS or decode tokens." >&2
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
    log "Generating $NUM_FLOWS expanded flows from prompt suite..."
    python3 run_flow.py flows/three_step.json --num-flows "$NUM_FLOWS"
    log "Flows generated"
    log "Starting LE-0 execution ($NUM_FLOWS workflows)..."
    
    # Capture stdout to temp file for metrics, but also display it
    local temp_output=$(mktemp)
    trap "rm -f $temp_output" EXIT
    
    # Check if LE-0 supports --num_flows with a single flow file
    if [ "$LE0_SUPPORTS_NUM_FLOWS" = "1" ] && [ "$NUM_FLOWS" -gt 1 ]; then
        # Try using --num_flows with first flow file
        local first_flow=$(printf "flows/_expanded_%02d.json" "1")
        if [ -f "$first_flow" ]; then
            log "Executing all workflows via --num_flows..."
            if "$LE0_CMD" "$LE0_FLOW_FLAG" "$first_flow" --num_flows "$NUM_FLOWS" | tee "$temp_output"; then
                log "LE-0 execution completed"
            else
                log "LE-0 --num_flows failed, falling back to per-workflow loop" >&2
                rm -f "$temp_output"
                temp_output=$(mktemp)
                # Fall through to loop
            fi
        fi
    fi
    
    # If --num_flows didn't work or wasn't supported, loop through workflows
    if [ ! -s "$temp_output" ]; then
        for i in $(seq 1 "$NUM_FLOWS"); do
            flow_file=$(printf "flows/_expanded_%02d.json" "$i")
            if [ -f "$flow_file" ]; then
                log "Executing workflow $i/$NUM_FLOWS..."
                "$LE0_CMD" "$LE0_FLOW_FLAG" "$flow_file" | tee -a "$temp_output"
            else
                log "Warning: Flow file $flow_file not found, skipping" >&2
            fi
        done
        log "LE-0 execution completed"
    fi
    
    # Extract metrics
    LE0_METRICS=$(capture_metrics "$temp_output")
    rm -f "$temp_output"
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
        log "SUMMARY vLLM+LE-0:       steps=$steps prompt_tokens_total=$prompt_tokens latency_ms_total=${latency_ms%.*}"
    fi
elif [ "$MODE" = "both" ]; then
    run_standalone || true  # Continue even if standalone fails
    echo ""
    run_le0 || true  # Continue even if LE-0 fails
    
    # Print comparison summary
    if [ -n "$STANDALONE_METRICS" ] && [ -n "$LE0_METRICS" ]; then
        read -r standalone_prompt standalone_latency standalone_steps <<< "$STANDALONE_METRICS"
        read -r le0_prompt le0_latency le0_steps <<< "$LE0_METRICS"
        
        log "SUMMARY vLLM Standalone: steps=$standalone_steps prompt_tokens_total=$standalone_prompt latency_ms_total=${standalone_latency%.*}"
        log "SUMMARY vLLM+LE-0:       steps=$le0_steps prompt_tokens_total=$le0_prompt latency_ms_total=${le0_latency%.*}"
        
        # Calculate deltas using Python
        delta_result=$(python3 -c "print(int($standalone_prompt) - int($le0_prompt), float($standalone_latency) - float($le0_latency))")
        read -r prompt_delta latency_delta <<< "$delta_result"
        log "DELTA: prompt_tokens_total=$prompt_delta latency_ms_total=${latency_delta%.*}"
    elif [ -n "$STANDALONE_METRICS" ]; then
        read -r prompt_tokens latency_ms steps <<< "$STANDALONE_METRICS"
        log "SUMMARY vLLM Standalone: steps=$steps prompt_tokens_total=$prompt_tokens latency_ms_total=${latency_ms%.*}"
    elif [ -n "$LE0_METRICS" ]; then
        read -r prompt_tokens latency_ms steps <<< "$LE0_METRICS"
        log "SUMMARY vLLM+LE-0:       steps=$steps prompt_tokens_total=$prompt_tokens latency_ms_total=${latency_ms%.*}"
    fi
fi

