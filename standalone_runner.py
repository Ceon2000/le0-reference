#!/usr/bin/env python3
"""
Standalone runner that executes multiple workflows sequentially.
"""

import json
import os
import sys
from pathlib import Path
from target_vllm import run_prompt


def execute_one_workflow(flow_file: str, flow_idx: int) -> None:
    """
    Execute a single workflow using target_vllm.run_prompt.
    
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
    
    # Execute each step sequentially
    for step in steps:
        step_name = step.get("name", "unknown")
        instruction = step.get("instruction", "")
        
        # Build prompt: instruction + input
        prompt_parts = []
        if instruction:
            prompt_parts.append(f"Instruction: {instruction}")
        if flow_input:
            prompt_parts.append(f"Input: {flow_input}")
        
        prompt = "\n\n".join(prompt_parts) if prompt_parts else ""
        
        # Call run_prompt (standalone path)
        run_prompt(prompt, step_name, max_tokens=1024, temperature=0.7)


def execute_standalone(num_flows: int = 25) -> None:
    """
    Execute multiple workflows sequentially.
    
    Args:
        num_flows: Number of workflows to execute (1-25)
    """
    num_flows = min(max(1, num_flows), 25)  # Clamp to 1-25
    
    for i in range(1, num_flows + 1):
        flow_file = f"flows/_expanded_{i:02d}.json"
        
        if not os.path.exists(flow_file):
            print(f"[PROGRESS] Warning: Flow file {flow_file} not found, skipping", file=sys.stderr)
            continue
        
        execute_one_workflow(flow_file, i)


if __name__ == "__main__":
    num_flows = int(os.environ.get("NUM_FLOWS", "25"))
    execute_standalone(num_flows)
