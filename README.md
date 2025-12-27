# LE-0 Reference Implementation with vLLM

This repository provides a reference implementation for A/B comparison between vLLM Standalone and vLLM+LE-0 using the `allenai/Olmo-3-7B-Think` model.

## Quick Start

From a fresh shell on RunPod A40:

### vLLM Standalone

```bash
MODE=standalone bash run.sh
```

### vLLM+LE-0

```bash
MODE=le0 LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh
```

**Note:** `LE0_WHEEL` is only required for `MODE=le0`. If `MODE` is not specified, it defaults to `le0`.

## Expected Output

The script will automatically inject the complete `fixtures/helpdesk_ai/` codebase into the flow input before step 1, making the prompt >=10k tokens. The script will execute 3 steps (planner/executor/verifier) and print:

- One banner line indicating the mode:
  - `vLLM Standalone` (for MODE=standalone)
  - `vLLM+LE-0` (for MODE=le0)

- One `[INPUT]` line before step 1:
  - `fixture_bytes`: Total bytes loaded from fixture files
  - `fixture_files`: Number of fixture files loaded

- Per-step target metrics with `[TARGET]` prefix (one line per step):
  - `step`: Step name (planner, executor, verifier)
  - `latency_ms`: Generation latency in milliseconds
  - `prompt_tokens`: Number of tokens in the prompt
  - `decode_tokens`: Number of tokens generated
  - `local_out_hash`: SHA256 hash (first 8 chars) of the output bytes

- In `MODE=le0`, LE-0 will print its own per-step hash lines (printed by LE-0)

- **No model output text is printed** (IP-safe)

Example output format for MODE=standalone:
```
vLLM Standalone
[INPUT] fixture_bytes=115185 fixture_files=40
[TARGET] step=planner latency_ms=1234.56 prompt_tokens=12456 decode_tokens=128 local_out_hash=a1b2c3d4
[TARGET] step=executor latency_ms=2345.67 prompt_tokens=12567 decode_tokens=256 local_out_hash=e5f6g7h8
[TARGET] step=verifier latency_ms=3456.78 prompt_tokens=12678 decode_tokens=192 local_out_hash=i9j0k1l2
```

Example output format for MODE=le0:
```
vLLM+LE-0
[INPUT] fixture_bytes=115185 fixture_files=40
[TARGET] step=planner latency_ms=1234.56 prompt_tokens=12456 decode_tokens=128 local_out_hash=a1b2c3d4
[LE-0 hash line printed by LE-0]
[TARGET] step=executor latency_ms=2345.67 prompt_tokens=12567 decode_tokens=256 local_out_hash=e5f6g7h8
[LE-0 hash line printed by LE-0]
[TARGET] step=verifier latency_ms=3456.78 prompt_tokens=12678 decode_tokens=192 local_out_hash=i9j0k1l2
[LE-0 hash line printed by LE-0]
```

## Environment Variables

- `MODE` (optional): Execution mode - `standalone` (vLLM Standalone) or `le0` (vLLM+LE-0). Defaults to `le0`.
- `LE0_WHEEL` (required for MODE=le0): Path to the LE-0 wheel file
- `MODEL` (optional): Model ID to use (defaults to `allenai/Olmo-3-7B-Think`)
- `LE0_TARGET` (optional, for MODE=le0): Target entrypoint (defaults to `target_vllm:run`)

## Architecture

- **target_vllm.py**: vLLM wrapper with model loaded once and reused across steps
- **fixture_loader.py**: Loads fixture content from `fixtures/helpdesk_ai/`
- **run_flow.py**: Expands flow JSON with fixture content before execution
- **standalone_runner.py**: Direct execution runner for MODE=standalone
- **flows/three_step.json**: Flow definition with input and three steps
- **run.sh**: Setup script that creates venv, installs dependencies, expands flow, and runs either standalone or LE-0

## Features

- Model is loaded once and reused across steps
- Uses vLLM for efficient inference
- Automatically injects large fixture codebase (>=10k tokens) into flow input
- Tolerant to unknown kwargs
- IP-safe: no model output text printed
- A/B comparison: vLLM Standalone vs vLLM+LE-0

## Requirements

- Python 3.8+
- CUDA-capable GPU (for vLLM)
- LE-0 wheel file (only required for MODE=le0)
