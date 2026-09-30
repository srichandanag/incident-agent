import os
import sys
import pytest
from fastapi.testclient import TestClient
from unittest import mock

# Ensure the project root is on sys.path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, _pending_actions

client = TestClient(app)

# Fixture to mock the graph invoke to always require HITL
@pytest.fixture(autouse=True)
def mock_graph(monkeypatch):
    class MockGraph:
        def invoke(self, inputs, config=None):
            return {"hitl_required": True, "pending_id": "mock-pending-id"}
    # Mock get_graph_and_saver to return our MockGraph and a dummy saver
    monkeypatch.setattr('app.get_graph_and_saver', lambda: (MockGraph(), mock.Mock()))
    yield

def test_submit_incident_creates_pending_action():
    response = client.post('/incident', json={"description": "test incident", "payload": {}})
    assert response.status_code == 200
    data = response.json()
    assert data["hitl_required"] is True
    conv_id = data["conversation_id"]
    # Verify pending action stored
    assert conv_id in _pending_actions
    assert _pending_actions[conv_id]["approved"] is None

def test_sensitive_endpoint_without_approval_denied():
    resp = client.post('/incident', json={"description": "test", "payload": {}})
    conv_id = resp.json()["conversation_id"]
    # Attempt to run sensitive action before approval
    resp2 = client.post(f'/sensitive/{conv_id}/run')
    assert resp2.status_code == 403
    assert "Human approval required" in resp2.json()["detail"]

def test_approve_allows_sensitive_action():
    resp = client.post('/incident', json={"description": "test", "payload": {}})
    conv_id = resp.json()["conversation_id"]
    approve_resp = client.post(f'/incident/{conv_id}/approve')
    assert approve_resp.status_code == 200
    run_resp = client.post(f'/sensitive/{conv_id}/run')
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "sensitive action executed"

def test_reject_blocks_sensitive_action():
    resp = client.post('/incident', json={"description": "test", "payload": {}})
    conv_id = resp.json()["conversation_id"]
    reject_resp = client.post(f'/incident/{conv_id}/reject')
    assert reject_resp.status_code == 200
    run_resp = client.post(f'/sensitive/{conv_id}/run')
    assert run_resp.status_code == 403

def test_invalid_conversation_returns_404():
    resp = client.post('/incident/invalid-id/approve')
    assert resp.status_code == 404
