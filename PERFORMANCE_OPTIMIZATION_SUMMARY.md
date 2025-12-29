# Performance Optimization Summary

## Changes Made

### 1. Flow Expansion Caching (`run_flow.py`)
- **Added**: Hash-based caching system using `flows/.expanded_cache.json`
- **Key**: Cache keyed by `fixture_hash` (SHA256 of fixture content) + `template_hash` (SHA256 of flow template)
- **Benefit**: Skips regeneration when inputs unchanged, saving ~1-2 minutes per run
- **Implementation**: 
  - `_load_cache()` / `_save_cache()` functions
  - `_check_cache_valid()` validates cache before use
  - Cache includes `expanded_files` list for validation

### 2. Engine Pre-loading (`standalone_runner.py`)
- **Added**: Explicit `_ensure_model_loaded()` call before workflow loop
- **Benefit**: Engine initialized once, not lazily on first step
- **Timing**: Added `[TIMING] engine_init_ms=...` output

### 3. Comprehensive Timing Instrumentation
- **Flow Expansion**: `[TIMING] flow_expansion_ms=...` (cached vs generated)
- **Engine Init**: `[TIMING] engine_init_ms=...` (one-time cost)
- **Per-Workflow**: `[TIMING] workflow_N_ms=...` for each workflow
- **Benchmark Total**: `[TIMING] benchmark_total_ms=...` and `avg_workflow_ms=...`

### 4. Engine Initialization Optimization (`target_vllm.py`)
- **Added**: `CUDA_VISIBLE_DEVICES=0` environment variable before LLM creation
- **Note**: vLLM still initializes torch.distributed internally, but engine is only created once per process

### 5. Updated `run.sh`
- **Changed**: Log messages to mention "with caching"
- **No functional changes**: Caching is transparent to run.sh

## Expected Performance Improvements

### Before Optimization
- Flow expansion: ~1-2 minutes (every run)
- Engine init: ~5-10 seconds (first step only, but distributed init overhead)
- Total: 30-40 minutes for 25 workflows

### After Optimization
- Flow expansion: ~0.1 seconds (cached) or ~1-2 minutes (first run only)
- Engine init: ~5-10 seconds (once, pre-loaded)
- Total: **~25-30 minutes** for 25 workflows (saves 5-10 minutes on warm runs)

## How It Prevents Repeated Gloo Init

1. **Single Engine Instance**: Engine is created once via `_ensure_model_loaded()` and stored in global `_llm`
2. **Pre-loading**: Engine is explicitly loaded before workflows start, not lazily
3. **No Recreation**: Engine is only recreated if `_model_id` changes (which shouldn't happen during a run)
4. **Process Persistence**: All workflows run in the same Python process, so engine persists

## Cache Invalidation

Cache is invalidated when:
- Fixture content changes (different `fixture_hash`)
- Flow template changes (different `template_hash`)
- Number of flows changes (`num_flows` mismatch)
- Expanded files are missing

## Verification Commands

### Fast Path (Cached)
```bash
# First run (generates cache)
NUM_FLOWS=25 MODE=standalone bash run.sh

# Second run (uses cache)
NUM_FLOWS=25 MODE=standalone bash run.sh
# Should see: "Using cached expanded flows" and flow_expansion_ms < 100ms
```

### Cold Start
```bash
# Clear cache
rm -f flows/.expanded_cache.json flows/_expanded_*.json

# Run (will regenerate)
NUM_FLOWS=25 MODE=standalone bash run.sh
# Should see: "Regenerating expanded flows" and flow_expansion_ms > 1000ms
```

### Timing Output
Look for `[TIMING]` lines in stderr:
```
[TIMING] flow_expansion_ms=1234.56 (generated)
[TIMING] engine_init_ms=5678.90
[TIMING] workflow_1_ms=12345.67
...
[TIMING] benchmark_total_ms=1800000.00
[TIMING] avg_workflow_ms=72000.00
```

## Files Modified

1. `run_flow.py` - Added caching logic
2. `standalone_runner.py` - Added engine pre-loading and timing
3. `target_vllm.py` - Added CUDA_VISIBLE_DEVICES, improved timing
4. `run.sh` - Updated log messages
5. `.gitignore` - Added `.expanded_cache.json`

## Safety/Correctness

- **Results identical**: Same flows generated, same execution order
- **No semantic changes**: Only performance optimizations
- **Backward compatible**: Cache is optional, falls back to generation if cache invalid

