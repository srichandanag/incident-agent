import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure the project root is on sys.path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

client = TestClient(app)

def test_root_gradio_ui_accessible():
    """The root path should serve the Gradio UI mounted at '/' and return HTML content."""
    response = client.get('/')
    assert response.status_code == 200
    # Gradio UI returns HTML that includes the <title>Gradio</title> tag or a known JS bundle reference
    # Checking for presence of "gradio" string in the response text (case-insensitive)
    assert "gradio" in response.text.lower()
