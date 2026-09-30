# Tasks

## 1. Deployment Configuration

- [x] 1.1 Create `render.yaml` at repository root describing Render web service, start command, and environment variables. Verify file exists.
- [x] 1.2 Add documentation in `README.md` for Render deployment steps and required env vars. Verify documentation builds with a markdown preview.

## 2. Health Endpoint

- [x] 2.1 Add FastAPI route `GET /health` returning `{"status": "ok"}`. Verify endpoint returns 200 and correct JSON via `curl` or TestClient.
- [x] 2.2 Write pytest `test_health_endpoint.py` that uses `TestClient(app)` to assert the health response. Mock no external services.

## 3. CI / Test Coverage

- [x] 3.1 Add deployment‑focused test `test_render_deployment.py` that mocks Render environment variables and ensures no real Render calls are made. Verify test passes.
- [x] 3.2 Update existing test suite to include health check and ensure all tests pass (`pytest -q`).

## 4. Local Verification & Render Validation

- [x] 4.1 Run the application locally (`uvicorn app:app --reload`) and manually check that `/health` and the Gradio UI at `/` are reachable.
- [x] 4.2 Deploy to Render using the `render.yaml` configuration (manual step). Verify the health check endpoint passes Renderâ€™s health check and the Gradio UI loads.
- [x] 4.3 After successful Render deployment, run the mocked deployment tests again to ensure they still pass.