# LE-0 Reference Implementation with vLLM

This repository provides a reference implementation that wraps LE-0 behind a vLLM target using the `allenai/Olmo-3-7B-Think` model.

## Quick Start

From a fresh shell on RunPod A40:

```bash
LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh
```

## Expected Output

The script will execute 3 steps (planner/executor/verifier) and print:

- Per-step target metrics with `[TARGET]` prefix:
  - `latency_ms`: Generation latency in milliseconds
  - `prompt_tokens`: Number of tokens in the prompt
  - `decode_tokens`: Number of tokens generated
  - `output_hash`: SHA256 hash (first 8 chars) of the output bytes

- LE-0's own per-step output hashes (printed by LE-0)

- **No model output text is printed** (IP-safe)

Example output format:
```
[TARGET] Loading model: allenai/Olmo-3-7B-Think
[TARGET] Model loaded successfully
[TARGET] step=planner latency_ms=1234.56 prompt_tokens=45 decode_tokens=128 output_hash=a1b2c3d4
[TARGET] step=executor latency_ms=2345.67 prompt_tokens=67 decode_tokens=256 output_hash=e5f6g7h8
[TARGET] step=verifier latency_ms=3456.78 prompt_tokens=89 decode_tokens=192 output_hash=i9j0k1l2
```

## Environment Variables

- `LE0_WHEEL` (required): Path to the LE-0 wheel file
- `MODEL` (optional): Model ID to use (defaults to `allenai/Olmo-3-7B-Think`)
- `LE0_TARGET` (optional): Target entrypoint (defaults to `target_vllm:run`)

## Architecture

- **target_vllm.py**: vLLM wrapper with cached model loading
- **flows/three_step.json**: Flow definition with input and three steps
- **run.sh**: Setup script that creates venv, installs dependencies, and runs LE-0

## Features

- Model is cached across steps (loaded once)
- Uses vLLM for efficient inference (not HuggingFace token loop)
- Tolerant to unknown kwargs from LE-0
- IP-safe: no model output text printed
- Minimal UX friction: only `LE0_WHEEL` required

## Requirements

- Python 3.8+
- CUDA-capable GPU (for vLLM)
- LE-0 wheel file

