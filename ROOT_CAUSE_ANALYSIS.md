# Root Cause Analysis: 30-40 Minute Benchmark Runs

## Executive Summary
The benchmark currently takes 30-40 minutes for 25 workflows due to:
1. **Repeated flow expansion** (no caching) - ~1-2 minutes per run
2. **vLLM engine initialization overhead** - vLLM internally initializes `torch.distributed` even for single-GPU runs, causing Gloo backend initialization
3. **No explicit engine pre-loading** - Engine is lazily loaded on first step, but distributed init happens during LLM() construction
4. **Missing timing instrumentation** - Cannot identify bottlenecks

## Detailed Root Causes

### 1. Flow Expansion Without Caching
**Location**: `run_flow.py:61-124` (`build_multiple_flows()`)
- **Problem**: Every run regenerates all 25 expanded flow files from scratch
- **Impact**: ~1-2 minutes wasted on I/O and fixture loading
- **Evidence**: `run.sh:187` calls `run_flow.py` unconditionally every run

### 2. vLLM Engine Initialization Overhead
**Location**: `target_vllm.py:140` (`LLM(model=...)`)
- **Problem**: vLLM internally calls `torch.distributed.init_process_group()` even for single-GPU runs
- **Impact**: Gloo backend initialization takes ~5-10 seconds per engine creation
- **Evidence**: Logs show `[Gloo] Rank 0 is connected to 0 peer ranks...` messages
- **Note**: Engine is global (`_llm`) and should be reused, but if it's recreated or if vLLM reinitializes distributed backend, we pay the cost

### 3. Lazy Engine Loading
**Location**: `target_vllm.py:123-149` (`_ensure_model_loaded()`)
- **Problem**: Engine is loaded on first `run_prompt()` or `run()` call, not pre-loaded
- **Impact**: First workflow pays initialization cost, but more importantly, if engine is destroyed/recreated, we pay again
- **Evidence**: No explicit pre-loading in `standalone_runner.py` or `run.sh`

### 4. Missing Timing Instrumentation
**Location**: Throughout codebase
- **Problem**: No wall-clock timing for:
  - Flow expansion phase
  - Engine initialization phase
  - Per-workflow execution
  - First token latency
- **Impact**: Cannot identify which phase is slow

## Where Distributed Init Occurs

### vLLM Internal (Not directly in our code)
- vLLM's `LLM.__init__()` internally calls distributed initialization
- This happens even when `world_size=1` (single GPU)
- We cannot prevent this without modifying vLLM, but we can ensure engine is only created once

### Our Code (No direct calls)
- **No direct `torch.distributed.init_process_group()` calls found**
- The Gloo messages come from vLLM's internal initialization

## Where Engine is Created/Destroyed

### Creation
- **File**: `target_vllm.py:140`
- **Function**: `_ensure_model_loaded()`
- **Condition**: `if _llm is None or _model_id != current_model_id`
- **Called from**: 
  - `run_prompt()` (line 181) - standalone mode
  - `run()` (line 260) - LE-0 mode

### Destruction
- **Not explicitly destroyed** - Engine persists in global `_llm` variable
- **Potential issue**: If Python process restarts or if `_model_id` changes, engine is recreated

## Performance Impact Breakdown (Estimated)

For a 30-minute run with 25 workflows:
- **Flow expansion**: ~1-2 minutes (no caching)
- **Engine initialization**: ~5-10 seconds (if happens once) or ~2-5 minutes (if happens per workflow - unlikely but possible if engine is recreated)
- **Actual generation**: ~25-28 minutes (75 steps × ~20-25 seconds per step)
- **Overhead**: ~2-5 minutes wasted on initialization/expansion

## Solution Strategy

1. **Cache expanded flows**: Hash-based cache keyed by fixture hash + template version
2. **Pre-load engine**: Explicitly load engine before workflows start
3. **Add timing instrumentation**: Track all phases
4. **Ensure single engine instance**: Verify engine is not recreated

