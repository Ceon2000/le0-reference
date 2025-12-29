#!/usr/bin/env python3
"""
Flow expansion script that injects fixture content into flow input.
Includes caching to avoid regenerating flows when inputs haven't changed.
"""

import json
import os
import sys
import hashlib
import time
from pathlib import Path
from fixture_loader import load_fixture


def _progress(msg: str) -> None:
    """Print progress message to stderr unless QUIET=1."""
    if os.environ.get("QUIET", "0") != "1":
        print(f"[PROGRESS] {msg}", file=sys.stderr)


def _compute_hash(data: str) -> str:
    """Compute SHA256 hash of data."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def _load_cache() -> dict:
    """Load cache metadata from flows/.expanded_cache.json."""
    cache_file = Path("flows/.expanded_cache.json")
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache_data: dict) -> None:
    """Save cache metadata to flows/.expanded_cache.json."""
    cache_file = Path("flows/.expanded_cache.json")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(cache_data, f, indent=2)


def _check_cache_valid(fixture_hash: str, template_hash: str, num_flows: int, cache: dict) -> bool:
    """Check if cached flows are valid for current inputs."""
    if cache.get("fixture_hash") != fixture_hash:
        return False
    if cache.get("template_hash") != template_hash:
        return False
    if cache.get("num_flows") != num_flows:
        return False
    
    # Check if all expanded files exist
    expanded_files = cache.get("expanded_files", [])
    if len(expanded_files) != num_flows:
        return False
    
    for fname in expanded_files:
        if not Path(fname).exists():
            return False
    
    return True


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
    Uses caching to avoid regenerating flows when inputs haven't changed.
    
    Args:
        flow_file: Path to input flow JSON file
        num_flows: Number of workflows to generate (1-25)
    """
    num_flows = min(max(1, num_flows), 25)  # Clamp to 1-25
    
    # Timing: flow expansion start
    expand_start_time = time.time()
    
    # Load cache
    cache = _load_cache()
    
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
    
    # Load fixture once to get metrics and compute hash
    _progress("Loading fixture files...")
    fixture_text, fixture_bytes, fixture_files = load_fixture()
    _progress(f"Loaded {fixture_files} fixture files ({fixture_bytes} bytes)")
    fixture_hash = _compute_hash(fixture_text)
    
    # Load original flow once and compute hash
    _progress("Loading flow file...")
    with open(flow_file, "r") as f:
        flow_template = json.load(f)
    
    template_hash = _compute_hash(json.dumps(flow_template, sort_keys=True))
    original_input = flow_template.get("input", "")
    
    # Check cache validity
    if _check_cache_valid(fixture_hash, template_hash, num_flows, cache):
        _progress(f"Using cached expanded flows (fixture_hash={fixture_hash[:8]}..., template_hash={template_hash[:8]}...)")
        expand_time = time.time() - expand_start_time
        print(f"[TIMING] flow_expansion_ms={expand_time * 1000:.2f} (cached)", file=sys.stderr)
        # Still print [INPUT] line for consistency
        print(f"[INPUT] fixture_bytes={fixture_bytes} fixture_files={fixture_files}")
        return
    
    # Cache miss: regenerate flows
    _progress(f"Regenerating expanded flows (cache miss: fixture_hash={fixture_hash[:8]}..., template_hash={template_hash[:8]}...)")
    
    expanded_files = []
    # Generate each workflow file
    for i in range(1, num_flows + 1):
        output_file = f"flows/_expanded_{i:02d}.json"
        expanded_files.append(output_file)
        
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
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(flow, f, indent=2)
        
        # Print input metrics for each workflow (required output)
        print(f"[INPUT] fixture_bytes={fixture_bytes} fixture_files={fixture_files}")
    
    # Save cache
    cache_data = {
        "fixture_hash": fixture_hash,
        "template_hash": template_hash,
        "num_flows": num_flows,
        "expanded_files": expanded_files,
        "created_at": time.time()
    }
    _save_cache(cache_data)
    
    expand_time = time.time() - expand_start_time
    print(f"[TIMING] flow_expansion_ms={expand_time * 1000:.2f} (generated)", file=sys.stderr)
    _progress("All flows generated")


def build_fast_flows(flow_file: str, num_flows: int = 25) -> None:
    """
    Build lightweight flows for fast testing.
    Each flow has unique ID to prevent prefix caching but minimal prompt size.
    
    Args:
        flow_file: Path to input flow JSON file (template)
        num_flows: Number of workflows to generate (1-25)
    """
    import uuid
    
    num_flows = min(max(1, num_flows), 25)
    
    # Load template flow
    _progress("Loading flow template...")
    with open(flow_file, "r") as f:
        template = json.load(f)
    
    expand_start_time = time.time()
    
    # Sample code snippets for variety (all short)
    code_snippets = [
        '''def process_items(items):
    result = []
    for i in range(len(items)):
        if items[i] > 0:
            result.append(items[i] * 2)
    return result''',
        '''def find_max(numbers):
    if not numbers:
        return None
    max_val = numbers[0]
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val''',
        '''class DataStore:
    def __init__(self):
        self.data = {}
    def get(self, key):
        return self.data[key]
    def set(self, key, value):
        self.data[key] = value''',
        '''async def fetch_data(url):
    response = await http_get(url)
    if response.status != 200:
        raise Error("Failed")
    return response.json()''',
        '''def validate_email(email):
    if "@" not in email:
        return False
    parts = email.split("@")
    return len(parts) == 2 and len(parts[1]) > 0'''
    ]
    
    _progress(f"Generating {num_flows} fast flows...")
    
    for i in range(1, num_flows + 1):
        # Generate unique task ID
        task_id = f"{uuid.uuid4().hex[:8]}_{i:02d}"
        
        # Select code snippet (cycle through)
        snippet = code_snippets[(i - 1) % len(code_snippets)]
        
        # Build lightweight input (~200-300 tokens)
        flow_input = f"""Task ID: {task_id}

Analyze this code and identify any issues:

```python
{snippet}
```

Consider: correctness, edge cases, performance, readability.
Focus on practical improvements that would help in production."""
        
        # Create flow with unique input
        flow = {
            "input": flow_input,
            "steps": template.get("steps", [])
        }
        
        # Write expanded flow
        output_file = f"flows/_expanded_{i:02d}.json"
        with open(output_file, "w") as f:
            json.dump(flow, f, indent=2)
    
    expand_time = time.time() - expand_start_time
    print(f"[TIMING] flow_expansion_ms={expand_time * 1000:.2f} (fast mode)", file=sys.stderr)
    print(f"[INPUT] fixture_bytes=0 fixture_files=0", file=sys.stderr)
    _progress("All fast flows generated")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build expanded flow files")
    parser.add_argument("input_flow", help="Path to input flow JSON file")
    parser.add_argument("output_flow", nargs="?", help="Path to output expanded flow JSON file (optional if --num-flows used)")
    parser.add_argument("--num-flows", type=int, default=None, help="Generate multiple flows (1-25)")
    parser.add_argument("--fast", action="store_true", help="Use fast mode with lightweight prompts")
    args = parser.parse_args()
    
    if args.num_flows:
        if args.fast:
            build_fast_flows(args.input_flow, args.num_flows)
        else:
            build_multiple_flows(args.input_flow, args.num_flows)
    else:
        if not args.output_flow:
            print("ERROR: output_flow required when --num-flows not specified", file=sys.stderr)
            sys.exit(1)
        build_expanded_flow(args.input_flow, args.output_flow)

