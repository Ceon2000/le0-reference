#!/usr/bin/env python3
"""
Comparison runner - runs both baseline and treatment with comprehensive metrics.

Includes prefill/decode latency breakdown and BENCH_PROFILE support.

Usage: NUM_TASKS=5 python3 compare_runner.py
       BENCH_PROFILE=prefill_dominant NUM_TASKS=3 python3 compare_runner.py
"""

import json
import os
import sys
import time
from datetime import datetime

from agent_driver import load_tasks, execute_lookups, build_step_prompt_baseline, build_step_prompt_treatment, count_tokens, SnippetTracker, STEP_NAMES
from target_vllm import run_prompt, _ensure_model_loaded, BENCH_PROFILE


def run_baseline(num_tasks, tasks):
    """Run baseline mode, collecting detailed metrics including prefill/decode breakdown."""
    totals = {
        "client_tokens": 0, "output_tokens": 0, "latency_ms": 0, "energy_j": 0,
        "prefill_ms": 0, "decode_ms": 0, "prefill_tokens_computed": 0, "reused_tokens": 0,
    }
    all_tasks = []
    
    for i in range(1, num_tasks + 1):
        lookups = execute_lookups(i)
        snippet_tokens = sum(l["token_estimate"] for l in lookups)
        task = {"client": 0, "output": 0, "latency": 0, "prefill_ms": 0, "decode_ms": 0}
        prior = []
        
        for step in STEP_NAMES:
            prompt = build_step_prompt_baseline(i, tasks[i-1], step, lookups, prior)
            task["client"] += count_tokens(prompt)
            out, metrics = run_prompt(prompt=prompt, step_name=step, flow_idx=i, temperature=0.7)
            prior.append(out.decode('utf-8', errors='replace'))
            task["output"] += metrics.get("output_tokens", 0)
            task["latency"] += metrics.get("latency_ms", 0)
            task["prefill_ms"] += metrics.get("prefill_ms", 0)
            task["decode_ms"] += metrics.get("decode_ms", 0)
            totals["prefill_tokens_computed"] += metrics.get("prefill_tokens_computed", 0)
            totals["reused_tokens"] += metrics.get("reused_tokens", 0)
            totals["energy_j"] += metrics.get("energy_j", 0)
        
        totals["client_tokens"] += task["client"]
        totals["output_tokens"] += task["output"]
        totals["latency_ms"] += task["latency"]
        totals["prefill_ms"] += task["prefill_ms"]
        totals["decode_ms"] += task["decode_ms"]
        all_tasks.append({"task": i, "client_tokens": task["client"], "output_tokens": task["output"], 
                         "latency_ms": task["latency"], "prefill_ms": task["prefill_ms"], "decode_ms": task["decode_ms"]})
        print(f"  [BASELINE] Task {i}: {task['client']:,} in, {task['output']} out, {task['latency']:.0f}ms (prefill={task['prefill_ms']:.0f}ms)", file=sys.stderr)
    
    # Snippet tokens (baseline sends full each time)
    totals["snippet_tokens"] = sum(sum(l["token_estimate"] for l in execute_lookups(i)) for i in range(1, num_tasks + 1)) * 3
    
    return {
        "total_client_tokens": totals["client_tokens"],
        "total_snippet_tokens": totals["snippet_tokens"],
        "total_output_tokens": totals["output_tokens"],
        "total_latency_ms": totals["latency_ms"],
        "total_prefill_ms": totals["prefill_ms"],
        "total_decode_ms": totals["decode_ms"],
        "total_prefill_tokens_computed": totals["prefill_tokens_computed"],
        "total_reused_tokens": totals["reused_tokens"],
        "total_energy_j": totals["energy_j"],
        "avg_client_tokens": totals["client_tokens"] / num_tasks,
        "avg_output_tokens": totals["output_tokens"] / num_tasks,
        "avg_latency_ms": totals["latency_ms"] / num_tasks,
        "prefill_pct": (totals["prefill_ms"] / totals["latency_ms"] * 100) if totals["latency_ms"] > 0 else 0,
        "tasks": all_tasks
    }


def run_treatment(num_tasks, tasks):
    """Run treatment mode with snippet deduplication, collecting detailed metrics."""
    tracker = SnippetTracker()
    totals = {
        "client_tokens": 0, "output_tokens": 0, "latency_ms": 0, "energy_j": 0,
        "prefill_ms": 0, "decode_ms": 0, "prefill_tokens_computed": 0, "reused_tokens": 0,
    }
    total_avoided = 0
    all_tasks = []
    
    for i in range(1, num_tasks + 1):
        lookups = execute_lookups(i)
        new_count = sum(1 for l in lookups if not tracker.has_seen(l["snippet_id"]))
        reused_tokens = sum(l["token_estimate"] for l in lookups if tracker.has_seen(l["snippet_id"]))
        task = {"client": 0, "output": 0, "latency": 0, "prefill_ms": 0, "decode_ms": 0}
        prior = []
        
        for step in STEP_NAMES:
            prompt = build_step_prompt_treatment(i, tasks[i-1], step, lookups, prior, tracker)
            task["client"] += count_tokens(prompt)
            out, metrics = run_prompt(prompt=prompt, step_name=step, flow_idx=i, temperature=0.7)
            prior.append(out.decode('utf-8', errors='replace'))
            task["output"] += metrics.get("output_tokens", 0)
            task["latency"] += metrics.get("latency_ms", 0)
            task["prefill_ms"] += metrics.get("prefill_ms", 0)
            task["decode_ms"] += metrics.get("decode_ms", 0)
            totals["prefill_tokens_computed"] += metrics.get("prefill_tokens_computed", 0)
            totals["reused_tokens"] += metrics.get("reused_tokens", 0)
            totals["energy_j"] += metrics.get("energy_j", 0)
        
        totals["client_tokens"] += task["client"]
        totals["output_tokens"] += task["output"]
        totals["latency_ms"] += task["latency"]
        totals["prefill_ms"] += task["prefill_ms"]
        totals["decode_ms"] += task["decode_ms"]
        total_avoided += reused_tokens * 3
        all_tasks.append({"task": i, "client_tokens": task["client"], "output_tokens": task["output"], 
                         "new_snippets": new_count, "prefill_ms": task["prefill_ms"], "decode_ms": task["decode_ms"]})
        print(f"  [TREATMENT] Task {i}: {task['client']:,} in, {task['output']} out, new={new_count}, seen={len(tracker.seen_ids)}", file=sys.stderr)
    
    return {
        "total_client_tokens": totals["client_tokens"],
        "total_output_tokens": totals["output_tokens"],
        "total_latency_ms": totals["latency_ms"],
        "total_prefill_ms": totals["prefill_ms"],
        "total_decode_ms": totals["decode_ms"],
        "total_prefill_tokens_computed": totals["prefill_tokens_computed"],
        "total_reused_tokens": totals["reused_tokens"],
        "total_energy_j": totals["energy_j"],
        "total_avoided_tokens": total_avoided,
        "avg_client_tokens": totals["client_tokens"] / num_tasks,
        "avg_output_tokens": totals["output_tokens"] / num_tasks,
        "avg_latency_ms": totals["latency_ms"] / num_tasks,
        "prefill_pct": (totals["prefill_ms"] / totals["latency_ms"] * 100) if totals["latency_ms"] > 0 else 0,
        "unique_snippets": len(tracker.seen_ids),
        "reuse_rate": tracker.get_reuse_rate() * 100,
        "tasks": all_tasks
    }


def delta_indicator(old, new, lower_is_better=True):
    """Return delta string with indicator."""
    diff = new - old
    pct = (diff / old * 100) if old != 0 else 0
    sign = "+" if diff > 0 else ""
    good = (diff < 0) if lower_is_better else (diff > 0)
    indicator = "🟢" if good else "🔴" if not good and abs(pct) > 1 else "⚪"
    return f"{sign}{diff:,.1f} ({sign}{pct:.1f}%) {indicator}"


def print_comparison(baseline, treatment, num_tasks, elapsed):
    """Print comprehensive comparison report with prefill/decode breakdown."""
    W = 90
    
    # Energy calculations
    b_energy = baseline.get("total_energy_j", baseline["total_latency_ms"] * 0.28)
    t_energy = treatment.get("total_energy_j", treatment["total_latency_ms"] * 0.28)
    b_jpt = (b_energy / 1000) / num_tasks if num_tasks > 0 else 0
    t_jpt = (t_energy / 1000) / num_tasks if num_tasks > 0 else 0
    
    print(f"\n📊 RETRIEVAL-NATIVE COMPARISON (profile={BENCH_PROFILE})", file=sys.stderr)
    print("=" * W, file=sys.stderr)
    print(f"  Benchmark: 25-Task Retrieval-Native | Tasks: {num_tasks} | Steps: {num_tasks * 3}", file=sys.stderr)
    print("=" * W, file=sys.stderr)
    print("  Tier Definitions:", file=sys.stderr)
    print("    vLLM (Baseline) = Stateless client, resends full snippet_text every lookup", file=sys.stderr)
    print("    vLLM+LE-0 (Treatment) = Session-native, sends snippet_text once then snippet_id", file=sys.stderr)
    print("=" * W, file=sys.stderr)
    
    print(f"{'Metric':<45} {'vLLM':>20} {'vLLM+LE-0':>20}", file=sys.stderr)
    print("-" * W, file=sys.stderr)
    print(f"{'Tasks':<45} {num_tasks:>20} {num_tasks:>20}", file=sys.stderr)
    print(f"{'Total Steps':<45} {num_tasks * 3:>20} {num_tasks * 3:>20}", file=sys.stderr)
    print(f"{'Unique Snippets':<45} {'N/A':>20} {treatment['unique_snippets']:>20}", file=sys.stderr)
    print(f"{'Snippet Reuse Rate':<45} {'0.0%':>20} {treatment['reuse_rate']:>19.1f}%", file=sys.stderr)
    print("-" * W, file=sys.stderr)
    print(f"{'Total Client Sent Tokens':<45} {baseline['total_client_tokens']:>20,} {treatment['total_client_tokens']:>20,}", file=sys.stderr)
    print(f"{'Avoided Snippet Tokens':<45} {'0':>20} {treatment.get('total_avoided_tokens', 0):>20,}", file=sys.stderr)
    
    # Prefill/Decode breakdown
    print("-" * W, file=sys.stderr)
    print(f"{'⏱️ LATENCY BREAKDOWN':<45}", file=sys.stderr)
    print(f"{'Total Latency (ms)':<45} {baseline['total_latency_ms']:>20,.0f} {treatment['total_latency_ms']:>20,.0f}", file=sys.stderr)
    print(f"{'  Prefill Time (ms)':<45} {baseline['total_prefill_ms']:>20,.0f} {treatment['total_prefill_ms']:>20,.0f}", file=sys.stderr)
    print(f"{'  Decode Time (ms)':<45} {baseline['total_decode_ms']:>20,.0f} {treatment['total_decode_ms']:>20,.0f}", file=sys.stderr)
    print(f"{'  Prefill % of Total':<45} {baseline['prefill_pct']:>19.1f}% {treatment['prefill_pct']:>19.1f}%", file=sys.stderr)
    
    # Prefill tokens
    print("-" * W, file=sys.stderr)
    print(f"{'🔢 PREFILL TOKENS':<45}", file=sys.stderr)
    print(f"{'Prompt Tokens (input)':<45} {baseline['total_client_tokens']:>20,} {treatment['total_client_tokens']:>20,}", file=sys.stderr)
    b_prefill_computed = baseline.get('total_prefill_tokens_computed', baseline['total_client_tokens'])
    t_prefill_computed = treatment.get('total_prefill_tokens_computed', treatment['total_client_tokens'])
    print(f"{'Prefill Tokens Computed':<45} {b_prefill_computed:>20,} {t_prefill_computed:>20,}", file=sys.stderr)
    b_reused = baseline.get('total_reused_tokens', 0)
    t_reused = treatment.get('total_reused_tokens', 0)
    print(f"{'Reused Tokens (cache hit)':<45} {b_reused:>20,} {t_reused:>20,}", file=sys.stderr)
    
    # Energy
    print("-" * W, file=sys.stderr)
    print(f"{'Energy (kJ)':<45} {b_energy/1000:>20.3f} {t_energy/1000:>20.3f}", file=sys.stderr)
    print(f"{'Joules/Task':<45} {b_jpt:>20.3f} {t_jpt:>20.3f}", file=sys.stderr)
    print("=" * W, file=sys.stderr)
    
    # Delta section
    print(f"\n📈 LE-0 vs vLLM DELTA (Efficiency Focus)", file=sys.stderr)
    print("-" * W, file=sys.stderr)
    
    tk_delta = delta_indicator(baseline["total_client_tokens"], treatment["total_client_tokens"], lower_is_better=True)
    print(f"{'Token Reduction':<45} {tk_delta:>45}", file=sys.stderr)
    
    lat_delta = delta_indicator(baseline["total_latency_ms"], treatment["total_latency_ms"], lower_is_better=True)
    print(f"{'Latency Change':<45} {lat_delta:>42} ms", file=sys.stderr)
    
    prefill_delta = delta_indicator(baseline["total_prefill_ms"], treatment["total_prefill_ms"], lower_is_better=True)
    print(f"{'Prefill Time Change':<45} {prefill_delta:>42} ms", file=sys.stderr)
    
    decode_delta = delta_indicator(baseline["total_decode_ms"], treatment["total_decode_ms"], lower_is_better=True)
    print(f"{'Decode Time Change':<45} {decode_delta:>42} ms", file=sys.stderr)
    
    print("-" * W, file=sys.stderr)
    
    energy_delta = delta_indicator(b_energy/1000, t_energy/1000, lower_is_better=True)
    print(f"{'🔋 Energy Change':<45} {energy_delta:>42} kJ", file=sys.stderr)
    
    print("-" * W, file=sys.stderr)
    print(f"{'Snippet Reuse Rate':<45} {treatment['reuse_rate']:>44.1f}%", file=sys.stderr)
    print("=" * W, file=sys.stderr)
    
    # Diagnostic interpretation
    print(f"\n🔍 COMPUTE BOUNDARY DIAGNOSTIC", file=sys.stderr)
    print("-" * W, file=sys.stderr)
    prefill_reduction_pct = ((baseline["total_prefill_ms"] - treatment["total_prefill_ms"]) / baseline["total_prefill_ms"] * 100) if baseline["total_prefill_ms"] > 0 else 0
    token_reduction_pct = ((baseline["total_client_tokens"] - treatment["total_client_tokens"]) / baseline["total_client_tokens"] * 100) if baseline["total_client_tokens"] > 0 else 0
    
    if abs(prefill_reduction_pct) < 5 and token_reduction_pct > 20:
        print("  ⚠️  Token reduction WITHOUT prefill reduction suggests transmission-only savings", file=sys.stderr)
        print("      LE-0 may not be providing compute-bound reuse (prefill avoidance)", file=sys.stderr)
    elif prefill_reduction_pct > 10:
        print("  ✅ Prefill reduction detected - suggests compute-bound reuse is working", file=sys.stderr)
    else:
        print("  ℹ️  Results inconclusive - try prefill_dominant profile for clearer signal", file=sys.stderr)
    print("=" * W, file=sys.stderr)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n📄 Full run summary saved: comparison_summary_{timestamp}.json", file=sys.stderr)
    
    token_reduction = baseline["total_client_tokens"] - treatment["total_client_tokens"]
    token_reduction_pct = (token_reduction / baseline["total_client_tokens"] * 100) if baseline["total_client_tokens"] > 0 else 0
    
    return {
        "timestamp": timestamp,
        "profile": BENCH_PROFILE,
        "num_tasks": num_tasks,
        "baseline": baseline,
        "treatment": treatment,
        "deltas": {
            "token_reduction": token_reduction,
            "token_reduction_pct": token_reduction_pct,
            "prefill_reduction_ms": baseline["total_prefill_ms"] - treatment["total_prefill_ms"],
            "prefill_reduction_pct": prefill_reduction_pct,
            "decode_reduction_ms": baseline["total_decode_ms"] - treatment["total_decode_ms"],
            "energy_savings_kj": (b_energy - t_energy) / 1000,
            "energy_savings_pct": ((b_energy - t_energy) / b_energy * 100) if b_energy > 0 else 0
        }
    }


def main():
    num_tasks = min(int(os.environ.get("NUM_TASKS", "5")), 25)
    _ensure_model_loaded()
    tasks = load_tasks()
    
    print(f"\n[COMPARE] Starting {num_tasks}-task comparison benchmark (profile={BENCH_PROFILE})", file=sys.stderr)
    start = time.time()
    
    baseline = run_baseline(num_tasks, tasks)
    treatment = run_treatment(num_tasks, tasks)
    
    elapsed = time.time() - start
    result = print_comparison(baseline, treatment, num_tasks, elapsed)
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
