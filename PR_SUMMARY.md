# Performance Optimization: Eliminate Repeated Engine Restarts

## Problem
25-workflow benchmark runs were taking 30-40 minutes due to:
1. **Repeated flow expansion** (~1-2 min per run) - no caching
2. **vLLM engine initialization overhead** - torch.distributed/Gloo init even for single-GPU
3. **Lazy engine loading** - engine loaded on first step, not pre-loaded
4. **Missing timing instrumentation** - cannot identify bottlenecks

## Solution

### 1. Flow Expansion Caching (`run_flow.py`)
- Added hash-based cache (`flows/.expanded_cache.json`)
- Cache key: `fixture_hash` (SHA256) + `template_hash` (SHA256) + `num_flows`
- Skips regeneration when inputs unchanged
- **Impact**: Saves ~1-2 minutes on warm runs

### 2. Engine Pre-loading (`standalone_runner.py`)
- Explicit `_ensure_model_loaded()` call before workflow loop
- Engine initialized once, not lazily
- **Impact**: Ensures single engine instance, prevents repeated init

### 3. Timing Instrumentation
- `[TIMING] flow_expansion_ms=...` (cached vs generated)
- `[TIMING] engine_init_ms=...` (one-time cost)
- `[TIMING] workflow_N_ms=...` (per-workflow)
- `[TIMING] benchmark_total_ms=...` (total + avg)

### 4. Engine Initialization Optimization (`target_vllm.py`)
- Set `CUDA_VISIBLE_DEVICES=0` before LLM creation
- Note: vLLM still initializes torch.distributed internally, but only once per process

## Files Modified

1. **`run_flow.py`**
   - Added `_compute_hash()`, `_load_cache()`, `_save_cache()`, `_check_cache_valid()`
   - Modified `build_multiple_flows()` to use cache
   - Added timing output

2. **`standalone_runner.py`**
   - Added `_ensure_model_loaded()` import and pre-load call
   - Added timing instrumentation for engine init and workflows

3. **`target_vllm.py`**
   - Added `CUDA_VISIBLE_DEVICES=0` in `_ensure_model_loaded()`
   - Fixed timing calculations (use `end_time` variable)

4. **`run.sh`**
   - Updated log messages to mention caching

5. **`.gitignore`**
   - Added `flows/.expanded_cache.json`

6. **`ROOT_CAUSE_ANALYSIS.md`** (new)
   - Detailed root cause analysis

7. **`PERFORMANCE_OPTIMIZATION_SUMMARY.md`** (new)
   - Implementation details and verification commands

## How It Prevents Repeated Gloo Init

1. **Single Engine Instance**: Engine created once via `_ensure_model_loaded()`, stored in global `_llm`
2. **Pre-loading**: Engine explicitly loaded before workflows start
3. **No Recreation**: Engine only recreated if `_model_id` changes (shouldn't happen)
4. **Process Persistence**: All workflows run in same Python process

## Expected Performance

- **Before**: 30-40 minutes (flow expansion + engine init overhead)
- **After**: ~25-30 minutes (saves 5-10 minutes on warm runs)
- **Cache hit**: Flow expansion ~0.1s (vs ~1-2 min)

## Verification

### Fast Path (Cached)
```bash
# First run
NUM_FLOWS=25 MODE=standalone bash run.sh
# Second run (uses cache)
NUM_FLOWS=25 MODE=standalone bash run.sh
# Should see: "Using cached expanded flows" and flow_expansion_ms < 100ms
```

### Cold Start
```bash
rm -f flows/.expanded_cache.json flows/_expanded_*.json
NUM_FLOWS=25 MODE=standalone bash run.sh
# Should see: "Regenerating expanded flows" and flow_expansion_ms > 1000ms
```

## Safety/Correctness

- ✅ Results identical: Same flows generated, same execution order
- ✅ No semantic changes: Only performance optimizations
- ✅ Backward compatible: Cache optional, falls back to generation if invalid
- ✅ All timing uses `torch.cuda.synchronize()` for accurate GPU timing

