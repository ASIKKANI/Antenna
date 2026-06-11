"""
Pytest fixtures for ChronosPet backend tests.
All LLM calls are mocked — no API keys needed.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_llm_router():
    """Mock the LiteLLM Router to return structured task JSON."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"clean_title": "Deploy server patch", "deadline_epoch": 9999999999, "priority_level": "high"}'

    with patch("main.llm_router") as mock_router:
        mock_router.completion.return_value = mock_response
        yield mock_router


@pytest.fixture
def client(mock_llm_router):
    """FastAPI test client with mocked LLM."""
    from main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_webhook_payload():
    """Standard webhook payload matching PRD Section 8.2."""
    return {
        "sender": "919876543210",
        "message_id": "WA-MSG-TEST001",
        "timestamp": 1781124300,
        "message_type": "text",
        "content": "Finish documenting the API endpoints by 6 PM today, priority high",
    }


@pytest.fixture
def unauthorized_payload():
    """Webhook payload from an unauthorized sender."""
    return {
        "sender": "000000000000",
        "message_id": "WA-MSG-UNAUTH",
        "timestamp": 1781124300,
        "message_type": "text",
        "content": "This should be rejected",
    }
