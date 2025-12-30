#!/usr/bin/env python3
"""
SWE-Style Evaluation Runner

Runs the SWE-bench-style evaluation suite against fixtures/helpdesk_ai.

Usage:
    python -m swe_style_eval.runner --suite tasks/swe_style_suite_25.yaml --out results.json
"""

import argparse
import json
import os
import sys
import subprocess
import re
import ast
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import yaml

from .checks import (
    run_pytest_check,
    run_regex_check,
    run_ast_check,
)


def load_suite(suite_path: str) -> Dict[str, Any]:
    """Load the YAML suite file."""
    with open(suite_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_assertion(
    assertion: Dict[str, Any],
    files_in_scope: List[str],
    base_path: Path,
    eval_base: Path,
) -> Tuple[bool, str, Optional[str]]:
    """
    Run a single assertion.
    
    Returns:
        Tuple of (passed, description, evidence)
    """
    check_type = assertion.get("check_type")
    description = assertion.get("description", "Unknown check")
    
    try:
        if check_type == "pytest":
            test_path = assertion.get("test_path", "")
            passed, evidence = run_pytest_check(test_path, eval_base)
            return passed, description, evidence
            
        elif check_type == "regex":
            pattern = assertion.get("pattern", "")
            expect_match = assertion.get("expect_match", True)
            passed, evidence = run_regex_check(pattern, files_in_scope, base_path, expect_match)
            return passed, description, evidence
            
        elif check_type == "ast_check":
            pattern_name = assertion.get("pattern", "")
            passed, evidence = run_ast_check(pattern_name, files_in_scope, base_path)
            return passed, description, evidence
            
        else:
            return False, description, f"Unknown check type: {check_type}"
            
    except Exception as e:
        return False, description, f"Error: {str(e)}"


def run_task(
    task: Dict[str, Any],
    base_path: Path,
    eval_base: Path,
) -> Dict[str, Any]:
    """
    Run all assertions for a single task.
    
    Returns:
        Task result dictionary.
    """
    task_id = task.get("task_id", "UNKNOWN")
    files_in_scope = task.get("files_in_scope", [])
    outcomes = task.get("expected_outcomes", {})
    assertions = outcomes.get("assertions", [])
    
    passed_assertions = []
    failed_assertions = []
    evidence_list = []
    
    for assertion in assertions:
        passed, desc, evidence = run_assertion(
            assertion, files_in_scope, base_path, eval_base
        )
        
        if passed:
            passed_assertions.append(desc)
        else:
            failed_assertions.append(desc)
        
        evidence_list.append({
            "description": desc,
            "passed": passed,
            "evidence": evidence,
        })
    
    # Task passes if all assertions pass
    task_passed = len(failed_assertions) == 0 and len(passed_assertions) > 0
    
    return {
        "task_id": task_id,
        "pass": task_passed,
        "passed_assertions": passed_assertions,
        "failed_assertions": failed_assertions,
        "evidence": evidence_list,
        "files_in_scope": files_in_scope,
    }


def run_suite(
    suite_path: str,
    base_path: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run the full evaluation suite.
    
    Args:
        suite_path: Path to the YAML suite file
        base_path: Base path to the target codebase (defaults to fixtures/helpdesk_ai)
        verbose: Print progress
        
    Returns:
        Results dictionary
    """
    suite = load_suite(suite_path)
    
    # Determine paths
    suite_dir = Path(suite_path).parent.parent
    if base_path:
        target_base = Path(base_path)
    else:
        target_codebase = suite.get("target_codebase", "fixtures/helpdesk_ai")
        target_base = suite_dir / target_codebase
    
    eval_base = suite_dir / "swe_style_eval"
    
    tasks = suite.get("tasks", [])
    results = []
    passed_tasks = []
    failed_tasks = []
    
    if verbose:
        print(f"Running SWE-Style Evaluation Suite", file=sys.stderr)
        print(f"  Suite: {suite_path}", file=sys.stderr)
        print(f"  Target: {target_base}", file=sys.stderr)
        print(f"  Tasks: {len(tasks)}", file=sys.stderr)
        print("-" * 60, file=sys.stderr)
    
    for task in tasks:
        task_id = task.get("task_id", "UNKNOWN")
        
        if verbose:
            print(f"  [{task_id}] Running...", end=" ", file=sys.stderr)
        
        result = run_task(task, target_base, eval_base)
        results.append(result)
        
        if result["pass"]:
            passed_tasks.append(task_id)
            if verbose:
                print("PASS", file=sys.stderr)
        else:
            failed_tasks.append(task_id)
            if verbose:
                print(f"FAIL ({len(result['failed_assertions'])} assertions)", file=sys.stderr)
    
    pass_rate = len(passed_tasks) / len(tasks) if tasks else 0.0
    
    if verbose:
        print("-" * 60, file=sys.stderr)
        print(f"Results: {len(passed_tasks)}/{len(tasks)} passed ({pass_rate*100:.1f}%)", file=sys.stderr)
    
    return {
        "suite": suite_path,
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(tasks),
        "passed_tasks": passed_tasks,
        "failed_tasks": failed_tasks,
        "pass_count": len(passed_tasks),
        "fail_count": len(failed_tasks),
        "pass_rate": pass_rate,
        "per_task": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run SWE-Style Evaluation Suite"
    )
    parser.add_argument(
        "--suite",
        required=True,
        help="Path to the YAML suite file"
    )
    parser.add_argument(
        "--out",
        default="results.json",
        help="Output JSON file path"
    )
    parser.add_argument(
        "--base-path",
        default=None,
        help="Base path to target codebase"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print progress"
    )
    
    args = parser.parse_args()
    
    results = run_suite(
        suite_path=args.suite,
        base_path=args.base_path,
        verbose=args.verbose,
    )
    
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results written to {args.out}")
    
    # Exit with non-zero if any failures
    sys.exit(0 if results["fail_count"] == 0 else 1)


if __name__ == "__main__":
    main()
