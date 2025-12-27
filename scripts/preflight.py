#!/usr/bin/env python3
"""
Preflight verifier for LE-0 reference implementation.
Runs fast checks before execution to fail fast with clear messages.
"""

import os
import sys
import importlib
from pathlib import Path


def check_python_version():
    """Check Python version is >= 3.9."""
    if sys.version_info < (3, 9):
        print(f"[PREFLIGHT] ERROR: Python 3.9+ required, found {sys.version_info.major}.{sys.version_info.minor}", file=sys.stderr)
        return False
    return True


def check_imports():
    """Check required imports succeed."""
    required_imports = [
        ("vllm", "vLLM"),
        ("torch", "PyTorch"),
        ("transformers", "Transformers"),
        ("tokenizers", "Tokenizers"),
    ]
    
    failed = []
    for module_name, display_name in required_imports:
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            failed.append((display_name, str(e)))
    
    if failed:
        for display_name, error in failed:
            print(f"[PREFLIGHT] ERROR: {display_name} import failed: {error}", file=sys.stderr)
        return False
    
    return True


def check_le0_wheel():
    """Check LE0_WHEEL is set and file exists."""
    le0_wheel = os.environ.get("LE0_WHEEL")
    if not le0_wheel:
        print("[PREFLIGHT] ERROR: LE0_WHEEL environment variable is required for MODE=le0 or MODE=both", file=sys.stderr)
        return False
    
    wheel_path = Path(le0_wheel)
    if not wheel_path.exists():
        print(f"[PREFLIGHT] ERROR: LE0_WHEEL file not found: {le0_wheel}", file=sys.stderr)
        return False
    
    return True


def check_le0_runtime():
    """Check le0_runtime can be imported and has version."""
    try:
        import le0_runtime
        version = getattr(le0_runtime, "__version__", "unknown")
        return True, version
    except ImportError as e:
        print(f"[PREFLIGHT] ERROR: le0_runtime import failed: {e}", file=sys.stderr)
        print("[PREFLIGHT] HINT: Ensure LE-0 wheel is installed in venv", file=sys.stderr)
        return False, None


def check_le0_target():
    """Check LE0_TARGET resolves as importable module:function."""
    le0_target = os.environ.get("LE0_TARGET")
    if not le0_target:
        print("[PREFLIGHT] ERROR: LE0_TARGET environment variable is required", file=sys.stderr)
        return False, None
    
    # Split module:function
    if ":" not in le0_target:
        print(f"[PREFLIGHT] ERROR: LE0_TARGET must be in format 'module:function', got: {le0_target}", file=sys.stderr)
        return False, None
    
    module_name, function_name = le0_target.split(":", 1)
    
    # Ensure repo root is in PYTHONPATH for importing target_vllm
    repo_root = Path.cwd()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    
    # Try to import the module
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        print(f"[PREFLIGHT] ERROR: Cannot import module '{module_name}': {e}", file=sys.stderr)
        print(f"[PREFLIGHT] HINT: Ensure PYTHONPATH includes repo root (current: {repo_root})", file=sys.stderr)
        return False, None
    
    # Check function exists and is callable
    if not hasattr(module, function_name):
        print(f"[PREFLIGHT] ERROR: Module '{module_name}' has no attribute '{function_name}'", file=sys.stderr)
        return False, None
    
    func = getattr(module, function_name)
    if not callable(func):
        print(f"[PREFLIGHT] ERROR: '{module_name}.{function_name}' is not callable", file=sys.stderr)
        return False, None
    
    return True, le0_target


def main():
    """Run preflight checks."""
    mode = os.environ.get("MODE", "le0")
    
    # Always check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Always check imports
    if not check_imports():
        sys.exit(1)
    
    # Collect success messages
    success_parts = ["vllm", "torch", "transformers", "tokenizers"]
    
    # For le0 or both mode, check LE-0 specific requirements
    if mode in ("le0", "both"):
        # Check LE0_WHEEL
        if not check_le0_wheel():
            sys.exit(1)
        
        # Check le0_runtime import
        le0_ok, le0_version = check_le0_runtime()
        if not le0_ok:
            sys.exit(1)
        success_parts.append(f"le0={le0_version}")
        
        # Check LE0_TARGET
        target_ok, target_str = check_le0_target()
        if not target_ok:
            sys.exit(1)
        success_parts.append(f"target={target_str}")
    
    # Print success summary
    print(f"[PREFLIGHT] ok: {' '.join(success_parts)}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()

