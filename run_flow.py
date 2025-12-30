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
    Each flow gets the FULL synthetic repo as shared context.
    
    Args:
        num_flows: Number of workflows to generate (1-25)
    """
    num_flows = min(max(1, num_flows), 25)
    
    # Load the synthetic repo as shared context
    from fixture_loader import load_fixture
    _progress("Loading synthetic repo (fixtures/helpdesk_ai)...")
    repo_content, repo_bytes, file_count = load_fixture("fixtures/helpdesk_ai")
    
    if not repo_content:
        print("[ERROR] Failed to load fixtures/helpdesk_ai - no files found", file=sys.stderr)
        sys.exit(1)
    
    _progress(f"Loaded {file_count} files, {repo_bytes} bytes from synthetic repo")
    
    # Load prompt suite (task prompts)
    _progress("Loading prompt suite...")
    prompt_suite_path = Path("flows/prompt_suite.json")
    with open(prompt_suite_path, "r") as f:
        prompts = json.load(f)
    
    expand_start_time = time.time()
    
    # 3-step workflow template - each step works on the SAME shared context
    steps = [
        {"name": "planner", "instruction": "Analyze the codebase and plan your approach to address the task."},
        {"name": "executor", "instruction": "Execute your analysis plan and provide detailed findings from the codebase."},
        {"name": "verifier", "instruction": "Verify the findings are accurate and summarize the results."}
    ]
    
    _progress(f"Generating {num_flows} flows with shared context...")
    
    for i in range(1, num_flows + 1):
        # Select task prompt (cycle through if needed)
        task_prompt = prompts[(i - 1) % len(prompts)]
        
        # Create flow with FULL repo context + task
        # The input includes both the repo content AND the task prompt
        flow_input = f"""## Synthetic Codebase

The following is a complete codebase that you need to analyze:

{repo_content}

## Task

{task_prompt}
"""
        
        flow = {
            "input": flow_input,
            "steps": steps
        }
        
        # Write expanded flow
        output_file = f"flows/_expanded_{i:02d}.json"
        with open(output_file, "w") as f:
            json.dump(flow, f, indent=2)
    
    expand_time = time.time() - expand_start_time
    print(f"[TIMING] flow_expansion_ms={expand_time * 1000:.2f}", file=sys.stderr)
    
    # Report input size (repo + prompts)
    context_bytes = len(repo_content.encode('utf-8'))
    print(f"[INPUT] context_bytes={context_bytes} repo_files={file_count} num_prompts={num_flows}", file=sys.stderr)
    
    _progress("All flows generated with shared repo context")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build expanded flow files")
    parser.add_argument("--num-flows", type=int, default=25, help="Number of flows to generate (1-25)")
    # Accept but ignore legacy args for compatibility
    parser.add_argument("input_flow", nargs="?", help="(ignored - kept for compatibility)")
    parser.add_argument("--fast", action="store_true", help="(ignored - always fast)")
    args = parser.parse_args()
    
    build_flows(args.num_flows)
