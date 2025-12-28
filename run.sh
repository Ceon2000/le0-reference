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

# Set default GPU power if not provided (W) - used for energy calculations
# Can be overridden with GPU_POWER env var, or will try nvidia-smi
export GPU_POWER="${GPU_POWER:-140.0}"

# Suppress vLLM and torch internal logs
export VLLM_LOGGING_LEVEL=ERROR
export TOKENIZERS_PARALLELISM=false
export TRANSFORMERS_VERBOSITY=error
export TQDM_DISABLE=1
export HF_HUB_DISABLE_PROGRESS_BARS=1
export HF_HUB_DISABLE_EXPERIMENTAL_WARNING=1
export PYTHONWARNINGS=ignore

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

# Run preflight verifier
log "Running preflight checks..."
if ! ./venv/bin/python scripts/preflight.py; then
    log "Preflight checks failed. Aborting." >&2
    exit 1
fi

# Helper function for Python-based floating point calculations (replaces bc)
python_calc() {
    local expr="$1"
    local result
    # Use Python to calculate and round to 1 decimal place
    result=$(./venv/bin/python -c "try: print('{:.1f}'.format(round($expr, 1))); except: print('0.0')" 2>/dev/null)
    # If result is empty or calculation failed, return 0.0
    if [ -z "$result" ]; then
        echo "0.0"
    else
        echo "$result"
    fi
}

# Helper function to get GPU power (W)
# Tries nvidia-smi first, falls back to GPU_POWER env var, then default estimate
get_gpu_power() {
    local power
    # Try nvidia-smi to get current GPU power
    if command -v nvidia-smi >/dev/null 2>&1; then
        power=$(nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits 2>/dev/null | head -1 | xargs)
        if [ -n "$power" ] && [ "$power" != "N/A" ]; then
            echo "$power"
            return
        fi
    fi
    # Fall back to environment variable or default estimate
    power="${GPU_POWER:-140.0}"
    echo "$power"
}

# Helper function to capture metrics from stderr
capture_metrics() {
    local output_file="$1"
    ./venv/bin/python - "$output_file" <<'PYTHON_SCRIPT'
import re
import sys

prompt_tokens_total = 0
decode_tokens_total = 0
latency_ms_total = 0.0
prefill_tokens_total = 0
reused_tokens_total = 0
count_steps = 0

# Match [TARGET] lines from stderr with prefill/reused tokens
pattern = r'\[TARGET\] flow=\d+ step=\S+ latency_ms=([0-9.]+) prompt_tokens=([0-9]+) decode_tokens=([0-9]+) prefill_tokens=([0-9]+) reused_tokens=([0-9]+)'

try:
    with open(sys.argv[1], 'r') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                latency_ms = float(match.group(1))
                prompt_tokens = int(match.group(2))
                decode_tokens = int(match.group(3))
                prefill_tokens = int(match.group(4))
                reused_tokens = int(match.group(5))
                latency_ms_total += latency_ms
                prompt_tokens_total += prompt_tokens
                decode_tokens_total += decode_tokens
                prefill_tokens_total += prefill_tokens
                reused_tokens_total += reused_tokens
                count_steps += 1
except Exception as e:
    sys.stderr.write(f"Error reading metrics: {e}\n")
    sys.exit(1)

print(f"{prompt_tokens_total} {decode_tokens_total} {latency_ms_total:.2f} {prefill_tokens_total} {reused_tokens_total} {count_steps}")
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
    # Clear Python cache to ensure fresh code is used
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
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
    
    # Set PYTHONPATH so LE-0 can import target_vllm
    export PYTHONPATH="$(pwd)"
    
    # Capture stdout and stderr separately
    local temp_stdout=$(mktemp)
    local temp_stderr=$(mktemp)
    trap "rm -f $temp_stdout $temp_stderr" EXIT
    
    # Clear Python cache to ensure fresh code is used
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
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
        read -r prompt_tokens decode_tokens latency_ms prefill_tokens reused_tokens steps <<< "$STANDALONE_METRICS"
        avg_input_tokens=$((prompt_tokens / steps))
        avg_output_tokens=$((decode_tokens / steps))
        avg_total_tokens=$(((prompt_tokens + decode_tokens) / steps))
        avg_latency=$(python_calc "$latency_ms / $steps")
        log "SUMMARY vLLM Standalone: steps=$steps avg_input_tokens=$avg_input_tokens avg_output_tokens=$avg_output_tokens avg_total_tokens=$avg_total_tokens avg_latency_ms=${avg_latency}"
    fi
elif [ "$MODE" = "le0" ]; then
    run_le0
    if [ -n "$LE0_METRICS" ]; then
        read -r prompt_tokens decode_tokens latency_ms prefill_tokens reused_tokens steps <<< "$LE0_METRICS"
        expected_steps=$((NUM_FLOWS * 3))
        if [ "$steps" -eq "$expected_steps" ]; then
            avg_input_tokens=$((prompt_tokens / steps))
            avg_output_tokens=$((decode_tokens / steps))
            avg_total_tokens=$(((prompt_tokens + decode_tokens) / steps))
            avg_prefill=$((prefill_tokens / steps))
            avg_reused=$((reused_tokens / steps))
            avoided_prefill=$((prompt_tokens - prefill_tokens))
            avoided_ratio=$(python_calc "$avoided_prefill * 100 / $prompt_tokens")
            avg_latency=$(python_calc "$latency_ms / $steps")
            # Print clean summary (no [PROGRESS] prefix)
            echo "[PROGRESS] SUMMARY vLLM+LE-0:       steps=$steps avg_input_tokens=$avg_input_tokens avg_output_tokens=$avg_output_tokens avg_total_tokens=$avg_total_tokens avg_prefill=$avg_prefill avg_reused=$avg_reused avoided_prefill=$avoided_prefill avoided_ratio=${avoided_ratio}% avg_latency_ms=${avg_latency}" >&2
        else
            log "SUMMARY vLLM+LE-0:       steps=$steps (expected $expected_steps) prompt_tokens_total=$prompt_tokens latency_ms_total=${latency_ms%.*}"
        fi
    else
        log "SUMMARY vLLM+LE-0: unavailable (no metrics captured)"
    fi
elif [ "$MODE" = "both" ]; then
    run_standalone || true  # Continue even if standalone fails
    echo ""
    # Set PYTHONPATH for LE-0 mode (run_le0 will also set it, but ensure it's set)
    export PYTHONPATH="$(pwd)"
    run_le0 || true  # Continue even if LE-0 fails
    
    # Print comparison summary in table format
    if [ -n "$STANDALONE_METRICS" ] && [ -n "$LE0_METRICS" ]; then
        read -r standalone_prompt standalone_decode standalone_latency standalone_prefill standalone_reused standalone_steps <<< "$STANDALONE_METRICS"
        read -r le0_prompt le0_decode le0_latency le0_prefill le0_reused le0_steps <<< "$LE0_METRICS"
        
        # Calculate averages
        standalone_avg_input=$((standalone_prompt / standalone_steps))
        standalone_avg_output=$((standalone_decode / standalone_steps))
        standalone_avg_total=$(((standalone_prompt + standalone_decode) / standalone_steps))
        # Calculate averages with proper floating point division
        standalone_avg_input=$((standalone_prompt / standalone_steps))
        standalone_avg_output=$((standalone_decode / standalone_steps))
        standalone_avg_total=$(((standalone_prompt + standalone_decode) / standalone_steps))
        # Calculate average latency with proper error handling
        if [ -n "$standalone_latency" ] && [ "$standalone_steps" -gt 0 ]; then
            standalone_avg_latency=$(python_calc "$standalone_latency / $standalone_steps")
        else
            standalone_avg_latency="0.0"
        fi
        
        le0_avg_input=$((le0_prompt / le0_steps))
        le0_avg_output=$((le0_decode / le0_steps))
        le0_avg_total=$(((le0_prompt + le0_decode) / le0_steps))
        le0_avg_prefill=$((le0_prefill / le0_steps))
        le0_avg_reused=$((le0_reused / le0_steps))
        # Avoided prefill = total prompt tokens that would have been needed without reuse
        # This is approximated as: total_prompt_tokens - total_prefill_tokens
        le0_avoided_prefill=$((le0_prompt - le0_prefill))
        le0_avg_avoided_prefill=$((le0_avoided_prefill / le0_steps))
        # Calculate avoided ratio: (avg_avoided_prefill / avg_input_tokens) * 100
        # This shows what percentage of input tokens were avoided due to reuse
        if [ "$le0_avg_input" -gt 0 ]; then
            le0_avoided_ratio=$(python_calc "$le0_avg_avoided_prefill * 100.0 / $le0_avg_input")
        else
            le0_avoided_ratio="0.0"
        fi
        # Calculate average latency with proper error handling
        if [ -n "$le0_latency" ] && [ "$le0_steps" -gt 0 ]; then
            le0_avg_latency=$(python_calc "$le0_latency / $le0_steps")
        else
            le0_avg_latency="0.0"
        fi
        
        # Get GPU power (W) for energy calculations
        gpu_power=$(get_gpu_power)
        
        # Calculate energy (kJ): Power (W) * Time (s) / 1000
        # Total time in seconds = total_latency_ms / 1000
        standalone_total_time_s=$(python_calc "$standalone_latency / 1000.0")
        le0_total_time_s=$(python_calc "$le0_latency / 1000.0")
        standalone_energy_kj=$(python_calc "$gpu_power * $standalone_total_time_s / 1000.0")
        le0_energy_kj=$(python_calc "$gpu_power * $le0_total_time_s / 1000.0")
        
        # Calculate tokens/joule: Total tokens / Energy (kJ)
        standalone_total_tokens=$((standalone_prompt + standalone_decode))
        le0_total_tokens=$((le0_prompt + le0_decode))
        # Check if energy > 0 using Python comparison
        standalone_energy_check=$(./venv/bin/python -c "print(1 if $standalone_energy_kj > 0 else 0)" 2>/dev/null || echo "0")
        le0_energy_check=$(./venv/bin/python -c "print(1 if $le0_energy_kj > 0 else 0)" 2>/dev/null || echo "0")
        if [ "$standalone_energy_check" = "1" ]; then
            standalone_tokens_joule=$(python_calc "$standalone_total_tokens / $standalone_energy_kj")
        else
            standalone_tokens_joule="0.0"
        fi
        if [ "$le0_energy_check" = "1" ]; then
            le0_tokens_joule=$(python_calc "$le0_total_tokens / $le0_energy_kj")
        else
            le0_tokens_joule="0.0"
        fi
        
        # Calculate deltas
        token_delta=$((le0_avg_total - standalone_avg_total))
        token_delta_pct=$(python_calc "$token_delta * 100 / $standalone_avg_total" 2>/dev/null || echo "0.0")
        latency_delta=$(python_calc "$le0_avg_latency - $standalone_avg_latency" 2>/dev/null || echo "0.0")
        latency_delta_pct=$(python_calc "$latency_delta * 100 / $standalone_avg_latency" 2>/dev/null || echo "0.0")
        energy_delta=$(python_calc "$le0_energy_kj - $standalone_energy_kj" 2>/dev/null || echo "0.0")
        energy_delta_pct=$(python_calc "$energy_delta * 100 / $standalone_energy_kj" 2>/dev/null || echo "0.0")
        tokens_joule_delta=$(python_calc "$le0_tokens_joule - $standalone_tokens_joule" 2>/dev/null || echo "0.0")
        tokens_joule_delta_pct=$(python_calc "$tokens_joule_delta * 100 / $standalone_tokens_joule" 2>/dev/null || echo "0.0")
        
        # Print clean comparison table (to stderr, no [PROGRESS] prefix)
        echo "" >&2
        echo "==========================================================================================" >&2
        echo "  Task: multi_task_benchmark | Model: ${MODEL:-allenai/Olmo-3-7B-Think} | Workflows: $NUM_FLOWS" >&2
        echo "==========================================================================================" >&2
        echo "  Tier Definitions:" >&2
        echo "    vLLM = Baseline (vLLM Standalone) - Standard generation, no reuse" >&2
        echo "    vLLM+LE-0 = LE-0 Optimization - Reuse across workflow steps" >&2
        echo "==========================================================================================" >&2
        printf "%-60s %20s %20s\n" "Metric" "vLLM" "vLLM+LE-0" >&2
        echo "------------------------------------------------------------------------------------------" >&2
        printf "%-60s %20s %20s\n" "Samples" "$NUM_FLOWS" "$NUM_FLOWS" >&2
        printf "%-60s %20s %20s\n" "Avg Input Tokens" "$standalone_avg_input" "$le0_avg_input" >&2
        printf "%-60s %20s %20s\n" "Avg Output Tokens" "$standalone_avg_output" "$le0_avg_output" >&2
        printf "%-60s %20s %20s\n" "Avg Total Tokens" "$standalone_avg_total" "$le0_avg_total" >&2
        printf "%-60s %20s %20s\n" "Avg Prefill Tokens" "$standalone_avg_input" "$le0_avg_prefill" >&2
        printf "%-60s %20s %20s\n" "Avg Reused Tokens" "0" "$le0_avg_reused" >&2
        printf "%-60s %20s %20s\n" "Avg Avoided Prefill" "$standalone_avg_input" "$le0_avg_avoided_prefill" >&2
        printf "%-60s %20s %20s\n" "Avoided Prefill Ratio" "0.0%" "${le0_avoided_ratio}%" >&2
        echo "------------------------------------------------------------------------------------------" >&2
        printf "%-60s %20s %20s\n" "Avg Latency (ms)" "${standalone_avg_latency}" "${le0_avg_latency}" >&2
        echo "------------------------------------------------------------------------------------------" >&2
        printf "%-60s %20s %20s\n" "Avg GPU Power (W)" "${gpu_power}" "${gpu_power}" >&2
        printf "%-60s %20s %20s\n" "Energy (kJ)" "${standalone_energy_kj}" "${le0_energy_kj}" >&2
        printf "%-60s %20s %20s\n" "Tokens/Joule" "${standalone_tokens_joule}" "${le0_tokens_joule}" >&2
        echo "==========================================================================================" >&2
        echo "📈 vLLM+LE-0 vs vLLM DELTA (Efficiency Focus)" >&2
        echo "------------------------------------------------------------------------------------------" >&2
        printf "%-60s %s\n" "Token change" "$token_delta ($token_delta_pct%)" >&2
        printf "%-60s %s\n" "Latency change" "${latency_delta} ($latency_delta_pct%) ms" >&2
        echo "------------------------------------------------------------------------------------------" >&2
        printf "%-60s %s\n" "🔋 Energy change" "${energy_delta} (${energy_delta_pct}%) kJ" >&2
        printf "%-60s %s\n" "⚡ Tokens/Joule change" "${tokens_joule_delta} (${tokens_joule_delta_pct}%)" >&2
        echo "------------------------------------------------------------------------------------------" >&2
    elif [ -n "$STANDALONE_METRICS" ]; then
        read -r prompt_tokens decode_tokens latency_ms prefill_tokens reused_tokens steps <<< "$STANDALONE_METRICS"
        avg_input_tokens=$((prompt_tokens / steps))
        avg_output_tokens=$((decode_tokens / steps))
        avg_total_tokens=$(((prompt_tokens + decode_tokens) / steps))
        avg_latency=$(python_calc "$latency_ms / $steps")
        log "SUMMARY vLLM Standalone: steps=$steps avg_input_tokens=$avg_input_tokens avg_output_tokens=$avg_output_tokens avg_total_tokens=$avg_total_tokens avg_latency_ms=${avg_latency}"
    elif [ -n "$LE0_METRICS" ]; then
        read -r prompt_tokens decode_tokens latency_ms prefill_tokens reused_tokens steps <<< "$LE0_METRICS"
        avg_input_tokens=$((prompt_tokens / steps))
        avg_output_tokens=$((decode_tokens / steps))
        avg_total_tokens=$(((prompt_tokens + decode_tokens) / steps))
        avg_prefill=$((prefill_tokens / steps))
        avg_reused=$((reused_tokens / steps))
        avoided_prefill=$((prompt_tokens - prefill_tokens))
        avoided_ratio=$(python_calc "$avoided_prefill * 100 / $prompt_tokens")
        avg_latency=$(python_calc "$latency_ms / $steps")
        # Print clean summary (no [PROGRESS] prefix)
        echo "[PROGRESS] SUMMARY vLLM+LE-0:       steps=$steps avg_input_tokens=$avg_input_tokens avg_output_tokens=$avg_output_tokens avg_total_tokens=$avg_total_tokens avg_prefill=$avg_prefill avg_reused=$avg_reused avoided_prefill=$avoided_prefill avoided_ratio=${avoided_ratio}% avg_latency_ms=${avg_latency}" >&2
    fi
fi
