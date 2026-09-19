"""Shared test fixtures for Opero."""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def sample_tool():
    """A minimal TOOL dict for testing."""
    return {
        "name": "test_tool",
        "description": "A test tool",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    }
