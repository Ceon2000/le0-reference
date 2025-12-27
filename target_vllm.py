#!/usr/bin/env python3
"""
vLLM target implementation for LE-0.
Provides a cached vLLM model wrapper that accepts LE-0 step calls.
"""

import os
import sys
import time
import hashlib
from typing import Optional, Dict, Any

try:
    from vllm import LLM, SamplingParams
except ImportError:
    print("[TARGET] ERROR: vLLM not installed. Install with: pip install vllm", file=sys.stderr)
    sys.exit(1)

# Global cached model and tokenizer
_cached_llm: Optional[LLM] = None
_model_id: Optional[str] = None


def _get_model_id() -> str:
    """Get model ID from environment or default."""
    return os.environ.get("MODEL", "allenai/Olmo-3-7B-Think")


def _ensure_model_loaded():
    """Ensure the vLLM model is loaded and cached."""
    global _cached_llm, _model_id
    
    current_model_id = _get_model_id()
    
    if _cached_llm is None or _model_id != current_model_id:
        try:
            print(f"[TARGET] Loading model: {current_model_id}", file=sys.stderr)
            _cached_llm = LLM(model=current_model_id, trust_remote_code=True)
            _model_id = current_model_id
            print(f"[TARGET] Model loaded successfully", file=sys.stderr)
        except Exception as e:
            print(f"[TARGET] ERROR: Failed to load model '{current_model_id}': {e}", file=sys.stderr)
            raise


def _count_tokens(text: str) -> int:
    """Count tokens using the model's tokenizer."""
    global _cached_llm
    if _cached_llm is None:
        return len(text.split())  # Fallback approximation
    try:
        # Access the tokenizer through the LLM engine
        tokenizer = _cached_llm.llm_engine.tokenizer.tokenizer
        return len(tokenizer.encode(text))
    except Exception:
        # Fallback to word count approximation
        return len(text.split())


def run(step_name: str, **kwargs) -> bytes:
    """
    Run a single LE-0 step through vLLM.
    
    Args:
        step_name: Name of the step (e.g., "planner", "executor", "verifier")
        **kwargs: Additional arguments from LE-0. Expected keys:
            - prompt_prefix: Optional shared prefix
            - role: Role description
            - instruction: Step instruction
            - input: Input text for this step
    
    Returns:
        bytes: Raw model output as bytes
    """
    global _cached_llm
    
    _ensure_model_loaded()
    
    # Extract prompt components from kwargs (tolerant to missing keys)
    prompt_prefix = kwargs.get("prompt_prefix", "")
    role = kwargs.get("role", "")
    instruction = kwargs.get("instruction", "")
    input_text = kwargs.get("input", "")
    
    # Build prompt from components
    prompt_parts = []
    if prompt_prefix:
        prompt_parts.append(prompt_prefix)
    if role:
        prompt_parts.append(f"Role: {role}")
    if instruction:
        prompt_parts.append(f"Instruction: {instruction}")
    if input_text:
        prompt_parts.append(f"Input: {input_text}")
    
    prompt = "\n\n".join(prompt_parts) if prompt_parts else ""
    
    # Record start time for latency measurement
    start_time = time.time()
    
    # Run vLLM generation
    try:
        sampling_params = SamplingParams(
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 1024),
            top_p=kwargs.get("top_p", 0.9),
        )
        
        outputs = _cached_llm.generate([prompt], sampling_params)
        
        # Extract generated text and token counts
        if outputs and outputs[0].outputs:
            output = outputs[0].outputs[0]
            generated_text = output.text
            
            # Get decode tokens from output metadata
            # vLLM's CompletionOutput has token_ids attribute
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
        
        # Calculate hash
        output_hash = hashlib.sha256(output_bytes).hexdigest()[:8]
        
        # Print metrics (IP-safe: no text output)
        print(
            f"[TARGET] step={step_name} latency_ms={latency_ms:.2f} "
            f"prompt_tokens={prompt_tokens} decode_tokens={decode_tokens} "
            f"output_hash={output_hash}",
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
        result = run(
            "test_step",
            prompt_prefix="Test prefix",
            role="Test role",
            instruction="Say hello",
            input="test input"
        )
        print(f"[TARGET] Smoke test passed. Output length: {len(result)} bytes", file=sys.stderr)
    except Exception as e:
        print(f"[TARGET] Smoke test failed: {e}", file=sys.stderr)
        sys.exit(1)

