#!/usr/bin/env python3
"""SWE-Style Evaluation Runner - pytest-based behavioral tests."""
import argparse
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import yaml


def load_suite(suite_path: str) -> Dict[str, Any]:
    """Load task suite from YAML file."""
    with open(suite_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_pytest_for_task(task_id: str, test_nodeids: List[str], base_dir: Path) -> Dict[str, Any]:
    """Run pytest for specific test nodeids and return results."""
    if not test_nodeids:
        return {"pass": False, "failed_tests": [], "evidence": "No tests specified"}
    
    # Build pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        "-v", "--tb=short", "-q",
        "--no-header",
    ] + test_nodeids
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(base_dir),
        )
        
        # Parse output for failed tests
        output = result.stdout + result.stderr
        lines = output.strip().split('\n')
        
        failed_tests = []
        passed_tests = []
        for line in lines:
            if ' PASSED' in line:
                passed_tests.append(line.split(' ')[0])
            elif ' FAILED' in line:
                failed_tests.append(line.split(' ')[0])
        
        task_passed = result.returncode == 0
        
        # Truncate evidence to avoid huge output
        evidence = output[-1000:] if len(output) > 1000 else output
        
        return {
            "pass": task_passed,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "evidence": evidence.strip(),
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"pass": False, "failed_tests": test_nodeids, "evidence": "Timeout after 60s"}
    except Exception as e:
        return {"pass": False, "failed_tests": test_nodeids, "evidence": f"Error: {e}"}


def collect_test_nodeids(tests_dir: Path) -> Dict[str, List[str]]:
    """Collect all test nodeids by task ID."""
    task_tests = {}
    
    for test_file in tests_dir.glob("test_T*.py"):
        # Extract task ID(s) from filename
        # e.g., test_T01_routing.py -> T01
        # e.g., test_T13_T16_reliability.py -> T13, T14, T15, T16
        name = test_file.stem
        parts = name.replace("test_", "").split("_")
        
        # Find all T## patterns
        task_ids = []
        i = 0
        while i < len(parts):
            if parts[i].startswith("T") and len(parts[i]) >= 2:
                if parts[i][1:].isdigit():
                    task_ids.append(parts[i])
                elif "_" in parts[i]:
                    # Handle T13_T16 format
                    pass
            i += 1
        
        # Handle range format like T13_T16
        if len(task_ids) == 2 and task_ids[0].startswith("T") and task_ids[1].startswith("T"):
            start = int(task_ids[0][1:])
            end = int(task_ids[1][1:])
            task_ids = [f"T{i:02d}" for i in range(start, end + 1)]
        elif len(task_ids) == 1:
            pass
        elif not task_ids:
            # Fallback: use first T## found
            for p in parts:
                if p.startswith("T") and len(p) >= 2 and p[1:3].isdigit():
                    task_ids = [p[:3]]
                    break
        
        # Assign file to each task ID
        test_nodeid = str(test_file.relative_to(tests_dir.parent.parent))
        for tid in task_ids:
            if tid not in task_tests:
                task_tests[tid] = []
            task_tests[tid].append(test_nodeid)
    
    return task_tests


def run_suite(suite_path: str, base_path: Optional[str] = None, verbose: bool = False) -> Dict[str, Any]:
    """Run the full test suite and return results."""
    suite = load_suite(suite_path)
    suite_dir = Path(suite_path).parent.parent
    base_dir = Path(base_path) if base_path else suite_dir
    tests_dir = suite_dir / "swe_style_eval" / "tests"
    
    # Collect test nodeids by task
    task_tests = collect_test_nodeids(tests_dir)
    
    tasks = suite.get("tasks", [])
    results = {}
    passed_tasks = []
    failed_tasks = []
    
    if verbose:
        print(f"Running {len(tasks)} tasks from {suite_path}", file=sys.stderr)
        print(f"Tests directory: {tests_dir}", file=sys.stderr)
    
    for task in tasks:
        task_id = task.get("task_id", "UNKNOWN")
        
        # Get test nodeids from suite or auto-discover
        scoring = task.get("scoring", {})
        if scoring.get("mode") == "pytest" and "test_nodeids" in scoring:
            test_nodeids = scoring["test_nodeids"]
        else:
            # Auto-discover from collected tests
            test_nodeids = task_tests.get(task_id, [])
        
        if verbose:
            print(f"  [{task_id}] Running {len(test_nodeids)} test file(s)...", file=sys.stderr, end=" ")
        
        result = run_pytest_for_task(task_id, test_nodeids, base_dir)
        results[task_id] = result
        
        if result["pass"]:
            passed_tasks.append(task_id)
            if verbose:
                print("PASS", file=sys.stderr)
        else:
            failed_tasks.append(task_id)
            if verbose:
                print(f"FAIL ({len(result.get('failed_tests', []))} failed)", file=sys.stderr)
    
    total = len(tasks)
    pass_rate = len(passed_tasks) / total if total > 0 else 0.0
    
    if verbose:
        print(f"\nResults: {len(passed_tasks)}/{total} passed ({pass_rate*100:.1f}%)", file=sys.stderr)
    
    return {
        "suite": suite_path,
        "timestamp": datetime.now().isoformat(),
        "total_tasks": total,
        "passed_tasks": passed_tasks,
        "failed_tasks": failed_tasks,
        "pass_rate": pass_rate,
        "per_task": results,
    }


def main():
    parser = argparse.ArgumentParser(description="SWE-Style pytest evaluation runner")
    parser.add_argument("--suite", required=True, help="Path to YAML suite file")
    parser.add_argument("--out", default="swe_results.json", help="Output JSON file")
    parser.add_argument("--base-path", default=None, help="Base path for test execution")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    results = run_suite(args.suite, args.base_path, args.verbose)
    
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results: {args.out}")
    print(f"  Passed: {len(results['passed_tasks'])}/{results['total_tasks']}")
    print(f"  Failed: {len(results['failed_tasks'])}/{results['total_tasks']}")
    
    # Exit with 0 if all pass, 1 if any fail
    sys.exit(0 if len(results["failed_tasks"]) == 0 else 1)


if __name__ == "__main__":
    main()
