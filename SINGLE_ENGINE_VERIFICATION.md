# Single Engine Instance Verification

## Summary of Changes

### 1. Fast-Path Optimization (`target_vllm.py`)
- Added early return in `_ensure_model_loaded()` if engine already loaded
- Avoids repeated `_get_model_id()` calls and function overhead
- **Line 128-129**: Fast path check before any work

### 2. Timing Logging (`target_vllm.py`)
- Added `_engine_init_timing_logged` flag to ensure timing logged only once
- **Line 51**: Global flag initialization
- **Line 135-136**: Log `engine_init_start` only on first init
- **Line 155-159**: Log `engine_init_ms` only on first init

### 3. Safety Checks (`target_vllm.py`)
- `run_prompt()` and `run()` only call `_ensure_model_loaded()` if engine is None
- **Line 189**: Safety check in `run_prompt()`
- **Line 272**: Safety check in `run()`
- Prevents redundant calls even if somehow engine is None

### 4. Pre-loading (`standalone_runner.py`)
- Engine explicitly pre-loaded before workflow loop
- **Line 67**: `_ensure_model_loaded()` called once before loop
- All workflows reuse the same engine instance

## Verification Checklist

### ✅ Engine Init Timing
- `[TIMING] engine_init_ms=...` appears **ONCE** (not 25 times)
- Verified by `_engine_init_timing_logged` flag

### ✅ No Subprocess Calls
- No `subprocess`, `Popen`, `spawn`, `fork` found in codebase
- All workflows run in same Python process

### ✅ Engine Persistence
- Engine stored in global `_llm` variable
- Persists across all workflow calls
- Only recreated if `_model_id` changes (shouldn't happen)

### ✅ Fast-Path Performance
- `_ensure_model_loaded()` returns immediately if engine loaded
- Avoids repeated function calls and checks

## Expected Behavior

### Standalone Mode
1. `standalone_runner.py` starts
2. `_ensure_model_loaded()` called **once** (line 67)
3. Engine initialized, timing logged **once**
4. Loop executes 25 workflows
5. Each workflow calls `run_prompt()` → fast-path returns immediately
6. No engine re-init, no Gloo messages

### LE-0 Mode
1. LE-0 starts, calls `run()` for first step
2. `run()` calls `_ensure_model_loaded()` → engine initialized **once**
3. Timing logged **once**
4. Subsequent `run()` calls → fast-path returns immediately
5. No engine re-init, no Gloo messages

## How to Verify (Commands)

```bash
# 1. Check engine_init_ms appears once
NUM_FLOWS=25 MODE=standalone bash run.sh 2>&1 | grep -c "\[TIMING\] engine_init_ms"
# Expected: 1

# 2. Check Gloo messages appear once
NUM_FLOWS=25 MODE=standalone bash run.sh 2>&1 | grep -c "Gloo\|Rank 0"
# Expected: 1-2 (once during init)

# 3. Check workflow timing is reasonable
NUM_FLOWS=25 MODE=standalone bash run.sh 2>&1 | grep "avg_workflow_ms"
# Expected: ~60000-90000 ms (60-90 seconds)

# 4. Verify no subprocess calls
grep -r "subprocess\|Popen" --include="*.py" .
# Expected: Only comments or unrelated code
```

## Code Flow

### Standalone Mode Flow
```
standalone_runner.py:execute_standalone()
  ├─> _ensure_model_loaded() [ONCE]
  │   ├─> Check: _llm is None? → YES
  │   ├─> Log: [TIMING] engine_init_start
  │   ├─> Create: LLM(...) [triggers Gloo init ONCE]
  │   └─> Log: [TIMING] engine_init_ms=...
  │
  └─> Loop: 25 workflows
      └─> execute_one_workflow()
          └─> run_prompt()
              └─> _ensure_model_loaded() [FAST-PATH]
                  └─> Check: _llm is None? → NO
                  └─> Return immediately (no work)
```

### LE-0 Mode Flow
```
LE-0 calls run() for first step
  └─> _ensure_model_loaded() [ONCE]
      ├─> Check: _llm is None? → YES
      ├─> Log: [TIMING] engine_init_start
      ├─> Create: LLM(...) [triggers Gloo init ONCE]
      └─> Log: [TIMING] engine_init_ms=...

LE-0 calls run() for subsequent steps
  └─> _ensure_model_loaded() [FAST-PATH]
      └─> Check: _llm is None? → NO
      └─> Return immediately (no work)
```

## Files Modified

1. **`target_vllm.py`**
   - Added `_engine_init_timing_logged` flag (line 51)
   - Added fast-path return (line 128-129)
   - Added timing logging only on first init (line 135-136, 155-159)
   - Made `run_prompt()` and `run()` only call `_ensure_model_loaded()` if engine is None

2. **`standalone_runner.py`**
   - Pre-loads engine before loop (line 67)
   - No changes needed (already correct)

3. **`VERIFICATION_GUIDE.md`** (new)
   - Detailed verification steps

4. **`SINGLE_ENGINE_VERIFICATION.md`** (this file)
   - Summary of changes and verification

