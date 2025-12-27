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
from pathlib import Path
from typing import Optional, Dict, Any

# Suppress vLLM and torch internal logs before importing
logging.getLogger("vllm").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("tokenizers").setLevel(logging.ERROR)

# Suppress tqdm progress bars
os.environ.setdefault("TQDM_DISABLE", "1")

def _progress(msg: str) -> None:
    """Print progress message to stderr unless QUIET=1."""
    if os.environ.get("QUIET", "0") != "1":
        print(f"[PROGRESS] {msg}", file=sys.stderr)

try:
    from vllm import LLM, SamplingParams
except ImportError:
    print("[TARGET] ERROR: vLLM not installed. Install with: pip install vllm", file=sys.stderr)
    sys.exit(1)

# Global model and tokenizer (loaded once, reused across steps)
_llm: Optional[LLM] = None
_model_id: Optional[str] = None

# Flow tracking for LE-0 mode
_flow_idx: int = 0
_step_sequence: list = []  # Track step names in order: ["planner", "executor", "verifier", ...]
_flows_dir: Optional[Path] = None
_flows_cache: Dict[int, Dict] = {}


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
    """Ensure the vLLM model is loaded."""
    global _llm, _model_id
    
    current_model_id = _get_model_id()
    
    if _llm is None or _model_id != current_model_id:
        try:
            _progress("loading model")
            _llm = LLM(model=current_model_id, trust_remote_code=True)
            _model_id = current_model_id
            _progress("model loaded")
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
    
    Args:
        prompt: Full prompt text
        step_name: Name of the step
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
    
    Returns:
        bytes: Raw model output as bytes
    """
    global _llm
    
    _ensure_model_loaded()
    
    # Record start time for latency measurement
    start_time = time.time()
    
    # Run vLLM generation
    try:
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
        )
        
        outputs = _llm.generate([prompt], sampling_params, use_tqdm=False)
        
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
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Count prompt tokens using tokenizer
        prompt_tokens = _count_tokens(prompt)
        
        # Convert to bytes
        output_bytes = generated_text.encode('utf-8')
        
        # Print metrics to stderr (IP-safe: no text output)
        print(
            f"[TARGET] flow=0 step={step_name} latency_ms={latency_ms:.2f} "
            f"prompt_tokens={prompt_tokens} decode_tokens={decode_tokens}",
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
    
    Args:
        step_name: Name of the step (e.g., "planner", "executor", "verifier")
        **kwargs: Additional arguments from LE-0 (may be empty)
    
    Returns:
        bytes: Raw model output as bytes
    """
    global _llm, _flow_idx, _step_sequence
    
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
    
    # Record start time for latency measurement
    start_time = time.time()
    
    # Run vLLM generation
    try:
        sampling_params = SamplingParams(
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", kwargs.get("max_new_tokens", 1024)),
            top_p=kwargs.get("top_p", 0.9),
        )
        
        outputs = _llm.generate([prompt], sampling_params, use_tqdm=False)
        
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
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Count prompt tokens using tokenizer
        prompt_tokens = _count_tokens(prompt)
        
        # Convert to bytes
        output_bytes = generated_text.encode('utf-8')
        
        # Print metrics to stderr (IP-safe: no text output)
        print(
            f"[TARGET] flow={current_flow_idx + 1} step={step_name} latency_ms={latency_ms:.2f} "
            f"prompt_tokens={prompt_tokens} decode_tokens={decode_tokens}",
            file=sys.stderr
        )
        
        return output_bytes
        
    except Exception as e:
        print(f"[TARGET] ERROR: Generation failed for step '{step_name}': {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
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
