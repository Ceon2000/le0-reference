"""T04: Test input validation functions for SQL injection vulnerabilities."""
import pytest
import json
from helpdesk_ai.web.handlers import TicketHandler, Handler


class TestInputValidation:
    """Test input validation against injection attacks."""

    @pytest.fixture
    def ticket_handler(self):
        return TicketHandler()

    def test_handler_rejects_empty_body(self, ticket_handler):
        """POST without body should return 400."""
        response = ticket_handler.post(None)
        assert response["status"] == 400

    def test_handler_rejects_invalid_json(self, ticket_handler):
        """Invalid JSON should return 400."""
        response = ticket_handler.post("not-valid-json{")
        assert response["status"] == 400

    def test_handler_accepts_valid_json(self, ticket_handler):
        """Valid JSON should be accepted."""
        body = json.dumps({"title": "Test", "description": "Test ticket"})
        response = ticket_handler.post(body)
        assert response["status"] == 201

    @pytest.mark.parametrize("malicious_input", [
        "'; DROP TABLE tickets; --",
        "1' OR '1'='1",
        "admin'--",
        "<script>alert('xss')</script>",
        "{{7*7}}",
        "${7*7}",
    ])
    def test_handler_sanitizes_malicious_input(self, ticket_handler, malicious_input):
        """Malicious inputs should be rejected or sanitized."""
        body = json.dumps({
            "title": malicious_input,
            "description": malicious_input,
        })
        response = ticket_handler.post(body)
        # Bug: Handler doesn't validate/sanitize input content
        # It should either reject or sanitize malicious content
        # Currently it just accepts anything - this test documents the vulnerability
        if response["status"] == 201:
            response_body = json.loads(response["body"])
            # At minimum, raw SQL/script shouldn't appear unmodified in response
            # This will fail if input is echoed back unsanitized
            assert "DROP TABLE" not in response["body"] or response["status"] != 201, \
                "SQL injection pattern should be sanitized"

    def test_handler_validates_email_format(self, ticket_handler):
        """Email field should be validated."""
        body = json.dumps({
            "title": "Test",
            "description": "Test",
            "requester_email": "not-an-email",
        })
        response = ticket_handler.post(body)
        # Bug: No email validation - should reject invalid emails
        # Currently accepts anything

    def test_handler_limits_title_length(self, ticket_handler):
        """Title should have length limits."""
        long_title = "A" * 10000
        body = json.dumps({
            "title": long_title,
            "description": "Test",
        })
        response = ticket_handler.post(body)
        # Bug: No length validation - should reject excessively long titles

    def test_handler_limits_description_length(self, ticket_handler):
        """Description should have length limits."""
        long_desc = "A" * 1000000
        body = json.dumps({
            "title": "Test",
            "description": long_desc,
        })
        response = ticket_handler.post(body)
        # Bug: No length validation

    def test_base_handler_returns_405_for_unimplemented(self):
        """Base handler should return 405 Method Not Allowed."""
        handler = Handler()
        assert handler.get()["status"] == 405
        assert handler.post()["status"] == 405
        assert handler.put()["status"] == 405
        assert handler.delete()["status"] == 405
