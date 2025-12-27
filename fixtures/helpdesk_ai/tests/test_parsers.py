"""
Tests for parsers and validators.

These tests expose bugs in validation logic.
"""

import pytest
from helpdesk_ai.ingest.parsers import JSONParser, CSVParser, TextParser
from helpdesk_ai.ingest.validators import TicketValidator, ValidationError
from helpdesk_ai.ingest.normalize import TicketNormalizer


def test_json_parser():
    """Test JSON parsing."""
    parser = JSONParser()
    
    data = '{"ticket_id": "TKT-001", "title": "Test", "description": "Test desc", "requester_email": "test@example.com"}'
    result = parser.parse(data)
    
    assert result["ticket_id"] == "TKT-001"
    assert result["title"] == "Test"


def test_validator_required_fields():
    """Test validation of required fields."""
    validator = TicketValidator()
    
    # Missing required fields
    data = {}
    errors = validator.validate(data)
    
    assert len(errors) > 0
    error_fields = {e.field for e in errors}
    assert "ticket_id" in error_fields
    assert "title" in error_fields
    assert "requester_email" in error_fields


def test_validator_description_bug():
    """
    Test that exposes validator bug with description field.
    
    BUG: When data has "body" field but not "description", validation
    doesn't properly validate the "body" field.
    """
    validator = TicketValidator()
    
    # Data with "body" instead of "description"
    data = {
        "ticket_id": "TKT-001",
        "title": "Test ticket",
        "body": "",  # Empty body should fail validation
        "requester_email": "test@example.com",
    }
    
    errors = validator.validate(data)
    
    # BUG: This should catch empty "body" field, but validator may miss it
    description_errors = [e for e in errors if "description" in e.message.lower() or e.field == "description"]
    assert len(description_errors) > 0, "Should validate description/body field"


def test_validator_partial_validation_bug():
    """
    Test that exposes bug in partial validation.
    
    BUG: validate_partial doesn't validate description at all, even when provided.
    """
    validator = TicketValidator()
    
    # Partial update with description
    data = {
        "description": "",  # Empty description should fail
    }
    
    errors = validator.validate_partial(data)
    
    # BUG: Should validate description if present, but currently doesn't
    description_errors = [e for e in errors if "description" in e.message.lower() or e.field == "description"]
    # This assertion will fail because description validation is missing
    assert len(description_errors) > 0, "Should validate description in partial updates"


def test_validator_email_format():
    """Test email format validation."""
    validator = TicketValidator()
    
    data = {
        "ticket_id": "TKT-001",
        "title": "Test",
        "description": "Test desc",
        "requester_email": "invalid-email",  # Invalid format
    }
    
    errors = validator.validate(data)
    email_errors = [e for e in errors if e.field == "requester_email"]
    assert len(email_errors) > 0


def test_normalizer_body_to_description():
    """Test that normalizer handles "body" field."""
    normalizer = TicketNormalizer()
    
    data = {
        "ticket_id": "TKT-001",
        "title": "Test",
        "body": "Test description",  # Using "body" instead of "description"
        "requester_email": "test@example.com",
    }
    
    ticket = normalizer.normalize(data)
    assert ticket.description == "Test description"


def test_csv_parser():
    """Test CSV parsing."""
    parser = CSVParser(has_header=True)
    
    data = "ticket_id,title,description,requester_email\nTKT-001,Test,Test desc,test@example.com"
    result = parser.parse(data)
    
    assert result["ticket_id"] == "TKT-001"
    assert result["title"] == "Test"

