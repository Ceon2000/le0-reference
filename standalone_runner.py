#!/usr/bin/env python3
"""
Standalone runner that executes multiple workflows sequentially.
Pre-loads vLLM engine once before all workflows to avoid repeated initialization.
"""

import json
import os
import sys
import time
from pathlib import Path
from target_vllm import run_prompt, _ensure_model_loaded


def execute_workflow(flow_file: str, flow_idx: int) -> None:
    """
    Execute a single workflow from an expanded flow file.
    Context accumulates across steps:
    - Step 1: instruction + input
    - Step 2: instruction + input + step1_output
    - Step 3: instruction + input + step1_output + step2_output
    
    Args:
        flow_file: Path to expanded flow JSON file
        flow_idx: Flow index (1-based)
    """
    # Load flow
    with open(flow_file, "r") as f:
        flow = json.load(f)
    
    # Get flow input
    flow_input = flow.get("input", "")
    
    # Get steps
    steps = flow.get("steps", [])
    
    # Track accumulated context from previous steps
    accumulated_context = ""
    
    # Execute each step sequentially, accumulating outputs
    for step in steps:
        step_name = step.get("name", "unknown")
        instruction = step.get("instruction", "")
        
        # Build prompt: instruction + input + accumulated context from previous steps
        prompt_parts = []
        
        # Add accumulated context first (previous step outputs)
        if accumulated_context:
            prompt_parts.append(f"## Previous Analysis\n\n{accumulated_context}")
        
        # Add current step instruction
        if instruction:
            prompt_parts.append(f"## Current Task\n\n{instruction}")
        
        # Add original flow input (task description)
        if flow_input:
            prompt_parts.append(f"## Original Request\n\n{flow_input}")
        
        prompt = "\n\n".join(prompt_parts) if prompt_parts else ""
        
        # Call run_prompt and capture output for accumulation
        output_bytes = run_prompt(prompt, step_name, max_tokens=1024, temperature=0.7)
        
        # Accumulate this step's output for subsequent steps
        output_text = output_bytes.decode('utf-8', errors='replace') if output_bytes else ""
        accumulated_context += f"\n\n### {step_name.title()} Output\n\n{output_text}"


def execute_standalone(num_flows: int = 25) -> None:
    """
    Execute multiple workflows sequentially.
    Pre-loads vLLM engine once before all workflows.
    
    Args:
        num_flows: Number of workflows to execute (1-25)
    """
    num_flows = min(max(1, num_flows), 25)  # Clamp to 1-25
    
    # Timing: benchmark start
    benchmark_start_time = time.time()
    
    # Pre-load engine once before all workflows
    # Timing is logged inside _ensure_model_loaded() (only once)
    _ensure_model_loaded()
    
    # Log workflow loop start with PID for lifecycle verification
    print(f"[RUNNER] WORKFLOW_LOOP_START pid={os.getpid()}", file=sys.stderr)
    
    # Execute all workflows
    workflow_times = []
    for i in range(1, num_flows + 1):
        flow_file = f"flows/_expanded_{i:02d}.json"
        
        if not os.path.exists(flow_file):
            print(f"[PROGRESS] Warning: Flow file {flow_file} not found, skipping", file=sys.stderr)
            continue
        
        # Log each workflow start with PID
        print(f"[RUNNER] WORKFLOW_{i}_START pid={os.getpid()}", file=sys.stderr)
        
        workflow_start = time.time()
        execute_workflow(flow_file, i)
        workflow_time = time.time() - workflow_start
        workflow_times.append(workflow_time)
        print(f"[TIMING] workflow_{i}_ms={workflow_time * 1000:.2f}", file=sys.stderr)
    
    # Timing: benchmark end
    benchmark_total_time = time.time() - benchmark_start_time
    print(f"[TIMING] benchmark_total_ms={benchmark_total_time * 1000:.2f}", file=sys.stderr)
    print(f"[TIMING] avg_workflow_ms={sum(workflow_times) / len(workflow_times) * 1000:.2f}" if workflow_times else "[TIMING] avg_workflow_ms=0.00", file=sys.stderr)


if __name__ == "__main__":
    num_flows = int(os.environ.get("NUM_FLOWS", "25"))
    execute_standalone(num_flows)
