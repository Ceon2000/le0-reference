#!/usr/bin/env python3
"""
Agent driver for retrieval-native benchmark.

Orchestrates 25 tasks × 3 steps (planner/executor/verifier).
Tracks snippet deduplication for baseline vs treatment comparison.
"""

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from repo_tool import repo_lookup, get_predefined_lookups


class SnippetTracker:
    """Tracks seen snippets for deduplication in treatment mode."""
    
    def __init__(self):
        self.seen_ids: Set[str] = set()
        self.snippets: Dict[str, str] = {}  # id -> text
        self.total_sent = 0
        self.reuse_hits = 0
    
    def has_seen(self, snippet_id: str) -> bool:
        return snippet_id in self.seen_ids
    
    def record(self, snippet_id: str, snippet_text: str) -> bool:
        """Record a snippet. Returns True if newly seen."""
        if snippet_id in self.seen_ids:
            self.reuse_hits += 1
            return False
        self.seen_ids.add(snippet_id)
        self.snippets[snippet_id] = snippet_text
        self.total_sent += 1
        return True
    
    def get_reuse_rate(self) -> float:
        total = self.total_sent + self.reuse_hits
        if total == 0:
            return 0.0
        return self.reuse_hits / total


def count_tokens(text: str) -> int:
    """Estimate token count (~4 bytes per token)."""
    return len(text.encode('utf-8')) // 4


def build_step_prompt_baseline(
    task_idx: int,
    task_text: str,
    step_name: str,
    lookups: List[Dict],
    prior_outputs: List[str]
) -> str:
    """
    Build prompt for BASELINE mode.
    
    Always includes full snippet_text for all lookups.
    """
    parts = []
    
    # Task header
    parts.append(f"## Task {task_idx}: {task_text}")
    
    # Retrieved snippets (full text always)
    if lookups:
        parts.append("\n## Retrieved Code Snippets\n")
        for lookup in lookups:
            parts.append(f"### Snippet: {lookup['source_path']} (lines {lookup['line_range']})")
            parts.append(f"```\n{lookup['snippet_text']}\n```\n")
    
    # Prior step outputs
    if prior_outputs:
        labels = ["Planner", "Executor", "Verifier"]
        parts.append("\n## Previous Analysis\n")
        for i, output in enumerate(prior_outputs):
            label = labels[i] if i < len(labels) else f"Step {i+1}"
            bounded = output[:1500] + "..." if len(output) > 1500 else output
            parts.append(f"### {label} Output\n{bounded}\n")
    
    # Step instruction
    instructions = {
        "planner": "Create a detailed analysis plan for this task. Identify what to examine.",
        "executor": "Execute the analysis based on the plan. Document specific findings.",
        "verifier": "Verify the findings and provide a summary with recommendations."
    }
    parts.append(f"\n## Your Task: {step_name.title()}\n{instructions.get(step_name, step_name)}")
    
    return "\n".join(parts)


def build_step_prompt_treatment(
    task_idx: int,
    task_text: str,
    step_name: str,
    lookups: List[Dict],
    prior_outputs: List[str],
    tracker: SnippetTracker
) -> str:
    """
    Build prompt for TREATMENT mode.
    
    Sends snippet_text only for NEW snippets.
    Uses snippet_id reference for previously seen snippets.
    """
    parts = []
    
    # Task header
    parts.append(f"## Task {task_idx}: {task_text}")
    
    # Retrieved snippets (deduplicated)
    if lookups:
        parts.append("\n## Retrieved Code Snippets\n")
        for lookup in lookups:
            snippet_id = lookup['snippet_id']
            is_new = tracker.record(snippet_id, lookup['snippet_text'])
            
            if is_new:
                # First time: include full text
                parts.append(f"### Snippet [{snippet_id}]: {lookup['source_path']} (lines {lookup['line_range']})")
                parts.append(f"```\n{lookup['snippet_text']}\n```\n")
            else:
                # Already seen: reference by ID only
                parts.append(f"### Snippet Reference: [{snippet_id}] (previously loaded)")
    
    # Prior step outputs
    if prior_outputs:
        labels = ["Planner", "Executor", "Verifier"]
        parts.append("\n## Previous Analysis\n")
        for i, output in enumerate(prior_outputs):
            label = labels[i] if i < len(labels) else f"Step {i+1}"
            bounded = output[:1500] + "..." if len(output) > 1500 else output
            parts.append(f"### {label} Output\n{bounded}\n")
    
    # Step instruction
    instructions = {
        "planner": "Create a detailed analysis plan for this task. Identify what to examine.",
        "executor": "Execute the analysis based on the plan. Document specific findings.",
        "verifier": "Verify the findings and provide a summary with recommendations."
    }
    parts.append(f"\n## Your Task: {step_name.title()}\n{instructions.get(step_name, step_name)}")
    
    return "\n".join(parts)


def load_tasks() -> List[str]:
    """Load 25 task prompts."""
    task_file = Path("tasks/prompt_suite_25.json")
    if not task_file.exists():
        raise FileNotFoundError(f"Task file not found: {task_file}")
    with open(task_file, "r") as f:
        return json.load(f)


def execute_lookups(task_idx: int) -> List[Dict]:
    """Execute predefined lookups for a task."""
    queries = get_predefined_lookups(task_idx)
    results = []
    for query in queries:
        result = repo_lookup(query)
        results.append(result)
    return results


def debug_log(task_idx: int, step_name: str, prompt: str, snippet_ids: List[str]) -> None:
    """Log debug info if DEBUG=1."""
    if os.environ.get("DEBUG") == "1":
        prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16]
        tokens = count_tokens(prompt)
        ids_str = ",".join(snippet_ids[:3])
        print(
            f"[DEBUG] task={task_idx} step={step_name} "
            f"sha256={prompt_hash} tokens={tokens} snippets=[{ids_str}]",
            file=sys.stderr
        )


STEP_NAMES = ["planner", "executor", "verifier"]


if __name__ == "__main__":
    # Test the agent driver
    tasks = load_tasks()
    print(f"Loaded {len(tasks)} tasks")
    
    # Test lookups for task 1
    lookups = execute_lookups(1)
    print(f"\nTask 1 lookups:")
    for l in lookups:
        print(f"  {l['query']} -> {l['snippet_id']} ({l['token_estimate']} tokens)")
