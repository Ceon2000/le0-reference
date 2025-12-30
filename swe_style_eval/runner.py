#!/usr/bin/env python3
"""SWE-bench-Shaped Evaluation Runner - pytest-based behavioral tests.

This runner follows SWE-bench Verified methodology:
- Load task specifications with expected outcomes
- Run pytest for each task's test nodeids
- Output pass/fail with evidence
- JSON output is SWE-bench compatible
"""
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


def run_pytest_for_nodeids(nodeids: List[str], base_dir: Path) -> Dict[str, Any]:
    """Run pytest for specific test nodeids and return results."""
    if not nodeids:
        return {
            "pass": False,
            "passed_tests": [],
            "failed_tests": [],
            "evidence": "No tests specified",
            "return_code": -1,
        }
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-v", "--tb=line", "-q",
        "--no-header",
    ] + nodeids
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(base_dir),
        )
        
        output = result.stdout + result.stderr
        lines = output.strip().split('\n')
        
        failed_tests = []
        passed_tests = []
        for line in lines:
            if '::' in line:
                if ' PASSED' in line:
                    passed_tests.append(line.split(' ')[0])
                elif ' FAILED' in line:
                    failed_tests.append(line.split(' ')[0])
        
        # Extract brief evidence from failure messages
        brief_evidence = []
        for line in lines:
            if 'AssertionError' in line or 'assert' in line.lower():
                # Clean up assertion line for brief evidence
                clean = line.strip()
                if len(clean) > 100:
                    clean = clean[:97] + "..."
                if clean and clean not in brief_evidence:
                    brief_evidence.append(clean)
                    if len(brief_evidence) >= 2:
                        break
        
        return {
            "pass": result.returncode == 0,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "evidence": output[-800:] if len(output) > 800 else output,
            "brief_evidence": brief_evidence[:2],
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "pass": False,
            "passed_tests": [],
            "failed_tests": nodeids,
            "evidence": "Timeout after 60s",
            "brief_evidence": ["Test execution timed out"],
            "return_code": -1,
        }
    except Exception as e:
        return {
            "pass": False,
            "passed_tests": [],
            "failed_tests": nodeids,
            "evidence": f"Error: {e}",
            "brief_evidence": [str(e)],
            "return_code": -1,
        }


def run_suite(suite_path: str, base_path: Optional[str] = None, verbose: bool = False) -> Dict[str, Any]:
    """Run the full test suite and return SWE-bench-shaped results."""
    suite = load_suite(suite_path)
    suite_dir = Path(suite_path).parent.parent
    base_dir = Path(base_path) if base_path else suite_dir
    
    suite_name = suite.get("name", "SWE-bench-Shaped Suite")
    tasks = suite.get("tasks", [])
    
    per_task = {}
    passed_tasks = []
    failed_tasks = []
    
    if verbose:
        print(f"Running: {suite_name}", file=sys.stderr)
        print(f"Tasks: {len(tasks)}", file=sys.stderr)
        print("-" * 60, file=sys.stderr)
    
    for task in tasks:
        task_id = task.get("task_id", "UNKNOWN")
        prompt_swe = task.get("prompt_swe", task.get("prompt_original", ""))
        expected_outcome = task.get("expected_outcome", [])
        
        # Get test nodeids
        test_nodeids = task.get("tests", {}).get("nodeids", [])
        
        if verbose:
            print(f"  [{task_id}] ", end="", file=sys.stderr, flush=True)
        
        result = run_pytest_for_nodeids(test_nodeids, base_dir)
        
        # Build per-task result with SWE-bench framing
        task_result = {
            "pass": result["pass"],
            "prompt_swe": prompt_swe,
            "expected_outcome": expected_outcome,
            "passed_tests": result.get("passed_tests", []),
            "failed_tests": result.get("failed_tests", []),
            "brief_evidence": result.get("brief_evidence", []),
        }
        
        per_task[task_id] = task_result
        
        if result["pass"]:
            passed_tasks.append(task_id)
            if verbose:
                print("PASS", file=sys.stderr)
        else:
            failed_tasks.append(task_id)
            if verbose:
                n_failed = len(result.get("failed_tests", []))
                print(f"FAIL ({n_failed} test(s))", file=sys.stderr)
    
    total = len(tasks)
    pass_rate = len(passed_tasks) / total if total > 0 else 0.0
    
    if verbose:
        print("-" * 60, file=sys.stderr)
        print(f"Results: {len(passed_tasks)}/{total} passed ({pass_rate*100:.1f}%)", file=sys.stderr)
    
    return {
        "suite_name": suite_name,
        "suite_path": suite_path,
        "methodology": suite.get("methodology", "apply patch → run tests → pass/fail"),
        "timestamp": datetime.now().isoformat(),
        "total_tasks": total,
        "passed_tasks": passed_tasks,
        "failed_tasks": failed_tasks,
        "pass_rate": pass_rate,
        "per_task": per_task,
    }


def main():
    parser = argparse.ArgumentParser(
        description="SWE-bench-Shaped pytest evaluation runner",
        epilog="""
Example:
  python -m swe_style_eval.runner --suite tasks/swebench_shaped_suite_25.yaml -v
        """,
    )
    parser.add_argument("--suite", required=True, help="Path to YAML suite file")
    parser.add_argument("--out", default="swe_results.json", help="Output JSON file")
    parser.add_argument("--base-path", default=None, help="Base path for test execution")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output to stderr")
    args = parser.parse_args()
    
    results = run_suite(args.suite, args.base_path, args.verbose)
    
    # Write JSON to file
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Clean summary to stdout
    print(json.dumps({
        "suite": results["suite_name"],
        "passed": len(results["passed_tasks"]),
        "failed": len(results["failed_tasks"]),
        "pass_rate": f"{results['pass_rate']*100:.1f}%",
        "output_file": args.out,
    }, indent=2))
    
    sys.exit(0 if len(results["failed_tasks"]) == 0 else 1)


if __name__ == "__main__":
    main()
