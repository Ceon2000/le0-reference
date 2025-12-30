#!/usr/bin/env python3
"""
LE-0 runner - TREATMENT mode for 25-task retrieval-native benchmark.

TREATMENT CONTRACT:
- Sends snippet_text only the FIRST time a snippet is retrieved
- Uses snippet_id reference for subsequent uses
- Cross-task deduplication via SnippetTracker
"""

import json
import os
import sys
import time
from pathlib import Path

from agent_driver import (
    load_tasks,
    execute_lookups,
    build_step_prompt_treatment,
    count_tokens,
    debug_log,
    SnippetTracker,
    STEP_NAMES,
)
from target_vllm import run_prompt, _ensure_model_loaded


def execute_task(
    task_idx: int,
    task_text: str,
    tracker: SnippetTracker
) -> dict:
    """Execute a single task (3 steps) in TREATMENT mode with deduplication."""
    prior_outputs = []
    task_metrics = {
        "task_idx": task_idx,
        "task_text": task_text[:50],
        "steps": [],
        "total_client_sent_tokens": 0,
        "total_snippet_tokens": 0,
        "new_snippets": 0,
        "reused_snippets": 0,
        "total_output_tokens": 0,
        "total_latency_ms": 0,
        "snippet_ids": [],
    }
    
    # Get lookups for this task
    lookups = execute_lookups(task_idx)
    task_metrics["snippet_ids"] = [l["snippet_id"] for l in lookups]
    
    # Count new vs reused snippets BEFORE recording
    for l in lookups:
        if tracker.has_seen(l["snippet_id"]):
            task_metrics["reused_snippets"] += 1
        else:
            task_metrics["new_snippets"] += 1
    
    for step_name in STEP_NAMES:
        # Build prompt with deduplication
        prompt = build_step_prompt_treatment(
            task_idx, task_text, step_name, lookups, prior_outputs, tracker
        )
        
        client_sent_tokens = count_tokens(prompt)
        
        # Estimate snippet tokens actually sent (new only)
        new_snippet_tokens = sum(
            l["token_estimate"] for l in lookups 
            if not tracker.has_seen(l["snippet_id"])
        )
        
        debug_log(task_idx, step_name, prompt, task_metrics["snippet_ids"])
        
        output_bytes, metrics = run_prompt(
            prompt=prompt,
            step_name=step_name,
            flow_idx=task_idx,
            max_tokens=512,
            temperature=0.7,
        )
        
        output_text = output_bytes.decode('utf-8', errors='replace')
        prior_outputs.append(output_text)
        
        step_metrics = {
            "step_name": step_name,
            "client_sent_tokens": client_sent_tokens,
            "new_snippet_tokens": new_snippet_tokens,
            "output_tokens": metrics.get("output_tokens", 0),
            "latency_ms": metrics.get("latency_ms", 0),
        }
        task_metrics["steps"].append(step_metrics)
        task_metrics["total_client_sent_tokens"] += client_sent_tokens
        task_metrics["total_snippet_tokens"] += new_snippet_tokens
        task_metrics["total_output_tokens"] += metrics.get("output_tokens", 0)
        task_metrics["total_latency_ms"] += metrics.get("latency_ms", 0)
    
    return task_metrics


def execute_treatment(num_tasks: int = 25) -> dict:
    """Execute 25-task benchmark in TREATMENT mode with deduplication."""
    num_tasks = min(max(1, num_tasks), 25)
    
    start_time = time.time()
    _ensure_model_loaded()
    
    tasks = load_tasks()
    tracker = SnippetTracker()
    
    print(f"[RUNNER] TREATMENT_START tasks={num_tasks}", file=sys.stderr)
    
    all_tasks = []
    
    for i in range(1, num_tasks + 1):
        task_text = tasks[i - 1]
        print(f"[RUNNER] TASK_{i}_START seen_snippets={len(tracker.seen_ids)}", file=sys.stderr)
        task_start = time.time()
        
        task_metrics = execute_task(i, task_text, tracker)
        all_tasks.append(task_metrics)
        
        task_time = (time.time() - task_start) * 1000
        print(f"[TIMING] task_{i}_ms={task_time:.2f} new={task_metrics['new_snippets']} reused={task_metrics['reused_snippets']}", file=sys.stderr)
    
    total_time = (time.time() - start_time) * 1000
    
    # Aggregate metrics
    total_client = sum(t["total_client_sent_tokens"] for t in all_tasks)
    total_snippet = sum(t["total_snippet_tokens"] for t in all_tasks)
    total_output = sum(t["total_output_tokens"] for t in all_tasks)
    total_latency = sum(t["total_latency_ms"] for t in all_tasks)
    total_steps = num_tasks * 3
    unique_snippets = len(tracker.seen_ids)
    reuse_rate = tracker.get_reuse_rate() * 100
    
    # Print summary
    print(f"\n{'='*70}", file=sys.stderr)
    print(f"TREATMENT (25-Task Retrieval-Native) Summary", file=sys.stderr)
    print(f"{'='*70}", file=sys.stderr)
    print(f"  Tasks Completed:           {num_tasks}", file=sys.stderr)
    print(f"  Steps Completed:           {total_steps}", file=sys.stderr)
    print(f"  Unique Snippets:           {unique_snippets}", file=sys.stderr)
    print(f"  Snippet Reuse Rate:        {reuse_rate:.1f}%", file=sys.stderr)
    print(f"  Total Client Sent Tokens:  {total_client:,}", file=sys.stderr)
    print(f"  Total Snippet Tokens:      {total_snippet:,}", file=sys.stderr)
    print(f"  Total Output Tokens:       {total_output:,}", file=sys.stderr)
    print(f"  End-to-End Latency:        {total_latency:.1f} ms", file=sys.stderr)
    print(f"{'='*70}\n", file=sys.stderr)
    
    return {
        "mode": "treatment",
        "num_tasks": num_tasks,
        "total_steps": total_steps,
        "unique_snippets": unique_snippets,
        "snippet_reuse_rate": reuse_rate,
        "total_client_sent_tokens": total_client,
        "total_snippet_tokens_sent": total_snippet,
        "total_output_tokens": total_output,
        "total_latency_ms": total_latency,
        "benchmark_total_ms": total_time,
        "tasks": all_tasks,
    }


if __name__ == "__main__":
    num_tasks = int(os.environ.get("NUM_TASKS", "25"))
    result = execute_treatment(num_tasks)
    print(json.dumps(result, indent=2))
