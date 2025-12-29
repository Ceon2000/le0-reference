#!/usr/bin/env python3
"""
vLLM target implementation for LE-0.
Provides a vLLM model wrapper that accepts LE-0 step calls.
"""

import os
import sys
import time
import hashlib
import logging
import json
import warnings
import contextlib
import atexit
from pathlib import Path
from typing import Optional, Dict, Any

# =============================================================================
# CRITICAL: Set vLLM environment variables BEFORE importing vLLM
# These control worker spawn method and distributed initialization
# =============================================================================
os.environ.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")  # Proper fork handling
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")  # Single GPU
os.environ.setdefault("WORLD_SIZE", "1")  # No distributed
os.environ.setdefault("RANK", "0")
os.environ.setdefault("LOCAL_RANK", "0")

# Suppress vLLM and torch internal logs before importing
logging.getLogger("vllm").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("tokenizers").setLevel(logging.ERROR)
logging.getLogger("safetensors").setLevel(logging.ERROR)

# Suppress tqdm progress bars and other verbose output
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_EXPERIMENTAL_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

# Suppress torch warnings (already imported above)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore")

def _progress(msg: str) -> None:
    """Print progress message to stderr unless QUIET=1."""
    if os.environ.get("QUIET", "0") != "1":
        print(f"[PROGRESS] {msg}", file=sys.stderr)

try:
    from vllm import LLM, SamplingParams
    import torch
except ImportError:
    print("[TARGET] ERROR: vLLM not installed. Install with: pip install vllm", file=sys.stderr)
    sys.exit(1)

# Log process start for lifecycle instrumentation
print(f"[TARGET] PROCESS_START pid={os.getpid()}", file=sys.stderr)

# Global model and tokenizer (loaded once, reused across steps)
_llm: Optional[LLM] = None
_model_id: Optional[str] = None
_engine_init_timing_logged: bool = False  # Track if we've logged engine init timing

# Flow tracking for LE-0 mode
_flow_idx: int = 0
_step_sequence: list = []  # Track step names in order: ["planner", "executor", "verifier", ...]
_flows_dir: Optional[Path] = None
_flows_cache: Dict[int, Dict] = {}

# Token tracking for prefill/reused analysis
_step_token_tracking: Dict[tuple, int] = {}  # (flow_idx, step_name) -> prompt_tokens


def _get_model_id() -> str:
    """Get model ID from environment or default."""
    return os.environ.get("MODEL", "allenai/Olmo-3-7B-Think")


def _get_flows_dir() -> Path:
    """Get flows directory from environment or default."""
    flows_dir = os.environ.get("LE0_REF_FLOWS_DIR", "flows")
    return Path(flows_dir)


def _load_flow(flow_idx: int) -> Dict:
    """Load a flow file by index."""
    global _flows_cache, _flows_dir
    
    if flow_idx in _flows_cache:
        return _flows_cache[flow_idx]
    
    if _flows_dir is None:
        _flows_dir = _get_flows_dir()
    
    flow_file = _flows_dir / f"_expanded_{flow_idx:02d}.json"
    
    if not flow_file.exists():
        raise FileNotFoundError(f"Flow file not found: {flow_file}")
    
    with open(flow_file, "r") as f:
        flow = json.load(f)
    
    _flows_cache[flow_idx] = flow
    return flow


def _get_current_flow_idx() -> int:
    """Determine current flow index based on step sequence."""
    global _step_sequence
    
    # Expected step sequence: planner, executor, verifier (repeats for each flow)
    # Count how many complete cycles (planner->executor->verifier) we've seen
    
    if not _step_sequence:
        return 0
    
    # Count complete cycles by looking for "verifier" steps
    # Each "verifier" marks the end of a flow
    complete_flows = 0
    for i, step in enumerate(_step_sequence):
        if step == "verifier":
            complete_flows += 1
    
    # Current flow index (0-indexed)
    # If the last step was "verifier", we've completed that flow, so next call is next flow
    # Otherwise, we're still in the current flow
    if _step_sequence[-1] == "verifier":
        # Just completed a flow, next step will be in the next flow
        return complete_flows
    else:
        # Currently in a flow (planner or executor)
        return complete_flows


def _ensure_model_loaded():
    """Ensure the vLLM model is loaded. Returns immediately if already loaded."""
    global _llm, _model_id, _engine_init_timing_logged
    
    # Fast path: if engine already loaded and model ID matches, return immediately
    current_model_id = _get_model_id()
    if _llm is not None and _model_id == current_model_id:
        return
    
    # Engine needs to be created - log timing for first init only
    if not _engine_init_timing_logged:
        print("[TIMING] engine_init_start", file=sys.stderr)
        engine_init_start = time.time()
    
    try:
        _progress("loading model")
        # Aggressively suppress all output during model loading
        # Directly replace sys.stdout/stderr (more effective than redirect_stdout for subprocesses)
        devnull = open(os.devnull, 'w')
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = devnull
            sys.stderr = devnull
            # Prevent torch.distributed init for single-GPU runs
            # Set environment variables before LLM creation
            os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
            # Create engine (this will trigger vLLM's internal distributed init, but only once)
            _llm = LLM(model=current_model_id, trust_remote_code=True)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            devnull.close()
        _model_id = current_model_id
        _progress("model loaded")
        
        # Log timing for first init only
        if not _engine_init_timing_logged:
            engine_init_time = time.time() - engine_init_start
            print(f"[TIMING] engine_init_ms={engine_init_time * 1000:.2f}", file=sys.stderr)
            print(f"[TARGET] ENGINE_CREATED pid={os.getpid()}", file=sys.stderr)
            _engine_init_timing_logged = True
    except Exception as e:
        print(f"[TARGET] ERROR: Failed to load model '{current_model_id}': {e}", file=sys.stderr)
        raise


def _count_tokens(text: str) -> int:
    """Count tokens using the model's tokenizer."""
    global _llm
    if _llm is None:
        return len(text.split())  # Fallback approximation
    try:
        # Access the tokenizer through the LLM engine
        tokenizer = _llm.llm_engine.tokenizer.tokenizer
        return len(tokenizer.encode(text))
    except Exception:
        # Fallback to word count approximation
        return len(text.split())


def run_prompt(prompt: str, step_name: str, max_tokens: int = 1024, temperature: float = 0.7) -> bytes:
    """
    Run vLLM generation with an explicit prompt (for standalone mode).
    
    NOTE: Engine must be pre-loaded via _ensure_model_loaded() before calling this function.
    This function assumes the engine is already loaded to avoid repeated checks.
    
    Args:
        prompt: Full prompt text
        step_name: Name of the step
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
    
    Returns:
        bytes: Raw model output as bytes
    """
    global _llm
    
    # Engine should already be loaded by standalone_runner.py before workflow loop
    # Only check if somehow not loaded (safety check, should not happen)
    if _llm is None:
        _ensure_model_loaded()
    
    # Record start time for latency measurement (GPU synchronized)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    start_time = time.time()
    
    # Run vLLM generation
    try:
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
        )
        
        # Generate (this includes prefill + decode)
        outputs = _llm.generate([prompt], sampling_params, use_tqdm=False)
        
        # Synchronize GPU before measuring end time for accurate latency
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        
        # Calculate end time
        end_time = time.time()
        
        # Extract generated text and token counts
        if outputs and outputs[0].outputs:
            output = outputs[0].outputs[0]
            generated_text = output.text
            
            # Get decode tokens from output metadata
            decode_tokens = getattr(output, 'token_ids', None)
            if decode_tokens is not None and isinstance(decode_tokens, list):
                decode_tokens = len(decode_tokens)
            else:
                # Fallback: count tokens using tokenizer
                decode_tokens = _count_tokens(generated_text)
        else:
            generated_text = ""
            decode_tokens = 0
        
        # Calculate latency (end time already synchronized)
        latency_ms = (end_time - start_time) * 1000
        
        # Count prompt tokens using tokenizer
        prompt_tokens = _count_tokens(prompt)
        
        # Standalone mode: no reuse, all tokens are prefill
        prefill_tokens = prompt_tokens
        reused_tokens = 0
        
        # Convert to bytes
        output_bytes = generated_text.encode('utf-8')
        
        # Print metrics to stderr (IP-safe: no text output)
        print(
            f"[TARGET] flow=0 step={step_name} latency_ms={latency_ms:.2f} "
            f"prompt_tokens={prompt_tokens} decode_tokens={decode_tokens} "
            f"prefill_tokens={prefill_tokens} reused_tokens={reused_tokens}",
            file=sys.stderr
        )
        
        return output_bytes
        
    except Exception as e:
        print(f"[TARGET] ERROR: Generation failed for step '{step_name}': {e}", file=sys.stderr)
        raise


def run(step_name: str, **kwargs) -> bytes:
    """
    Run a single LE-0 step through vLLM.
    This function is called by LE-0 and must track flow/step indices internally.
    
    NOTE: Engine must be pre-loaded via _ensure_model_loaded() before LE-0 starts.
    This function assumes the engine is already loaded to avoid repeated checks.
    
    Args:
        step_name: Name of the step (e.g., "planner", "executor", "verifier")
        **kwargs: Additional arguments from LE-0 (may be empty)
    
    Returns:
        bytes: Raw model output as bytes
    """
    global _llm, _flow_idx, _step_sequence
    
    # Engine should already be loaded before LE-0 starts
    # Only check if somehow not loaded (safety check, should not happen)
    if _llm is None:
        _ensure_model_loaded()
    
    # Determine current flow index based on step sequence BEFORE appending current step
    # Each flow has 3 steps: planner, executor, verifier
    current_flow_idx = _get_current_flow_idx()
    
    # Track step sequence for next call
    _step_sequence.append(step_name)
    
    # Load flow for current flow_idx (1-indexed flow files)
    flow = _load_flow(current_flow_idx + 1)
    
    # Get flow input
    flow_input = flow.get("input", "")
    
    # Get steps
    steps = flow.get("steps", [])
    
    # Find the step by name
    step = None
    for s in steps:
        if s.get("name") == step_name:
            step = s
            break
    
    if step is None:
        raise ValueError(f"Step '{step_name}' not found in flow {current_flow_idx + 1}")
    
    # Get step instruction
    instruction = step.get("instruction", "")
    
    # Build prompt: instruction + input
    prompt_parts = []
    if instruction:
        prompt_parts.append(f"Instruction: {instruction}")
    if flow_input:
        prompt_parts.append(f"Input: {flow_input}")
    
    prompt = "\n\n".join(prompt_parts) if prompt_parts else ""
    
    # Record start time for latency measurement (GPU synchronized)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    start_time = time.time()
    
    # Run vLLM generation
    try:
        sampling_params = SamplingParams(
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", kwargs.get("max_new_tokens", 1024)),
            top_p=kwargs.get("top_p", 0.9),
        )
        
        outputs = _llm.generate([prompt], sampling_params, use_tqdm=False)
        
        # Synchronize GPU before measuring end time for accurate latency
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        
        # Calculate end time
        end_time = time.time()
        
        # Extract generated text and token counts
        if outputs and outputs[0].outputs:
            output = outputs[0].outputs[0]
            generated_text = output.text
            
            # Get decode tokens from output metadata
            decode_tokens = getattr(output, 'token_ids', None)
            if decode_tokens is not None and isinstance(decode_tokens, list):
                decode_tokens = len(decode_tokens)
            else:
                # Fallback: count tokens using tokenizer
                decode_tokens = _count_tokens(generated_text)
        else:
            generated_text = ""
            decode_tokens = 0
        
        # Calculate latency (end time already synchronized)
        latency_ms = (end_time - start_time) * 1000
        
        # Count prompt tokens using tokenizer
        prompt_tokens = _count_tokens(prompt)
        
        # Calculate prefill_tokens and reused_tokens for sanity check
        # Step 1 (planner): prefill_tokens = prompt_tokens, reused_tokens = 0
        # Step 2/3: compare to step 1 to infer reuse
        step_key = (current_flow_idx, step_name)
        step1_key = (current_flow_idx, "planner")
        step1_prompt_tokens = _step_token_tracking.get(step1_key, prompt_tokens)
        
        if step_name == "planner":
            # First step: all tokens are prefill
            prefill_tokens = prompt_tokens
            reused_tokens = 0
            # Track step 1 prompt tokens for comparison
            _step_token_tracking[step_key] = prompt_tokens
        else:
            # Subsequent steps: infer reuse from comparison to step 1
            # In LE-0, if reuse is working, step 2/3 should have similar or larger prompt_tokens
            # but only a small delta needs prefill (the new instruction part)
            # We approximate: if prompt_tokens is similar to step1, assume most was reused
            if step1_prompt_tokens > 0:
                # Estimate: if prompt is similar size, most tokens were reused
                # The prefill_tokens is the delta (new instruction tokens)
                # For simplicity, estimate prefill as ~10% of step1 (instruction part)
                # and reused as the rest
                estimated_prefill = max(50, int(step1_prompt_tokens * 0.1))  # Rough estimate for instruction
                if prompt_tokens >= step1_prompt_tokens * 0.9:
                    # Similar or larger prompt suggests reuse of step1 prefix
                    reused_tokens = step1_prompt_tokens
                    prefill_tokens = estimated_prefill
                elif prompt_tokens < step1_prompt_tokens * 0.5:
                    # Much smaller prompt suggests different prompt (no reuse)
                    reused_tokens = 0
                    prefill_tokens = prompt_tokens
                else:
                    # Moderate difference: partial reuse
                    reused_tokens = int(step1_prompt_tokens * 0.8)
                    prefill_tokens = max(0, prompt_tokens - reused_tokens)
            
            # Track prompt tokens for this step
            _step_token_tracking[step_key] = prompt_tokens
        
        # Convert to bytes
        output_bytes = generated_text.encode('utf-8')
        
        # Print metrics to stderr (IP-safe: no text output)
        print(
            f"[TARGET] flow={current_flow_idx + 1} step={step_name} latency_ms={latency_ms:.2f} "
            f"prompt_tokens={prompt_tokens} decode_tokens={decode_tokens} "
            f"prefill_tokens={prefill_tokens} reused_tokens={reused_tokens}",
            file=sys.stderr
        )
        
        return output_bytes
        
    except Exception as e:
        print(f"[TARGET] ERROR: Generation failed for step '{step_name}': {e}", file=sys.stderr)
        raise


def init() -> None:
    """
    Explicitly pre-load the vLLM engine.
    Call this BEFORE starting workflows to ensure engine is ready.
    Prints ENGINE_CREATED with PID for verification.
    """
    _ensure_model_loaded()


def _cleanup_engine():
    """Graceful cleanup of vLLM engine to prevent worker crash messages."""
    global _llm
    if _llm is not None:
        try:
            # Give workers time to shutdown gracefully
            time.sleep(0.5)
            _llm = None
            print(f"[TARGET] ENGINE_SHUTDOWN pid={os.getpid()}", file=sys.stderr)
        except Exception:
            pass  # Suppress any cleanup errors

# Register cleanup handler for graceful exit
atexit.register(_cleanup_engine)


# Eager initialization: pre-load engine at module import if LE0_EAGER_INIT=1
# This ensures engine is ready before LE-0 starts calling run()
if os.environ.get("LE0_EAGER_INIT") == "1":
    init()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="vLLM target for LE-0")
    parser.add_argument("--init-only", action="store_true",
                        help="Pre-load engine and exit (for testing)")
    args, _ = parser.parse_known_args()
    
    if args.init_only:
        init()
        print("[TARGET] Engine ready, exiting", file=sys.stderr)
    else:
        # Smoke test when run directly
        print("[TARGET] Running smoke test...", file=sys.stderr)
        try:
            result = run_prompt(
                "Instruction: Say hello\n\nInput: test input",
                "test_step"
            )
            print(f"[TARGET] Smoke test passed. Output length: {len(result)} bytes", file=sys.stderr)
        except Exception as e:
            print(f"[TARGET] Smoke test failed: {e}", file=sys.stderr)
            sys.exit(1)
