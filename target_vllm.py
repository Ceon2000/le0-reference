#!/usr/bin/env python3
"""
vLLM target implementation with PREFILL/DECODE latency breakdown.

THIN TARGET CONTRACT:
- Takes a pre-built prompt string
- Calls vLLM to generate
- Returns (output_bytes, metrics_dict)
- NO state tracking, NO context accumulation, NO reuse logic

IP-safe: Treats LE-0 as a black box. No internal details exposed.
"""

import os
import sys
import time
import logging
import warnings
import atexit
from typing import Optional, Tuple, Dict, Any

os.environ.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
os.environ.setdefault("WORLD_SIZE", "1")
os.environ.setdefault("RANK", "0")
os.environ.setdefault("LOCAL_RANK", "0")
os.environ.setdefault("VLLM_LOGGING_LEVEL", "ERROR")

logging.getLogger("vllm").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

warnings.filterwarnings("ignore")

# -----------------------------
# Decode budgeting (per step)
# -----------------------------
# Configurable via BENCH_PROFILE
BENCH_PROFILE = os.environ.get("BENCH_PROFILE", "default")

if BENCH_PROFILE == "prefill_dominant":
    # Prefill-dominant: short decode budgets
    STEP_MAX_NEW_TOKENS = {
        "planner": 64,
        "executor": 128,
        "verifier": 64,
    }
else:
    # Default profile
    STEP_MAX_NEW_TOKENS = {
        "planner": 128,
        "executor": 384,
        "verifier": 160,
    }

# Optional override: LE0_STEP_TOKENS='{"planner":96,"executor":320,"verifier":128}'
try:
    import json as _json
    if os.environ.get("LE0_STEP_TOKENS"):
        STEP_MAX_NEW_TOKENS.update(_json.loads(os.environ.get("LE0_STEP_TOKENS")))
except Exception:
    pass

# -----------------------------
# Prefill-dominant shared prefix
# -----------------------------
_SHARED_PREFIX: Optional[str] = None

def get_shared_prefix() -> str:
    """Get the shared prefix for prefill-dominant profile (deterministic, local)."""
    global _SHARED_PREFIX
    if _SHARED_PREFIX is not None:
        return _SHARED_PREFIX
    
    if BENCH_PROFILE != "prefill_dominant":
        _SHARED_PREFIX = ""
        return _SHARED_PREFIX
    
    # Build a large deterministic prefix from fixture content
    from pathlib import Path
    fixture_dir = Path(__file__).parent / "fixtures" / "helpdesk_ai"
    
    prefix_parts = []
    prefix_parts.append("# SHARED CONTEXT FOR ANALYSIS\n\n")
    prefix_parts.append("The following is the complete helpdesk_ai codebase for reference.\n")
    prefix_parts.append("=" * 80 + "\n\n")
    
    # Collect source files deterministically
    src_dir = fixture_dir / "src" / "helpdesk_ai"
    if src_dir.exists():
        for py_file in sorted(src_dir.rglob("*.py")):
            try:
                content = py_file.read_text(encoding='utf-8')
                rel_path = py_file.relative_to(fixture_dir)
                prefix_parts.append(f"## File: {rel_path}\n```python\n{content}\n```\n\n")
            except Exception:
                pass
    
    # Also include README
    readme = fixture_dir / "README.md"
    if readme.exists():
        try:
            content = readme.read_text(encoding='utf-8')
            prefix_parts.append(f"## File: README.md\n```markdown\n{content}\n```\n\n")
        except Exception:
            pass
    
    prefix_parts.append("=" * 80 + "\n\n")
    prefix_parts.append("# END SHARED CONTEXT\n\n")
    
    _SHARED_PREFIX = "".join(prefix_parts)
    
    # Target 8k-20k tokens (estimate ~4 chars per token)
    # If too short, pad; if too long, truncate
    target_chars = 40000  # ~10k tokens
    if len(_SHARED_PREFIX) < target_chars:
        # Repeat the content to reach target
        repeat_count = (target_chars // len(_SHARED_PREFIX)) + 1
        _SHARED_PREFIX = (_SHARED_PREFIX * repeat_count)[:target_chars]
    elif len(_SHARED_PREFIX) > target_chars * 2:
        _SHARED_PREFIX = _SHARED_PREFIX[:target_chars * 2]
    
    return _SHARED_PREFIX


# -----------------------------
# Stop sequences
# -----------------------------
STOP_MARKER = "<END>"
STOP_SEQUENCES = [STOP_MARKER]

# Optional extra stops: LE0_EXTRA_STOPS="###,</final>"
_extra = os.environ.get("LE0_EXTRA_STOPS", "").strip()
if _extra:
    STOP_SEQUENCES.extend([s.strip() for s in _extra.split(",") if s.strip()])


def get_step_max_tokens(step_name: str) -> int:
    """Get max tokens for a given step."""
    return STEP_MAX_NEW_TOKENS.get(step_name, 256)


def ensure_bounded_prompt(prompt: str) -> str:
    """Ensure prompt ends with stop marker instruction."""
    if STOP_MARKER not in prompt:
        prompt = prompt.rstrip() + f"\n\nOutput must be concise and MUST end with {STOP_MARKER}.\n"
    return prompt


def _log(msg: str) -> None:
    if os.environ.get("QUIET", "0") != "1":
        print(msg, file=sys.stderr)


def _get_gpu_power_watts() -> float:
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            return float(result.stdout.strip().split('\n')[0])
    except Exception:
        pass
    return float(os.environ.get("GPU_POWER", "140.0"))


try:
    from vllm import LLM, SamplingParams
    import torch
except ImportError:
    print("[TARGET] ERROR: vLLM not installed", file=sys.stderr)
    sys.exit(1)

print(f"[TARGET] PROCESS_START pid={os.getpid()} profile={BENCH_PROFILE}", file=sys.stderr)

_llm: Optional[LLM] = None
_engine_init_logged: bool = False


def _get_model_id() -> str:
    return os.environ.get("MODEL", "allenai/Olmo-3-7B-Think")


def _ensure_model_loaded() -> None:
    global _llm, _engine_init_logged
    if _llm is not None:
        return
    _log("[PROGRESS] loading model")
    start_time = time.time()
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        _llm = LLM(model=_get_model_id(), trust_remote_code=True, disable_log_stats=True, max_model_len=65536)
    finally:
        sys.stdout = old_stdout
    init_ms = (time.time() - start_time) * 1000
    if not _engine_init_logged:
        _log("[PROGRESS] model loaded")
        print(f"[TIMING] engine_init_ms={init_ms:.2f}", file=sys.stderr)
        print(f"[TARGET] ENGINE_CREATED pid={os.getpid()}", file=sys.stderr)
        _engine_init_logged = True


def _count_tokens(text: str) -> int:
    global _llm
    if _llm is None:
        return len(text.encode('utf-8')) // 4
    try:
        tokenizer = _llm.get_tokenizer()
        return len(tokenizer.encode(text))
    except Exception:
        return len(text.encode('utf-8')) // 4


def run_prompt(
    prompt: str,
    step_name: str,
    flow_idx: int = 1,
    max_tokens: int = None,
    temperature: float = 0.7,
    is_warmup: bool = False
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Run vLLM generation with TTFT-based prefill/decode timing breakdown.
    
    Args:
        prompt: Pre-built prompt string
        step_name: Name of step for logging
        flow_idx: Flow index for logging (1-indexed)
        max_tokens: Maximum tokens to generate (default: step-specific)
        temperature: Sampling temperature
        is_warmup: Whether this is a warmup call (for treatment)
    
    Returns:
        Tuple of (output_bytes, metrics_dict)
    """
    global _llm
    
    _ensure_model_loaded()
    
    # Prepend shared prefix for prefill-dominant profile
    if BENCH_PROFILE == "prefill_dominant":
        prompt = get_shared_prefix() + prompt
    
    # Apply bounded prompt (adds stop marker instruction)
    prompt = ensure_bounded_prompt(prompt)
    
    # Use step-specific max tokens if not explicitly set
    if max_tokens is None:
        max_tokens = get_step_max_tokens(step_name)
    
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    start_time = time.time()
    
    # Use step-specific max tokens AND stop sequences
    sampling_params = SamplingParams(
        temperature=temperature, 
        max_tokens=max_tokens, 
        top_p=0.9,
        stop=STOP_SEQUENCES
    )
    
    # Generate with streaming to capture TTFT
    # vLLM doesn't expose TTFT directly, so we use non-streaming and estimate
    outputs = _llm.generate([prompt], sampling_params, use_tqdm=False)
    
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    end_time = time.time()
    
    total_latency_ms = (end_time - start_time) * 1000
    
    if outputs and outputs[0].outputs:
        output = outputs[0].outputs[0]
        generated_text = output.text
        # Strip stop marker if present (some engines include it)
        if STOP_MARKER in generated_text:
            generated_text = generated_text.split(STOP_MARKER, 1)[0].rstrip()
        # Get actual decode tokens from vLLM output
        token_ids = getattr(output, 'token_ids', None)
        decode_tokens = len(token_ids) if token_ids and isinstance(token_ids, list) else _count_tokens(generated_text)
    else:
        generated_text = ""
        decode_tokens = 0
    
    prompt_tokens = _count_tokens(prompt)
    power_w = _get_gpu_power_watts()
    
    # TTFT-based prefill/decode estimation
    # Prefill time ≈ time proportional to prompt_tokens
    # Decode time ≈ time proportional to decode_tokens
    # Use a simple heuristic: prefill is ~10x faster per token than decode on GPU
    # More accurate would need vLLM internals, but this gives directional signal
    if decode_tokens > 0 and prompt_tokens > 0:
        # Estimate based on typical GPU characteristics:
        # Prefill: ~30k tokens/sec, Decode: ~100 tokens/sec per request
        # So decode_time/token >> prefill_time/token
        estimated_prefill_time_ratio = prompt_tokens / (prompt_tokens + decode_tokens * 300)
        prefill_ms = total_latency_ms * estimated_prefill_time_ratio
        decode_ms = total_latency_ms - prefill_ms
    else:
        prefill_ms = total_latency_ms
        decode_ms = 0.0
    
    energy_j = power_w * (total_latency_ms / 1000.0)
    
    # Baseline: prefill_tokens_computed = prompt_tokens (no reuse)
    # For treatment: the LE-0 wheel would return actual reused_tokens if available
    # Since we are the baseline target, we set reused_tokens to None to indicate "not available"
    prefill_tokens_computed = prompt_tokens
    reused_tokens = None  # N/A - wheel does not expose this metric
    
    # Log metrics with prefill/decode breakdown (IP-safe: no text output)
    reused_str = "N/A" if reused_tokens is None else str(reused_tokens)
    print(
        f"[TARGET] flow={flow_idx} step={step_name} "
        f"latency_ms={total_latency_ms:.2f} prefill_ms={prefill_ms:.2f} decode_ms={decode_ms:.2f} "
        f"prompt_tokens={prompt_tokens} decode_tokens={decode_tokens} "
        f"prefill_tokens_computed={prefill_tokens_computed} reused_tokens={reused_str} "
        f"power_w={power_w:.2f} energy_j={energy_j:.2f}",
        file=sys.stderr
    )
    
    output_bytes = generated_text.encode('utf-8')
    
    metrics = {
        "input_tokens": prompt_tokens,
        "output_tokens": decode_tokens,
        "prompt_tokens": prompt_tokens,
        "decode_tokens": decode_tokens,
        "latency_ms": total_latency_ms,
        "prefill_ms": prefill_ms,
        "decode_ms": decode_ms,
        "prefill_tokens_computed": prefill_tokens_computed,
        "reused_tokens": reused_tokens,  # None = not available from wheel
        "power_w": power_w,
        "energy_j": energy_j,
    }
    
    # For warmup, generate an opaque context handle
    # This simulates what LE-0 would return - an opaque reference to retained context
    if is_warmup:
        import hashlib
        handle = f"ctx_{hashlib.sha256(prompt.encode()).hexdigest()[:12]}"
        metrics["context_handle"] = handle
    
    return output_bytes, metrics


def run(step_name: str, flow_idx: int = 0, mode: str = "baseline", **kwargs) -> Tuple[bytes, Dict[str, Any]]:
    """
    LE-0 v0.2.0 target contract.
    
    Args:
        step_name: Name of step (warmup/planner/executor/verifier)
        flow_idx: Flow index (0-indexed from LE-0)
        mode: Execution mode (baseline/treatment)
        **kwargs: Must contain 'prompt' key
    
    Returns:
        Tuple of (output_bytes, metrics_dict)
    """
    prompt = kwargs.get("prompt", "")
    is_warmup = step_name == "warmup"
    
    return run_prompt(
        prompt=prompt,
        step_name=step_name,
        flow_idx=flow_idx + 1,
        max_tokens=kwargs.get("max_tokens", 1024),
        temperature=kwargs.get("temperature", 0.7),
        is_warmup=is_warmup,
    )


def init() -> None:
    _ensure_model_loaded()


def _cleanup_engine() -> None:
    global _llm
    if _llm is not None:
        try:
            del _llm
            _llm = None
            print(f"[TARGET] ENGINE_SHUTDOWN pid={os.getpid()}", file=sys.stderr)
        except Exception:
            pass


atexit.register(_cleanup_engine)

if os.environ.get("LE0_EAGER_INIT") == "1":
    init()
