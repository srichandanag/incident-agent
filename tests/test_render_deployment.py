import os
import pathlib
import pytest

# Test that render.yaml exists at project root and contains required env vars placeholders

def test_render_yaml_exists_and_contains_env_vars():
    project_root = pathlib.Path(__file__).resolve().parents[1]
    render_yaml_path = project_root / "render.yaml"
    assert render_yaml_path.is_file(), "render.yaml should exist in project root"
    content = render_yaml_path.read_text()
    # Ensure required env vars are listed
    for var in ["GEMINI_API_KEY", "DATABASE_URL"]:
        assert var in content, f"{var} should be listed in render.yaml envVars"

# Mock environment variables to simulate Render runtime and ensure app can start
def test_app_starts_with_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy_key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    # Import app after env vars are set to ensure any module-level env usage picks them up
    from app import app  # noqa: F401
    # No exception means app loaded correctly with mocked env
    assert True
