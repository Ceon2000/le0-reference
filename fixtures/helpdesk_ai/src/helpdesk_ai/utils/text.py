"""
Text utility functions.
"""

import re
from typing import Optional, List


def normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and normalizing line breaks."""
    if not text:
        return ""
    
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Normalize line breaks
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)
    # Remove trailing whitespace
    text = text.strip()
    
    return text


def extract_email(text: str) -> Optional[str]:
    """Extract email address from text."""
    email_pattern = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
    match = email_pattern.search(text)
    return match.group(0) if match else None


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text."""
    # Simple keyword extraction - words that are not common stop words
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "have", "has", "had", "do", "does", "did", "will", "would",
        "should", "could", "may", "might", "must", "can", "this", "that",
        "these", "those", "i", "you", "he", "she", "it", "we", "they",
    }
    
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    keywords = [w for w in words if len(w) >= min_length and w not in stop_words]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    
    return unique_keywords


def sanitize_filename(text: str) -> str:
    """Sanitize text for use as filename."""
    # Replace invalid characters with underscore
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', text)
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    # Limit length
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    return sanitized

