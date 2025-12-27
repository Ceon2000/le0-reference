#!/usr/bin/env python3
"""
Flow expansion script that injects fixture content into flow input.
"""

import json
import sys
from pathlib import Path
from fixture_loader import load_fixture


def build_expanded_flow(flow_file: str, output_file: str) -> None:
    """
    Load flow file, inject fixture content, and write expanded flow.
    
    Args:
        flow_file: Path to input flow JSON file
        output_file: Path to output expanded flow JSON file
    """
    # Load original flow
    with open(flow_file, "r") as f:
        flow = json.load(f)
    
    # Load fixture content
    fixture_text, fixture_bytes, fixture_files = load_fixture()
    
    # Get original input
    original_input = flow.get("input", "")
    
    # Combine fixture content with original input
    if fixture_text:
        combined_input = f"{original_input}\n\n{fixture_text}"
    else:
        combined_input = original_input
    
    # Update flow with expanded input
    flow["input"] = combined_input
    
    # Write expanded flow
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(flow, f, indent=2)
    
    # Print input metrics
    print(f"[INPUT] fixture_bytes={fixture_bytes} fixture_files={fixture_files}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_flow.py <input_flow> <output_flow>", file=sys.stderr)
        sys.exit(1)
    
    build_expanded_flow(sys.argv[1], sys.argv[2])

