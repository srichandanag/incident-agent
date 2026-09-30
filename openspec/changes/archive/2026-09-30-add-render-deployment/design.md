# Design

## Context
The current FastAPI application (`app.py`) already hosts the incident triage API and mounts a Gradio Blocks UI at the root path (`/`). The application uses environment variables (`GEMINI_API_KEY`, `DATABASE_URL`) loaded locally via `python-dotenv`. Deploying to Render requires a configuration file (`render.yaml`) that defines a web service, specifies the start command, and configures environment variables through Render’s UI rather than committing secrets.

## Goals / Non-Goals
**Goals:**
- Provide a Render `render.yaml` that enables one‑click deployment of the existing FastAPI + Gradio app.
- Add a lightweight health endpoint (`/health`) that returns `{"status": "ok"}` for readiness checks.
- Document required environment variables and ensure the code reads them at runtime, not from source control.
- Preserve all existing HITL approval logic; no new bypass mechanisms are added.

**Non-Goals:**
- Changing the LangGraph, RAG, or HITL implementations.
- Refactoring the existing business logic or UI components.
- Adding new features beyond deployment configuration and health checks.

## Decisions
- **Render Service Type:** Use a *web service* (not a background worker) because the app runs an HTTP server.
- **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`. Render injects the `$PORT` env var; using it ensures compatibility with Render’s routing.
- **Environment Variable Management:** Declare `GEMINI_API_KEY` and `DATABASE_URL` as *environment variables* in Render’s dashboard. The code already reads them via `os.getenv`, so no code changes are needed beyond ensuring defaults are not hard‑coded.
- **Health Endpoint Implementation:** Add a new FastAPI route `GET /health` that returns a JSON payload `{"status": "ok"}`. This endpoint is cheap, requires no external resources, and satisfies Render’s health‑check feature.
- **File Structure:** Place `render.yaml` at the repository root so that Render automatically detects it. Keep the file in version control (it contains no secrets).

## Risks / Trade-offs
- **Risk:** If required environment variables are missing in Render, the app will fail on start. *Mitigation:* Add clear documentation in `README.md` and in the `render.yaml` comments about the required variables.
- **Risk:** Render free tier limits (e.g., request timeout, disk space) could affect heavy RAG queries. *Mitigation:* Document that heavy workloads should be tested locally; the free tier is intended for demonstration and low‑traffic use.
- **Trade-off:** Keeping the health endpoint simple means it cannot test downstream dependencies (e.g., Supabase connectivity). This is acceptable because the primary goal is to verify the service is up; deeper checks can be added later.

## Migration Plan
1. Add `render.yaml` to the repo.
2. Add `/health` endpoint to `app.py`.
3. Update `README.md` with Render deployment instructions and required env var names.
4. Run local tests (`pytest`) to ensure the new endpoint does not break existing behavior.
5. Push changes and trigger a Render deploy using the provided `render.yaml`.
6. Verify deployment via Render’s health‑check URL and manual API/Gradio UI access.

## Open Questions
- None at this time.
