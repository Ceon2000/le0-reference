#!/usr/bin/env python3
"""
Deterministic repository lookup tool for retrieval-native benchmark.

Returns snippets with stable SHA256-based IDs for deduplication.
IP-safe: No LE-0 internals, treats runtime as black box.
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Maximum snippet size in characters
MAX_SNIPPET_SIZE = 2000

# Cache of loaded files
_file_cache: Dict[str, str] = {}


def _load_file(filepath: str) -> str:
    """Load file content with caching."""
    if filepath not in _file_cache:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                _file_cache[filepath] = f.read()
        except Exception:
            _file_cache[filepath] = ""
    return _file_cache[filepath]


def _get_snippet_id(text: str) -> str:
    """Generate deterministic snippet ID from content."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def _find_files_by_pattern(base_dir: str, pattern: str) -> List[str]:
    """Find files matching a pattern."""
    base_path = Path(base_dir)
    matches = []
    for path in base_path.rglob('*'):
        if path.is_file() and pattern.lower() in path.name.lower():
            matches.append(str(path))
    return sorted(matches)[:5]  # Limit to 5 matches


def _extract_function(content: str, func_name: str) -> Optional[Tuple[str, int, int]]:
    """Extract a function definition from content."""
    # Match Python function definitions
    pattern = rf'^(def\s+{re.escape(func_name)}\s*\([^)]*\).*?)(?=\ndef\s|\nclass\s|\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        func_text = match.group(1).strip()
        start_line = content[:match.start()].count('\n') + 1
        end_line = start_line + func_text.count('\n')
        return func_text[:MAX_SNIPPET_SIZE], start_line, end_line
    return None


def _extract_class(content: str, class_name: str) -> Optional[Tuple[str, int, int]]:
    """Extract a class definition from content."""
    pattern = rf'^(class\s+{re.escape(class_name)}\s*[:\(].*?)(?=\nclass\s|\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        class_text = match.group(1).strip()
        start_line = content[:match.start()].count('\n') + 1
        end_line = start_line + class_text.count('\n')
        return class_text[:MAX_SNIPPET_SIZE], start_line, end_line
    return None


def _extract_lines(content: str, start: int, end: int) -> Tuple[str, int, int]:
    """Extract specific line range from content."""
    lines = content.split('\n')
    start = max(1, start)
    end = min(len(lines), end)
    snippet = '\n'.join(lines[start-1:end])
    return snippet[:MAX_SNIPPET_SIZE], start, end


def repo_lookup(
    query: str,
    base_dir: str = "fixtures/helpdesk_ai"
) -> Dict:
    """
    Deterministic repository lookup.
    
    Query formats:
    - "file:router.py" - Get file overview
    - "file:router.py:10-50" - Get specific lines
    - "func:calculate_priority" - Find function
    - "class:TicketRouter" - Find class
    - "search:validation" - Search for keyword
    
    Returns:
        {
            "snippet_id": str,      # SHA256-based ID (stable)
            "snippet_text": str,    # Actual code content
            "source_path": str,     # File path
            "line_range": [int, int],
            "query": str,           # Original query
            "token_estimate": int   # ~4 bytes per token
        }
    """
    result = {
        "snippet_id": "",
        "snippet_text": "",
        "source_path": "",
        "line_range": [0, 0],
        "query": query,
        "token_estimate": 0
    }
    
    query = query.strip()
    
    # Parse query type
    if query.startswith("file:"):
        # File lookup: file:router.py or file:router.py:10-50
        parts = query[5:].split(":")
        filename = parts[0]
        
        # Find file
        matches = _find_files_by_pattern(base_dir, filename)
        if not matches:
            result["snippet_text"] = f"# File not found: {filename}"
            result["snippet_id"] = _get_snippet_id(result["snippet_text"])
            return result
        
        filepath = matches[0]
        content = _load_file(filepath)
        
        if len(parts) > 1 and "-" in parts[1]:
            # Line range specified
            try:
                start, end = map(int, parts[1].split("-"))
                snippet, start_line, end_line = _extract_lines(content, start, end)
            except ValueError:
                snippet = content[:MAX_SNIPPET_SIZE]
                start_line, end_line = 1, snippet.count('\n') + 1
        else:
            # Full file (truncated)
            snippet = content[:MAX_SNIPPET_SIZE]
            start_line, end_line = 1, snippet.count('\n') + 1
        
        result["snippet_text"] = snippet
        result["source_path"] = filepath
        result["line_range"] = [start_line, end_line]
    
    elif query.startswith("func:"):
        # Function lookup
        func_name = query[5:].strip()
        
        # Search all Python files
        for filepath in Path(base_dir).rglob("*.py"):
            content = _load_file(str(filepath))
            extracted = _extract_function(content, func_name)
            if extracted:
                snippet, start_line, end_line = extracted
                result["snippet_text"] = snippet
                result["source_path"] = str(filepath)
                result["line_range"] = [start_line, end_line]
                break
        
        if not result["snippet_text"]:
            result["snippet_text"] = f"# Function not found: {func_name}"
    
    elif query.startswith("class:"):
        # Class lookup
        class_name = query[6:].strip()
        
        for filepath in Path(base_dir).rglob("*.py"):
            content = _load_file(str(filepath))
            extracted = _extract_class(content, class_name)
            if extracted:
                snippet, start_line, end_line = extracted
                result["snippet_text"] = snippet
                result["source_path"] = str(filepath)
                result["line_range"] = [start_line, end_line]
                break
        
        if not result["snippet_text"]:
            result["snippet_text"] = f"# Class not found: {class_name}"
    
    elif query.startswith("search:"):
        # Keyword search
        keyword = query[7:].strip().lower()
        matches = []
        
        for filepath in Path(base_dir).rglob("*.py"):
            content = _load_file(str(filepath))
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if keyword in line.lower():
                    # Extract context around match
                    start = max(0, i - 2)
                    end = min(len(lines), i + 8)
                    context = '\n'.join(lines[start:end])
                    matches.append({
                        "path": str(filepath),
                        "line": i + 1,
                        "context": context[:500]
                    })
                    if len(matches) >= 3:
                        break
            if len(matches) >= 3:
                break
        
        if matches:
            snippet_parts = []
            for m in matches:
                snippet_parts.append(f"# {m['path']}:{m['line']}\n{m['context']}")
            result["snippet_text"] = '\n\n'.join(snippet_parts)[:MAX_SNIPPET_SIZE]
            result["source_path"] = matches[0]["path"]
            result["line_range"] = [matches[0]["line"], matches[0]["line"] + 10]
        else:
            result["snippet_text"] = f"# No matches for: {keyword}"
    
    else:
        # Default: treat as file or keyword search
        result["snippet_text"] = f"# Unknown query format: {query}"
    
    # Generate stable snippet ID
    result["snippet_id"] = _get_snippet_id(result["snippet_text"])
    result["token_estimate"] = len(result["snippet_text"].encode('utf-8')) // 4
    
    return result


def get_predefined_lookups(task_idx: int) -> List[str]:
    """
    Get deterministic lookup queries for a specific task.
    
    Each task has a predefined set of lookups to ensure reproducibility.
    """
    # Mapping of task index to required lookups
    lookup_patterns = [
        # Task 1: routing logic
        ["file:router.py", "func:route_ticket", "search:routing"],
        # Task 2: priority scoring
        ["file:scoring.py", "func:calculate_priority", "search:normalize"],
        # Task 3: database connections
        ["file:storage.py", "func:get_connection", "search:connection"],
        # Task 4: input validation
        ["search:validate", "func:validate_input", "file:validators.py"],
        # Task 5: ticket lifecycle
        ["file:ticket.py", "class:Ticket", "search:state"],
        # Task 6: error handling
        ["search:except", "search:error", "func:handle_error"],
        # Task 7: caching
        ["search:cache", "func:get_cached", "file:cache.py"],
        # Task 8: logging
        ["search:log", "func:log_event", "file:logger.py"],
        # Task 9: configuration
        ["file:config.py", "search:secret", "func:load_config"],
        # Task 10: API endpoints
        ["file:api.py", "search:auth", "func:handle_request"],
        # Task 11: rate limiting
        ["search:rate", "func:check_rate_limit", "file:limiter.py"],
        # Task 12: assignment
        ["func:assign_ticket", "search:assign", "file:assignment.py"],
        # Task 13: notifications
        ["search:notify", "func:send_notification", "file:notify.py"],
        # Task 14: search functionality
        ["func:search_tickets", "search:index", "file:search.py"],
        # Task 15: file attachments
        ["search:attach", "func:upload_file", "file:attachments.py"],
        # Task 16: session management
        ["search:session", "func:create_session", "file:session.py"],
        # Task 17: audit logging
        ["search:audit", "func:log_audit", "file:audit.py"],
        # Task 18: queue management
        ["file:queue.py", "func:enqueue", "search:priority"],
        # Task 19: escalation
        ["search:escalat", "func:escalate_ticket", "file:escalation.py"],
        # Task 20: SLA tracking
        ["search:sla", "func:check_sla", "file:sla.py"],
        # Task 21: metrics
        ["search:metric", "func:record_metric", "file:metrics.py"],
        # Task 22: backup/recovery
        ["search:backup", "func:backup_data", "file:storage.py:1-100"],
        # Task 23: inter-service
        ["search:http", "func:call_service", "file:client.py"],
        # Task 24: permissions
        ["search:permission", "func:check_permission", "class:User"],
        # Task 25: architecture
        ["file:__init__.py", "file:main.py", "search:import"],
    ]
    
    idx = (task_idx - 1) % len(lookup_patterns)
    return lookup_patterns[idx]


if __name__ == "__main__":
    # Test the lookup tool
    import json
    
    test_queries = [
        "file:router.py",
        "func:route_ticket",
        "search:validation",
    ]
    
    for q in test_queries:
        result = repo_lookup(q)
        print(f"\nQuery: {q}")
        print(f"  ID: {result['snippet_id']}")
        print(f"  Path: {result['source_path']}")
        print(f"  Lines: {result['line_range']}")
        print(f"  Tokens: {result['token_estimate']}")
        print(f"  Text: {result['snippet_text'][:100]}...")
