#!/usr/bin/env python3
"""
Flow expansion script - generates expanded flow files from prompt suite.
Uses lightweight prompts (~100 tokens) for fast benchmarks.
"""

import json
import os
import sys
import time
from pathlib import Path


def _progress(msg: str) -> None:
    """Print progress message to stderr unless QUIET=1."""
    if os.environ.get("QUIET") != "1":
        print(f"[PROGRESS] {msg}", file=sys.stderr)


def build_flows(num_flows: int = 25) -> None:
    """
    Build expanded flow files using prompts from prompt_suite.json.
    Each flow gets a unique prompt to prevent vLLM prefix caching.
    
    Args:
        num_flows: Number of workflows to generate (1-25)
    """
    num_flows = min(max(1, num_flows), 25)
    
    # Load prompt suite
    _progress("Loading prompt suite...")
    prompt_suite_path = Path("flows/prompt_suite.json")
    with open(prompt_suite_path, "r") as f:
        prompts = json.load(f)
    
    expand_start_time = time.time()
    
    # 3-step workflow template
    steps = [
        {"name": "planner", "instruction": "Analyze the request and plan your approach."},
        {"name": "executor", "instruction": "Execute your plan and provide detailed findings."},
        {"name": "verifier", "instruction": "Verify your findings and summarize the results."}
    ]
    
    _progress(f"Generating {num_flows} flows...")
    
    for i in range(1, num_flows + 1):
        # Select prompt (cycle through if needed)
        prompt = prompts[(i - 1) % len(prompts)]
        
        # Create flow with unique input
        flow = {
            "input": prompt,
            "steps": steps
        }
        
        # Write expanded flow
        output_file = f"flows/_expanded_{i:02d}.json"
        with open(output_file, "w") as f:
            json.dump(flow, f, indent=2)
    
    expand_time = time.time() - expand_start_time
    print(f"[TIMING] flow_expansion_ms={expand_time * 1000:.2f}", file=sys.stderr)
    
    # Report input size (prompt suite only, no fixtures)
    total_bytes = sum(len(p.encode('utf-8')) for p in prompts[:num_flows])
    print(f"[INPUT] prompt_bytes={total_bytes} num_prompts={num_flows}", file=sys.stderr)
    
    _progress("All flows generated")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build expanded flow files")
    parser.add_argument("--num-flows", type=int, default=25, help="Number of flows to generate (1-25)")
    # Accept but ignore legacy args for compatibility
    parser.add_argument("input_flow", nargs="?", help="(ignored - kept for compatibility)")
    parser.add_argument("--fast", action="store_true", help="(ignored - always fast)")
    args = parser.parse_args()
    
    build_flows(args.num_flows)
