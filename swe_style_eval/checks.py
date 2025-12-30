#!/usr/bin/env python3
"""
SWE-Style Evaluation Checks

Implements the three types of checks:
1. pytest - Run pytest tests
2. regex - Match regex patterns in files
3. ast_check - AST-based structural checks
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional


def run_pytest_check(test_path: str, eval_base: Path) -> Tuple[bool, str]:
    """
    Run a pytest test and return pass/fail with evidence.
    
    Args:
        test_path: Relative path like "test_generated/test_t01.py::test_func"
        eval_base: Base path to swe_style_eval directory
        
    Returns:
        Tuple of (passed, evidence)
    """
    full_path = eval_base / test_path.split("::")[0]
    
    if not full_path.exists():
        return False, f"Test file not found: {full_path}"
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(eval_base / test_path), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(eval_base.parent),
        )
        
        passed = result.returncode == 0
        evidence = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
        if result.returncode != 0:
            evidence += "\n" + (result.stderr[-200:] if len(result.stderr) > 200 else result.stderr)
        
        return passed, evidence.strip()
        
    except subprocess.TimeoutExpired:
        return False, "Test timed out after 60s"
    except Exception as e:
        return False, f"Test execution error: {str(e)}"


def run_regex_check(
    pattern: str,
    files_in_scope: List[str],
    base_path: Path,
    expect_match: bool = True,
) -> Tuple[bool, str]:
    """
    Run regex pattern check against files in scope.
    
    Args:
        pattern: Regex pattern to search for
        files_in_scope: List of relative file paths
        base_path: Base path to target codebase
        expect_match: True if pattern should be found, False if it should NOT be found
        
    Returns:
        Tuple of (passed, evidence)
    """
    try:
        regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as e:
        return False, f"Invalid regex pattern: {e}"
    
    matches = []
    files_checked = []
    
    for file_path in files_in_scope:
        full_path = base_path / file_path
        if not full_path.exists():
            continue
            
        files_checked.append(file_path)
        
        try:
            content = full_path.read_text(encoding='utf-8')
            file_matches = list(regex.finditer(content))
            
            for m in file_matches:
                line_num = content[:m.start()].count('\n') + 1
                matches.append({
                    "file": file_path,
                    "line": line_num,
                    "match": m.group()[:50],
                })
        except Exception:
            continue
    
    found = len(matches) > 0
    
    if expect_match:
        # We expect to find the pattern
        passed = found
        if passed:
            evidence = f"Found {len(matches)} match(es) in {len(files_checked)} files"
        else:
            evidence = f"Pattern not found in {len(files_checked)} files"
    else:
        # We expect NOT to find the pattern (security check)
        passed = not found
        if passed:
            evidence = f"Pattern correctly absent from {len(files_checked)} files"
        else:
            evidence = f"Found {len(matches)} unwanted match(es): {matches[:3]}"
    
    return passed, evidence


def run_ast_check(
    pattern_name: str,
    files_in_scope: List[str],
    base_path: Path,
) -> Tuple[bool, str]:
    """
    Run AST-based structural check.
    
    Args:
        pattern_name: Name of the AST pattern to check
        files_in_scope: List of relative file paths
        base_path: Base path to target codebase
        
    Returns:
        Tuple of (passed, evidence)
    """
    checker = AST_CHECKS.get(pattern_name)
    if not checker:
        return False, f"Unknown AST check pattern: {pattern_name}"
    
    results = []
    files_checked = []
    
    for file_path in files_in_scope:
        full_path = base_path / file_path
        if not full_path.exists():
            continue
            
        files_checked.append(file_path)
        
        try:
            content = full_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            passed, evidence = checker(tree, content, file_path)
            results.append((file_path, passed, evidence))
        except SyntaxError as e:
            results.append((file_path, False, f"Syntax error: {e}"))
        except Exception as e:
            results.append((file_path, False, f"Parse error: {e}"))
    
    # Check passes if all files pass
    all_passed = all(r[1] for r in results) and len(results) > 0
    
    if all_passed:
        evidence = f"All {len(files_checked)} files pass AST check"
    else:
        failures = [f"{r[0]}: {r[2]}" for r in results if not r[1]]
        evidence = f"Failures: {'; '.join(failures[:3])}"
    
    return all_passed, evidence


# ============================================================================
# AST Check Implementations
# ============================================================================

def check_with_statement_for_file_ops(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check that file operations use context managers (with statement)."""
    
    class FileOpVisitor(ast.NodeVisitor):
        def __init__(self):
            self.violations = []
            self.in_with = False
            
        def visit_With(self, node):
            old_in_with = self.in_with
            self.in_with = True
            self.generic_visit(node)
            self.in_with = old_in_with
            
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == 'open':
                if not self.in_with:
                    self.violations.append(node.lineno)
            self.generic_visit(node)
    
    visitor = FileOpVisitor()
    visitor.visit(tree)
    
    if visitor.violations:
        return False, f"open() without 'with' at lines: {visitor.violations[:3]}"
    return True, "All file operations use context managers"


def check_except_has_logging(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check that except blocks have logging calls."""
    
    class ExceptVisitor(ast.NodeVisitor):
        def __init__(self):
            self.bare_excepts = []
            
        def visit_ExceptHandler(self, node):
            # Check if body contains only 'pass'
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                self.bare_excepts.append(node.lineno)
            self.generic_visit(node)
    
    visitor = ExceptVisitor()
    visitor.visit(tree)
    
    if visitor.bare_excepts:
        return False, f"Bare 'except: pass' at lines: {visitor.bare_excepts[:3]}"
    return True, "No bare except:pass patterns found"


def check_method_has_logging(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check that methods have logging calls (basic check)."""
    # This is a simplified check - just verify logging module is imported
    has_logging = 'import logging' in content or 'from logging import' in content
    
    if has_logging:
        return True, "Logging module imported"
    return False, "No logging import found"


def check_handler_has_auth_check(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check that handler functions have authentication checks."""
    # Simplified check for auth-related patterns
    auth_patterns = ['auth', 'authenticate', 'verify_user', 'check_permission', 'require_auth']
    
    for pattern in auth_patterns:
        if pattern in content.lower():
            return True, f"Auth pattern '{pattern}' found"
    
    return False, "No authentication patterns found"


def check_has_retry_logic(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check for retry logic patterns."""
    retry_patterns = ['retry', 'max_attempts', 'backoff', 'for _ in range']
    
    for pattern in retry_patterns:
        if pattern in content.lower():
            return True, f"Retry pattern '{pattern}' found"
    
    return False, "No retry logic found"


def check_dict_lookup_or_set(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check that dict lookups are used (O(1) vs O(N))."""
    # Check for dictionary usage patterns
    if '.get(' in content or '[]' in content:
        return True, "Dictionary lookup patterns found"
    return False, "No indexed lookup patterns found"


def check_no_nested_for_loops(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check for O(N^2) nested loops."""
    
    class NestedLoopVisitor(ast.NodeVisitor):
        def __init__(self):
            self.nested_loops = []
            self.loop_depth = 0
            
        def visit_For(self, node):
            self.loop_depth += 1
            if self.loop_depth > 1:
                self.nested_loops.append(node.lineno)
            self.generic_visit(node)
            self.loop_depth -= 1
    
    visitor = NestedLoopVisitor()
    visitor.visit(tree)
    
    # Allow some nested loops, just flag if excessive
    if len(visitor.nested_loops) > 2:
        return False, f"Multiple nested loops at lines: {visitor.nested_loops[:5]}"
    return True, f"Acceptable loop nesting ({len(visitor.nested_loops)} nested)"


def check_has_timing_instrumentation(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check for timing/metrics instrumentation."""
    timing_patterns = ['time.time()', 'time.perf_counter()', 'datetime.now()', 'timedelta', 'metrics']
    
    for pattern in timing_patterns:
        if pattern in content:
            return True, f"Timing pattern '{pattern}' found"
    
    return False, "No timing instrumentation found"


def check_atomic_write_pattern(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check for atomic write pattern (temp file + rename)."""
    atomic_patterns = ['tempfile', 'rename', 'replace', 'shutil.move']
    
    found = [p for p in atomic_patterns if p in content]
    if found:
        return True, f"Atomic patterns found: {found}"
    
    return False, "No atomic write patterns found"


def check_try_except_around_service_calls(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check that service calls are wrapped in try-except."""
    
    class TryVisitor(ast.NodeVisitor):
        def __init__(self):
            self.try_count = 0
            
        def visit_Try(self, node):
            self.try_count += 1
            self.generic_visit(node)
    
    visitor = TryVisitor()
    visitor.visit(tree)
    
    if visitor.try_count > 0:
        return True, f"Found {visitor.try_count} try-except blocks"
    return False, "No try-except blocks found"


def check_permission_check_before_mutation(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check for permission checks before state mutations."""
    permission_patterns = ['permission', 'can_', 'has_access', 'is_authorized', 'check_role']
    
    for pattern in permission_patterns:
        if pattern in content.lower():
            return True, f"Permission pattern '{pattern}' found"
    
    return False, "No permission check patterns found"


def check_error_path_logged(tree: ast.AST, content: str, file_path: str) -> Tuple[bool, str]:
    """Check that error paths include logging."""
    # Simple heuristic: check if 'log' appears near 'error' or 'exception'
    if ('log' in content.lower() and 
        ('error' in content.lower() or 'exception' in content.lower())):
        return True, "Error logging patterns found"
    return False, "No error logging patterns found"


# Registry of AST checks
AST_CHECKS = {
    "with_statement_for_file_ops": check_with_statement_for_file_ops,
    "except_has_logging": check_except_has_logging,
    "method_has_logging": check_method_has_logging,
    "handler_has_auth_check": check_handler_has_auth_check,
    "has_retry_logic": check_has_retry_logic,
    "dict_lookup_or_set": check_dict_lookup_or_set,
    "no_nested_for_loops": check_no_nested_for_loops,
    "has_timing_instrumentation": check_has_timing_instrumentation,
    "atomic_write_pattern": check_atomic_write_pattern,
    "try_except_around_service_calls": check_try_except_around_service_calls,
    "permission_check_before_mutation": check_permission_check_before_mutation,
    "error_path_logged": check_error_path_logged,
}
