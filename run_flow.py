#!/usr/bin/env python3
"""
Flow expansion script that injects fixture content into flow input.
"""

import json
import os
import sys
from pathlib import Path
from fixture_loader import load_fixture


def _progress(msg: str) -> None:
    """Print progress message to stderr unless QUIET=1."""
    if os.environ.get("QUIET", "0") != "1":
        print(f"[PROGRESS] {msg}", file=sys.stderr)


def build_expanded_flow(flow_file: str, output_file: str) -> None:
    """
    Load flow file, inject fixture content, and write expanded flow.
    
    Args:
        flow_file: Path to input flow JSON file
        output_file: Path to output expanded flow JSON file
    """
    # Load original flow
    _progress("Loading flow file...")
    with open(flow_file, "r") as f:
        flow = json.load(f)
    
    # Load fixture content
    _progress("Loading fixture files...")
    fixture_text, fixture_bytes, fixture_files = load_fixture()
    _progress(f"Loaded {fixture_files} fixture files ({fixture_bytes} bytes)")
    
    # Get original input
    original_input = flow.get("input", "")
    
    # Combine original input and fixture content
    if fixture_text:
        combined_input = f"{original_input}\n\n{fixture_text}"
    else:
        combined_input = original_input
    
    # Update flow with expanded input
    flow["input"] = combined_input
    
    # Write expanded flow
    _progress(f"Writing expanded flow to {output_file}...")
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(flow, f, indent=2)
    _progress("Expanded flow written")
    
    # Print input metrics to stdout (required output)
    print(f"[INPUT] fixture_bytes={fixture_bytes} fixture_files={fixture_files}")


def build_multiple_flows(flow_file: str, num_flows: int = 25) -> None:
    """
    Build multiple expanded flows using prompts from the prompt suite.
    
    Args:
        flow_file: Path to input flow JSON file
        num_flows: Number of workflows to generate (1-25)
    """
    num_flows = min(max(1, num_flows), 25)  # Clamp to 1-25
    
    # Load prompt suite
    _progress("Loading prompt suite...")
    prompt_suite_path = Path("flows/prompt_suite.json")
    if not prompt_suite_path.exists():
        print("ERROR: flows/prompt_suite.json not found", file=sys.stderr)
        sys.exit(1)
    
    with open(prompt_suite_path, "r") as f:
        prompt_suite = json.load(f)
    
    if len(prompt_suite) < num_flows:
        print(f"ERROR: Prompt suite has only {len(prompt_suite)} prompts, but {num_flows} requested", file=sys.stderr)
        sys.exit(1)
    
    # Load fixture once to get metrics
    _progress("Loading fixture files...")
    fixture_text, fixture_bytes, fixture_files = load_fixture()
    _progress(f"Loaded {fixture_files} fixture files ({fixture_bytes} bytes)")
    
    # Load original flow once
    _progress("Loading flow file...")
    with open(flow_file, "r") as f:
        flow_template = json.load(f)
    
    original_input = flow_template.get("input", "")
    
    # Generate each workflow file
    for i in range(1, num_flows + 1):
        output_file = f"flows/_expanded_{i:02d}.json"
        
        # Select prompt from suite (0-indexed)
        selected_prompt = prompt_suite[i - 1]
        
        # Combine selected prompt, original input, and fixture content
        if fixture_text:
            combined_input = f"{selected_prompt}\n\n{original_input}\n\n{fixture_text}"
        else:
            combined_input = f"{selected_prompt}\n\n{original_input}"
        
        # Update flow with expanded input
        flow = flow_template.copy()
        flow["input"] = combined_input
        
        # Write expanded flow
        _progress(f"Writing expanded flow to {output_file}...")
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(flow, f, indent=2)
        
        # Print input metrics for each workflow (required output)
        print(f"[INPUT] fixture_bytes={fixture_bytes} fixture_files={fixture_files}")
    
    _progress("All flows generated")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build expanded flow files")
    parser.add_argument("input_flow", help="Path to input flow JSON file")
    parser.add_argument("output_flow", nargs="?", help="Path to output expanded flow JSON file (optional if --num-flows used)")
    parser.add_argument("--num-flows", type=int, default=None, help="Generate multiple flows (1-25)")
    args = parser.parse_args()
    
    if args.num_flows:
        build_multiple_flows(args.input_flow, args.num_flows)
    else:
        if not args.output_flow:
            print("ERROR: output_flow required when --num-flows not specified", file=sys.stderr)
            sys.exit(1)
        build_expanded_flow(args.input_flow, args.output_flow)

