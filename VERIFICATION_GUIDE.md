# Verification Guide: Single Engine Instance

## Hard Requirements
1. ✅ **One engine instance** - Engine created once, reused for all workflows
2. ✅ **One process** - All workflows run in same Python process
3. ✅ **No per-workflow re-init** - Engine not recreated between workflows
4. ✅ **No subprocess-per-workflow** - No process isolation

## How to Verify

### 1. Check Engine Init Timing

**Expected**: `[TIMING] engine_init_ms=...` should appear **ONCE** (not 25 times)

```bash
NUM_FLOWS=25 MODE=standalone bash run.sh 2>&1 | grep -c "\[TIMING\] engine_init_ms"
# Should output: 1
```

**If >1**: Engine is being recreated per workflow (BAD)

### 2. Check Gloo/Distributed Init Messages

**Expected**: Gloo messages should appear **ONCE** (during first engine init)

```bash
NUM_FLOWS=25 MODE=standalone bash run.sh 2>&1 | grep -c "Gloo\|Rank 0 is connected"
# Should output: 1-2 (once during init)
```

**If repeated per workflow**: Distributed backend is being reinitialized (BAD)

### 3. Check Workflow Timing

**Expected**: `avg_workflow_ms` should be ~60-90 seconds (dominated by inference, not overhead)

```bash
NUM_FLOWS=25 MODE=standalone bash run.sh 2>&1 | grep "avg_workflow_ms"
# Should show: [TIMING] avg_workflow_ms=60000.00-90000.00
```

**If much higher**: Overhead is dominating (BAD)

**If much lower**: Something is wrong with timing or workflows are being skipped

### 4. Verify No Subprocess Calls

**Expected**: All workflows run in same process

```bash
# Check for subprocess calls in code
grep -r "subprocess\|Popen\|spawn\|fork" --include="*.py" .
# Should only find comments or unrelated code
```

### 5. Check Process Count

**Expected**: Only one Python process running `standalone_runner.py`

```bash
# During execution, check process count
ps aux | grep "standalone_runner.py" | wc -l
# Should output: 1
```

## Current Implementation

### Standalone Mode (`standalone_runner.py`)
- ✅ Pre-loads engine **once** before workflow loop (line 67)
- ✅ All workflows run in same process
- ✅ `run_prompt()` only calls `_ensure_model_loaded()` if engine is None (safety check)
- ✅ Engine stored in global `_llm` variable

### LE-0 Mode (`target_vllm.py`)
- ✅ Engine initialized on first `run()` call
- ✅ Subsequent calls hit fast-path and return immediately
- ✅ Engine stored in global `_llm` variable
- ✅ Timing logged only once (first init)

## Expected Output

### Standalone Mode
```
[TIMING] engine_init_start
[TIMING] engine_init_ms=5678.90
[TIMING] workflow_1_ms=12345.67
[TIMING] workflow_2_ms=12340.12
...
[TIMING] workflow_25_ms=12350.45
[TIMING] benchmark_total_ms=1800000.00
[TIMING] avg_workflow_ms=72000.00
```

**Key**: `engine_init_ms` appears **once**, `workflow_N_ms` appears **25 times**

### LE-0 Mode
```
[TIMING] engine_init_start
[TIMING] engine_init_ms=5678.90
[TARGET] flow=1 step=planner latency_ms=...
[TARGET] flow=1 step=executor latency_ms=...
...
```

**Key**: `engine_init_ms` appears **once** (on first `run()` call)

## Troubleshooting

### If `engine_init_ms` appears multiple times:
1. Check if `_llm` global is being reset somewhere
2. Check if `_model_id` is changing between workflows
3. Check if there are multiple Python processes

### If Gloo messages appear repeatedly:
1. Engine is being recreated (check `_llm` is not None)
2. vLLM is reinitializing distributed backend (shouldn't happen if engine persists)

### If `avg_workflow_ms` is too high:
1. Check if workflows are actually running (check `[TARGET]` lines)
2. Check if there's overhead from flow loading or other operations
3. Verify GPU is being used (check `nvidia-smi`)

## Code Changes Made

1. **`target_vllm.py`**:
   - Added fast-path return in `_ensure_model_loaded()` (line 128-129)
   - Added timing logging for first init only (line 155-159)
   - Made `run_prompt()` and `run()` only call `_ensure_model_loaded()` if engine is None

2. **`standalone_runner.py`**:
   - Pre-loads engine before workflow loop (line 67)
   - All workflows run in same process

3. **No subprocess calls**: Verified - none found in codebase

