#!/usr/bin/env python3
"""
Standalone runner that executes multiple workflows sequentially.
"""

import json
import os
import sys
from target_vllm import run


def execute_one_workflow(flow_file: str) -> None:
    """
    Execute a single workflow using target_vllm.run.
    
    Args:
        flow_file: Path to expanded flow JSON file
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
        
        # Call target_vllm.run with consistent kwargs shape
        kwargs = {
            "instruction": instruction,
            "input": flow_input,
            "max_tokens": 1024,
            "temperature": 0.7,
        }
        
        # Run step (target_vllm handles printing)
        run(step_name, **kwargs)


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
        
        execute_one_workflow(flow_file)


if __name__ == "__main__":
    num_flows = int(os.environ.get("NUM_FLOWS", "25"))
    execute_standalone(num_flows)

