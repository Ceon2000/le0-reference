#!/usr/bin/env python3
"""
Standalone runner that executes flow steps directly using target_vllm.run
without LE-0.
"""

import json
import sys
from target_vllm import run


def execute_standalone(flow_file: str) -> None:
    """
    Execute flow steps directly using target_vllm.run.
    
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python standalone_runner.py <flow_file>", file=sys.stderr)
        sys.exit(1)
    
    execute_standalone(sys.argv[1])

