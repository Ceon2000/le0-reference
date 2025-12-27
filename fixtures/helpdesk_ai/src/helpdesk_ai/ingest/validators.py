"""
Validators for ensuring data quality and completeness.
"""

from typing import Dict, Any, List, Optional
import re


class ValidationError(Exception):
    """Raised when validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        """Initialize validation error."""
        super().__init__(message)
        self.field = field
        self.message = message


class Validator:
    """Base validator interface."""
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationError]:
        """Validate data and return list of errors."""
        raise NotImplementedError


class TicketValidator(Validator):
    """Validator for ticket data."""
    
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    TICKET_ID_PATTERN = re.compile(r'^[A-Z0-9-]+$')
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate ticket data.
        
        BUG: Missing validation for 'description' field in one code path.
        When data comes from certain parsers, description validation is skipped.
        """
        errors = []
        
        # Validate ticket_id
        ticket_id = data.get("ticket_id") or data.get("id") or data.get("ticket")
        if not ticket_id:
            errors.append(ValidationError("ticket_id is required", "ticket_id"))
        elif not isinstance(ticket_id, str):
            errors.append(ValidationError("ticket_id must be a string", "ticket_id"))
        elif not self.TICKET_ID_PATTERN.match(ticket_id):
            errors.append(ValidationError("ticket_id format is invalid", "ticket_id"))
        
        # Validate title
        title = data.get("title") or data.get("subject")
        if not title:
            errors.append(ValidationError("title is required", "title"))
        elif not isinstance(title, str):
            errors.append(ValidationError("title must be a string", "title"))
        elif len(title.strip()) == 0:
            errors.append(ValidationError("title cannot be empty", "title"))
        elif len(title) > 200:
            errors.append(ValidationError("title exceeds maximum length of 200", "title"))
        
        # BUG: Description validation is missing when data comes from certain sources
        # Specifically, if data has "body" but not "description", validation is skipped
        description = data.get("description")
        if not description:
            # Check alternative field names
            description = data.get("body")
            if description:
                # BUG: We found "body" but don't validate it here
                # Should validate description even if it comes from "body" field
                pass
            else:
                errors.append(ValidationError("description is required", "description"))
        elif not isinstance(description, str):
            errors.append(ValidationError("description must be a string", "description"))
        elif len(description.strip()) == 0:
            errors.append(ValidationError("description cannot be empty", "description"))
        
        # Validate email
        email = data.get("requester_email") or data.get("email") or data.get("user_email")
        if not email:
            errors.append(ValidationError("requester_email is required", "requester_email"))
        elif not isinstance(email, str):
            errors.append(ValidationError("requester_email must be a string", "requester_email"))
        elif not self.EMAIL_PATTERN.match(email):
            errors.append(ValidationError("requester_email format is invalid", "requester_email"))
        
        # Validate category if present
        category = data.get("category") or data.get("type")
        if category and not isinstance(category, str):
            errors.append(ValidationError("category must be a string", "category"))
        
        # Validate priority if present
        priority = data.get("priority")
        if priority and not isinstance(priority, str):
            errors.append(ValidationError("priority must be a string", "priority"))
        
        return errors
    
    def validate_partial(self, data: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate partial ticket data (for updates).
        
        BUG: This method doesn't validate description at all, even when provided.
        """
        errors = []
        
        # Only validate fields that are present
        if "ticket_id" in data:
            ticket_id = data["ticket_id"]
            if not isinstance(ticket_id, str):
                errors.append(ValidationError("ticket_id must be a string", "ticket_id"))
            elif not self.TICKET_ID_PATTERN.match(ticket_id):
                errors.append(ValidationError("ticket_id format is invalid", "ticket_id"))
        
        if "title" in data:
            title = data["title"]
            if not isinstance(title, str):
                errors.append(ValidationError("title must be a string", "title"))
            elif len(title.strip()) == 0:
                errors.append(ValidationError("title cannot be empty", "title"))
        
        # BUG: Description validation completely missing in partial validation
        # Should validate description if it's present in the update
        
        if "requester_email" in data:
            email = data["requester_email"]
            if not isinstance(email, str):
                errors.append(ValidationError("requester_email must be a string", "requester_email"))
            elif not self.EMAIL_PATTERN.match(email):
                errors.append(ValidationError("requester_email format is invalid", "requester_email"))
        
        return errors

