"""
Parsers for converting raw input data into structured ticket data.
"""

import json
import csv
from io import StringIO
from typing import Dict, Any, List, Optional
from ..domain.models import Ticket, Category, Priority, TicketStatus


class Parser:
    """Base parser interface."""
    
    def parse(self, data: str) -> Dict[str, Any]:
        """Parse input data into a dictionary."""
        raise NotImplementedError


class JSONParser(Parser):
    """Parser for JSON-formatted ticket data."""
    
    def parse(self, data: str) -> Dict[str, Any]:
        """Parse JSON data into ticket dictionary."""
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValueError("JSON must be an object")
            return parsed
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")


class TextParser(Parser):
    """Parser for plain text ticket data."""
    
    def __init__(self, delimiter: str = "\n"):
        """Initialize text parser with delimiter."""
        self.delimiter = delimiter
    
    def parse(self, data: str) -> Dict[str, Any]:
        """Parse text data into ticket dictionary."""
        lines = data.split(self.delimiter)
        result = {}
        
        for line in lines:
            line = line.strip()
            if not line or ":" not in line:
                continue
            
            key, value = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            
            if key == "description":
                result.setdefault("description", "")
                result["description"] += value + "\n"
            else:
                result[key] = value
        
        if "description" in result:
            result["description"] = result["description"].rstrip()
        
        return result


class CSVParser(Parser):
    """Parser for CSV-formatted ticket data."""
    
    def __init__(self, has_header: bool = True):
        """Initialize CSV parser."""
        self.has_header = has_header
    
    def parse(self, data: str) -> Dict[str, Any]:
        """Parse CSV data into ticket dictionary."""
        reader = csv.reader(StringIO(data))
        rows = list(reader)
        
        if not rows:
            raise ValueError("CSV data is empty")
        
        if self.has_header:
            headers = [h.strip().lower().replace(" ", "_") for h in rows[0]]
            if len(rows) < 2:
                raise ValueError("CSV has header but no data rows")
            values = rows[1]
        else:
            headers = [f"field_{i}" for i in range(len(rows[0]))]
            values = rows[0]
        
        if len(headers) != len(values):
            raise ValueError("Header and value count mismatch")
        
        return dict(zip(headers, values))


class MultiFormatParser:
    """Parser that tries multiple formats."""
    
    def __init__(self):
        """Initialize multi-format parser."""
        self.parsers = [
            JSONParser(),
            CSVParser(),
            TextParser(),
        ]
    
    def parse(self, data: str) -> Dict[str, Any]:
        """Try parsing with each parser until one succeeds."""
        errors = []
        for parser in self.parsers:
            try:
                return parser.parse(data)
            except Exception as e:
                errors.append(f"{parser.__class__.__name__}: {str(e)}")
        
        raise ValueError(f"Failed to parse with any parser: {'; '.join(errors)}")

