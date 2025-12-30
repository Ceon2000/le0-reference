#!/usr/bin/env python3
"""
Prompt builder for LE-0 session-native client contract.

ARCHITECTURE:
- Baseline: Every step includes full fixtures (~26K tokens)
- Treatment: Warmup sends fixtures once, steps use opaque handle (~4K tokens)

This module is IP-safe: treats LE-0 as a black box with opaque handles.
"""

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from fixture_loader import load_fixture

# Cache fixture content (loaded once per process)
_fixture_cache: Optional[str] = None
_fixture_tokens: int = 0


def _get_fixture_content() -> tuple:
    """Load fixture content once, cache for reuse. Returns (text, token_estimate)."""
    global _fixture_cache, _fixture_tokens
    if _fixture_cache is None:
        content, total_bytes, file_count = load_fixture("fixtures/helpdesk_ai")
        _fixture_cache = content
        # Rough token estimate: ~4 bytes per token
        _fixture_tokens = len(content.encode('utf-8')) // 4
    return _fixture_cache, _fixture_tokens


def get_contract_hash() -> str:
    """Generate stable contract hash for session identification."""
    fixtures, _ = _get_fixture_content()
    return hashlib.sha256(fixtures.encode('utf-8')).hexdigest()[:16]


def build_warmup_prompt(fixtures_ref: str = "fixtures/helpdesk_ai") -> str:
    """
    Build warmup prompt for treatment mode.
    
    Warmup sends full fixtures ONCE. LE-0 returns an opaque context_handle
    that references the retained context server-side.
    
    Args:
        fixtures_ref: Reference path to fixtures (for documentation)
    
    Returns:
        Complete warmup prompt with full fixtures
    """
    fixtures_text, _ = _get_fixture_content()
    contract_hash = get_contract_hash()
    
    return f"""## Session Warmup

Contract Hash: {contract_hash}
Fixtures Reference: {fixtures_ref}

## Codebase to Analyze

{fixtures_text}

## Instructions

This is a warmup request to establish session context. The codebase above will be referenced in subsequent requests using an opaque handle. Please acknowledge receipt and confirm context is retained."""


def build_step_prompt_baseline(
    step_name: str,
    task: str,
    prior_outputs: Optional[List[str]] = None
) -> str:
    """
    Build step prompt for BASELINE mode (native vLLM).
    
    Baseline: Always includes full fixtures (~26K tokens per step).
    This represents standard vLLM usage without any session state.
    
    Args:
        step_name: Step name (planner/executor/verifier)
        task: User task description
        prior_outputs: Outputs from prior steps in this flow
    
    Returns:
        Complete prompt with full fixtures
    """
    fixtures_text, _ = _get_fixture_content()
    
    prompt_parts = []
    
    # Full fixtures (sent every step in baseline)
    prompt_parts.append(f"## Codebase to Analyze\n\n{fixtures_text}")
    
    # Prior step outputs (bounded)
    if prior_outputs:
        accumulated = ""
        step_labels = ["Planner", "Executor", "Verifier"]
        for i, output in enumerate(prior_outputs):
            label = step_labels[i] if i < len(step_labels) else f"Step {i+1}"
            # Bound prior output to first 2000 chars to prevent unbounded growth
            bounded_output = output[:2000] + "..." if len(output) > 2000 else output
            accumulated += f"\n\n### {label} Output\n\n{bounded_output}"
        if accumulated:
            prompt_parts.append(f"## Previous Analysis{accumulated}")
    
    # Step instruction
    instruction = _get_step_instruction(step_name)
    prompt_parts.append(f"## Current Task\n\n{instruction}")
    
    # User task
    prompt_parts.append(f"## Original Request\n\n{task}")
    
    return "\n\n".join(prompt_parts)


def build_step_prompt_treatment(
    step_name: str,
    task: str,
    context_handle: str,
    prior_outputs: Optional[List[str]] = None
) -> str:
    """
    Build step prompt for TREATMENT mode (LE-0 session-native).
    
    Treatment: Uses opaque handle instead of full fixtures (~4K tokens).
    Fixtures are retained server-side and referenced by handle.
    
    Args:
        step_name: Step name (planner/executor/verifier)
        task: User task description
        context_handle: Opaque handle from warmup (references retained fixtures)
        prior_outputs: Outputs from prior steps in this flow
    
    Returns:
        Compact prompt with handle reference
    """
    prompt_parts = []
    
    # Opaque handle reference (NOT full fixtures)
    prompt_parts.append(f"## Context Reference\n\nContext Handle: {context_handle}\n\nNote: Full codebase is retained server-side via the handle above.")
    
    # Prior step outputs (bounded)
    if prior_outputs:
        accumulated = ""
        step_labels = ["Planner", "Executor", "Verifier"]
        for i, output in enumerate(prior_outputs):
            label = step_labels[i] if i < len(step_labels) else f"Step {i+1}"
            bounded_output = output[:2000] + "..." if len(output) > 2000 else output
            accumulated += f"\n\n### {label} Output\n\n{bounded_output}"
        if accumulated:
            prompt_parts.append(f"## Previous Analysis{accumulated}")
    
    # Step instruction
    instruction = _get_step_instruction(step_name)
    prompt_parts.append(f"## Current Task\n\n{instruction}")
    
    # User task
    prompt_parts.append(f"## Original Request\n\n{task}")
    
    return "\n\n".join(prompt_parts)


def _get_step_instruction(step_name: str) -> str:
    """Get instruction for a specific step."""
    instructions = {
        "planner": """You are analyzing the helpdesk_ai codebase.

Review the codebase structure and create a detailed analysis plan. Your plan should:
1. Identify the main components and their responsibilities
2. List specific files to examine for the task
3. Outline the analysis approach step by step
4. Note any potential areas of concern

Be thorough - your plan will guide the next analysis steps.""",

        "executor": """Based on the analysis plan above, execute the analysis:

1. Follow each step from the plan
2. Document specific findings with file names and line numbers where relevant
3. Identify any bugs, issues, or improvements
4. Provide concrete examples from the code

Be detailed and specific in your findings.""",

        "verifier": """Review the analysis plan and execution findings above.

1. Verify each finding is accurate and well-supported
2. Check if all planned analysis steps were completed
3. Identify any missed areas or incomplete analysis
4. Provide a final summary with prioritized recommendations

Conclude with a confidence assessment of the analysis quality."""
    }
    return instructions.get(step_name, f"Execute step: {step_name}")


def count_tokens(text: str) -> int:
    """Estimate token count (~4 bytes per token)."""
    return len(text.encode('utf-8')) // 4


def get_fixture_token_count() -> int:
    """Get cached fixture token count."""
    _, tokens = _get_fixture_content()
    return tokens


def get_prompt_hash(prompt: str) -> str:
    """Get SHA256 hash of prompt for verification."""
    return hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16]


def debug_log_prompt(mode: str, step_name: str, prompt: str, flow_idx: int = 0) -> None:
    """Log prompt hash to stderr if DEBUG_PROMPTS=1."""
    if os.environ.get("DEBUG_PROMPTS") == "1":
        prompt_hash = get_prompt_hash(prompt)
        prompt_len = len(prompt.encode('utf-8'))
        tokens = count_tokens(prompt)
        print(
            f"[HASH] mode={mode} flow={flow_idx} step={step_name} "
            f"sha256={prompt_hash} bytes={prompt_len} tokens={tokens}",
            file=sys.stderr
        )


# Step names in canonical order
STEP_NAMES = ["planner", "executor", "verifier"]


def load_flow(flow_idx: int, flows_dir: str = "flows") -> dict:
    """Load a flow file by index."""
    flow_file = Path(flows_dir) / f"_expanded_{flow_idx:02d}.json"
    if not flow_file.exists():
        raise FileNotFoundError(f"Flow file not found: {flow_file}")
    with open(flow_file, "r") as f:
        return json.load(f)


def get_task_from_flow(flow: dict) -> str:
    """Extract task description from flow."""
    return flow.get("input", "")
