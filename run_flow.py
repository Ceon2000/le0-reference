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
    
    Flow structure (context accumulates across steps):
    - Step 1 (planner): Small prompt with task → Generates detailed plan
    - Step 2 (executor): Receives step 1 output as context → Executes plan
    - Step 3 (verifier): Receives step 1+2 outputs as context → Verifies
    
    LE-0 benefit: Reuses accumulated context from previous steps.
    vLLM baseline: Must re-prefill growing context each step.
    
    Args:
        num_flows: Number of workflows to generate (1-25)
    """
    num_flows = min(max(1, num_flows), 25)
    
    # Load prompt suite (task prompts)
    _progress("Loading prompt suite...")
    prompt_suite_path = Path("flows/prompt_suite.json")
    with open(prompt_suite_path, "r") as f:
        prompts = json.load(f)
    
    expand_start_time = time.time()
    
    # 3-step workflow template
    # Note: The runner will accumulate context by passing previous outputs
    # Step 2 gets: instruction + step1_output
    # Step 3 gets: instruction + step1_output + step2_output
    # This creates growing context that LE-0 can reuse
    steps = [
        {
            "name": "planner", 
            "instruction": """You are analyzing the helpdesk_ai codebase located in fixtures/helpdesk_ai/.

Review the codebase structure and create a detailed analysis plan. Your plan should:
1. Identify the main components and their responsibilities
2. List specific files to examine for the task
3. Outline the analysis approach step by step
4. Note any potential areas of concern

Be thorough - your plan will guide the next analysis steps."""
        },
        {
            "name": "executor", 
            "instruction": """Based on the analysis plan above, execute the analysis:

1. Follow each step from the plan
2. Document specific findings with file names and line numbers where relevant
3. Identify any bugs, issues, or improvements
4. Provide concrete examples from the code

Be detailed and specific in your findings."""
        },
        {
            "name": "verifier", 
            "instruction": """Review the analysis plan and execution findings above.

1. Verify each finding is accurate and well-supported
2. Check if all planned analysis steps were completed
3. Identify any missed areas or incomplete analysis
4. Provide a final summary with prioritized recommendations

Conclude with a confidence assessment of the analysis quality."""
        }
    ]
    
    _progress(f"Generating {num_flows} flows...")
    
    total_prompt_bytes = 0
    for i in range(1, num_flows + 1):
        # Select task prompt (cycle through if needed)
        task_prompt = prompts[(i - 1) % len(prompts)]
        
        # Create flow with lightweight input (just the task, not the repo)
        # The repo exists at fixtures/helpdesk_ai/ and model references it
        flow_input = f"""Task: {task_prompt}

The codebase to analyze is located at: fixtures/helpdesk_ai/
This is a Python helpdesk AI system with routing, scoring, validation, and storage components."""
        
        flow = {
            "input": flow_input,
            "steps": steps
        }
        
        # Write expanded flow
        output_file = f"flows/_expanded_{i:02d}.json"
        with open(output_file, "w") as f:
            json.dump(flow, f, indent=2)
        
        total_prompt_bytes += len(flow_input.encode('utf-8'))
    
    expand_time = time.time() - expand_start_time
    print(f"[TIMING] flow_expansion_ms={expand_time * 1000:.2f}", file=sys.stderr)
    
    # Report input size (lightweight prompts only)
    print(f"[INPUT] prompt_bytes={total_prompt_bytes} num_prompts={num_flows}", file=sys.stderr)
    
    _progress("All flows generated (lightweight prompts, context accumulates across steps)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build expanded flow files")
    parser.add_argument("--num-flows", type=int, default=25, help="Number of flows to generate (1-25)")
    # Accept but ignore legacy args for compatibility
    parser.add_argument("input_flow", nargs="?", help="(ignored - kept for compatibility)")
    parser.add_argument("--fast", action="store_true", help="(ignored - always fast)")
    args = parser.parse_args()
    
    build_flows(args.num_flows)
