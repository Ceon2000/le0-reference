#!/bin/bash
set -euo pipefail

# Check required environment variable
if [ -z "${LE0_WHEEL:-}" ]; then
    echo "ERROR: LE0_WHEEL environment variable is required"
    echo "Usage: LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh"
    exit 1
fi

# Set default model if not provided
export MODEL="${MODEL:-allenai/Olmo-3-7B-Think}"

# Set LE-0 target entrypoint (try common variants)
export LE0_TARGET="${LE0_TARGET:-target_vllm:run}"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install LE-0 wheel
echo "Installing LE-0 wheel: $LE0_WHEEL"
pip install --quiet "$LE0_WHEEL"

# Install requirements
echo "Installing requirements..."
pip install --quiet -r requirements.txt

# Determine LE-0 CLI entrypoint
LE0_CMD=""
if command -v le0 &> /dev/null; then
    LE0_CMD="le0"
elif command -v le0-runtime &> /dev/null; then
    LE0_CMD="le0-runtime"
elif python -m le0 --help &> /dev/null 2>&1; then
    LE0_CMD="python -m le0"
else
    echo "ERROR: Could not find LE-0 CLI entrypoint."
    echo "Tried: le0, le0-runtime, python -m le0"
    echo "Please ensure LE-0 wheel is correctly installed."
    exit 1
fi

# Run LE-0 with the flow file
echo "Running LE-0 with three-step flow..."
"$LE0_CMD" flows/three_step.json

