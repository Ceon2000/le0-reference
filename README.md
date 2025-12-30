# LE-0 Reference Implementation

## Retrieval-Native Benchmark (25 Tasks × 3 Steps)

This benchmark demonstrates LE-0's **retrieval-native execution model** where snippet deduplication reduces token payload over time.

### Why 25 Tasks?

- Aligns with LE-0's maximum workflow length
- Enables compounding reuse as snippets repeat across tasks
- Shows clear separation between early tasks (building cache) and later tasks (high reuse)

---

## Architecture

| Mode | Snippet Handling | Token Payload |
|------|------------------|---------------|
| **Baseline** | Resend full `snippet_text` every time | Constant |
| **Treatment** | Send `snippet_text` once, then `snippet_id` | Decreases |

### Retrieval-Native Agent

Each task runs 3 steps:
1. **Planner**: Decides what to analyze
2. **Executor**: Performs lookups, reasons over code
3. **Verifier**: Validates findings

```
repo_lookup(query) -> {snippet_id, snippet_text, source_path}
```

---

## Quick Start

### Run Baseline (5 Tasks)
```bash
NUM_TASKS=5 python3 standalone_runner.py
```

### Run Treatment (5 Tasks)
```bash
NUM_TASKS=5 python3 le0_runner.py
```

### Full 25-Task Comparison
```bash
NUM_TASKS=25 python3 standalone_runner.py > baseline.json 2>&1
NUM_TASKS=25 python3 le0_runner.py > treatment.json 2>&1
```

---

## Expected Results

| Metric | Baseline | Treatment |
|--------|----------|-----------|
| Client Sent Tokens | ~150K (constant) | ~50K (decreasing) |
| Snippet Tokens | ~100K | ~30K |
| Reuse Rate | 0% | ~60% |

---

## Metrics

- **`client_sent_tokens`**: Tokens actually sent
- **`snippet_tokens_sent`**: Tokens from snippet payloads
- **`unique_snippets`**: Distinct snippets retrieved
- **`snippet_reuse_rate`**: % lookups hitting cache

---

## SWE-bench-shaped Scoring

This repository includes a **SWE-bench Verified-style evaluation suite** for code quality assessment.

### What is SWE-bench Verified?

[SWE-bench Verified](https://www.swebench.com/) evaluates code repair agents using:
1. **Issue description** (prompt) describing what needs to be fixed
2. **Apply patch** to the target codebase
3. **Run tests** (pytest) to verify the fix
4. **Pass/fail** outcome per issue

### How Our Suite Mirrors It

| SWE-bench Verified | Our Suite |
|-------------------|-----------|
| Real GitHub issues | 25 synthetic audit tasks (T01-T25) |
| Real repos | `fixtures/helpdesk_ai/` synthetic codebase |
| Real test suites | `swe_style_eval/tests/` pytest suite |
| Docker isolation | Local pytest execution |

**Methodology**: `apply patch → run tests → pass/fail`

### Prompts vs Tests

- **Prompts** (`prompt_swe`): Describe the issue and expected fix
- **Tests**: Are the ground truth for pass/fail scoring
- **Expected outcomes**: Document the behavioral invariants

### Commands

```bash
# Run the full 25-task suite
python -m swe_style_eval.runner --suite tasks/swebench_shaped_suite_25.yaml -v

# Output: swe_results.json with per-task pass/fail and evidence
```

### Interpreting Results

| Metric | Meaning |
|--------|---------|
| **Fixture compliance baseline** | How many tasks pass on current (unfixed) code |
| **Agent repair accuracy** | How many failing tasks become passing after patches |
| **pass_rate** | `passed_tasks / total_tasks` |

### Example Output

```json
{
  "suite_name": "SWE-bench-Shaped Suite v2.0",
  "passed_tasks": ["T01", "T03", ...],
  "failed_tasks": ["T02", "T04", ...],
  "pass_rate": 0.64,
  "per_task": {
    "T02": {
      "pass": false,
      "prompt_swe": "Fix WeightedScorer.score() to prevent ZeroDivisionError...",
      "expected_outcome": ["Normalized score ∈ [0.0, 1.0]", ...],
      "brief_evidence": ["AssertionError: Normalized score 7.5 out of range"]
    }
  }
}
```

---

## IP Safety

- LE-0 is a **black box**
- `snippet_id` is opaque (SHA256-based)
- No KV internals or merge semantics exposed
