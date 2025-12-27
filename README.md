# LE-0 Reference Implementation

## What this is / What this is not

This repository provides a runnable reference example that compares vLLM standalone execution against vLLM execution wrapped with LE-0 for a realistic multi-step workflow.

**What this is:** A reference implementation wrapper for evaluating LE-0.

**What this is not:** LE-0 itself. The LE-0 runtime is distributed separately and must be obtained independently.

## Getting LE-0

To run this example, you must first request access to the LE-0 runtime.

[Request LE-0 runtime access here](https://www.clclabs.ai/le-0) (you will receive a wheel file for local installation)

Once you have the LE-0 wheel file, set `LE0_WHEEL` to its path.

## Quick Start

**Prerequisites:** Python 3.8+, CUDA-capable GPU, LE-0 wheel file (for MODE=le0 only).

```bash
# vLLM Standalone (no LE-0 wheel required)
MODE=standalone bash run.sh

# vLLM+LE-0 (requires LE0_WHEEL)
MODE=le0 LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh

# Both comparisons sequentially (requires LE0_WHEEL)
MODE=both LE0_WHEEL=dist/<le0_wheel>.whl bash run.sh
```

If `MODE` is not specified, it defaults to `le0`. `MODE=both` runs vLLM Standalone followed by vLLM+LE-0 for side-by-side comparison.

The standalone mode establishes baseline per-step latency and token counts; the LE-0 mode demonstrates bounded reuse across steps using the same workflow.

## Expected Output

The script executes 3 steps (planner/executor/verifier) and prints:

- Banner: `vLLM Standalone` or `vLLM+LE-0`
- One `[INPUT]` line: `fixture_bytes=... fixture_files=...`
- Three `[TARGET]` lines: `step=... latency_ms=... prompt_tokens=... decode_tokens=... local_out_hash=...`
- In `MODE=le0`, LE-0 prints additional per-step hash lines

**No model output text is printed** (IP-safe: hashes and metrics only). Correctness is verified via step execution completion and stable per-step output hashes; performance characteristics are reflected in latency and token counts.

## Environment Variables

- `LE0_WHEEL` (required for MODE=le0 and MODE=both): Path to LE-0 wheel file
- `MODE` (optional): `standalone`, `le0`, or `both`, defaults to `le0`
- `MODEL` (optional): Model ID, defaults to `allenai/Olmo-3-7B-Think`
- `QUIET` (optional): Set to `1` to suppress `[PROGRESS]` messages

## What's in this repo

- `target_vllm.py`: vLLM wrapper implementing the target interface
- `fixture_loader.py`: Loads fixture codebase from `fixtures/helpdesk_ai/`
- `run_flow.py`: Expands flow JSON with fixture content
- `standalone_runner.py`: Direct step execution for MODE=standalone
- `run.sh`: Setup and execution script
- `flows/three_step.json`: Flow definition with three steps

**Non-goals:** This reference does not measure throughput, batching efficiency, or cross-node behavior.
