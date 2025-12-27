#!/usr/bin/env python3
"""
Fixture loader for loading helpdesk_ai fixture content.
"""

import os
from pathlib import Path
from typing import Tuple


def load_fixture(fixture_dir: str = "fixtures/helpdesk_ai") -> Tuple[str, int, int]:
    """
    Recursively load fixture files and concatenate into one string.
    
    Args:
        fixture_dir: Path to fixture directory
        
    Returns:
        Tuple of (combined_text, total_bytes, file_count)
    """
    fixture_path = Path(fixture_dir)
    if not fixture_path.exists():
        return "", 0, 0
    
    allowed_extensions = {".py", ".md", ".toml", ".txt", ".json"}
    combined_text = []
    total_bytes = 0
    file_count = 0
    
    # Walk directory recursively
    for root, dirs, files in os.walk(fixture_path):
        # Skip __pycache__ and hidden directories
        dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
        
        for file in files:
            # Skip hidden files and .pyc files
            if file.startswith(".") or file.endswith(".pyc"):
                continue
            
            file_path = Path(root) / file
            
            # Check extension
            if file_path.suffix not in allowed_extensions:
                continue
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    file_bytes = len(content.encode("utf-8"))
                    
                    # Get relative path from fixture_dir
                    rel_path = file_path.relative_to(fixture_path)
                    
                    # Add separator and file content
                    combined_text.append(f"===== FILE: {rel_path} =====\n{content}\n")
                    total_bytes += file_bytes
                    file_count += 1
            except Exception:
                # Skip files that can't be read
                continue
    
    return "\n".join(combined_text), total_bytes, file_count


if __name__ == "__main__":
    text, bytes_count, file_count = load_fixture()
    print(f"Loaded {file_count} files, {bytes_count} bytes, {len(text)} characters")

