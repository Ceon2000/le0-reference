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
fi

# Helper function to run standalone mode
run_standalone() {
    echo "vLLM Standalone"
    log "Generating $NUM_FLOWS expanded flows from prompt suite..."
    python3 run_flow.py flows/three_step.json --num-flows "$NUM_FLOWS"
    log "Flows generated"
    log "Starting standalone execution ($NUM_FLOWS workflows)..."
    NUM_FLOWS="$NUM_FLOWS" python3 standalone_runner.py
    log "Standalone execution completed"
}

# Helper function to run LE-0 mode
run_le0() {
    echo "vLLM+LE-0"
    log "Generating $NUM_FLOWS expanded flows from prompt suite..."
    python3 run_flow.py flows/three_step.json --num-flows "$NUM_FLOWS"
    log "Flows generated"
    log "Starting LE-0 execution ($NUM_FLOWS workflows)..."
    
    # Execute each workflow sequentially
    for i in $(seq 1 "$NUM_FLOWS"); do
        flow_file=$(printf "flows/_expanded_%02d.json" "$i")
        if [ -f "$flow_file" ]; then
            log "Executing workflow $i/$NUM_FLOWS..."
            "$LE0_CMD" "$flow_file"
        else
            log "Warning: Flow file $flow_file not found, skipping" >&2
        fi
    done
    
    log "LE-0 execution completed"
}

# Execute based on mode
if [ "$MODE" = "standalone" ]; then
    run_standalone
elif [ "$MODE" = "le0" ]; then
    run_le0
elif [ "$MODE" = "both" ]; then
    run_standalone
    echo ""
    run_le0
fi

