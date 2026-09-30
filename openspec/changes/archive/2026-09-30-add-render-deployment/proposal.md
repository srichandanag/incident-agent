# Proposal

## Why
Deploy the existing FastAPI + Gradio incident triage application to Render to provide a cost‑free, managed hosting environment and simplify production deployments.

## What Changes
- Add a Render `render.yaml` deployment configuration for the FastAPI service.
- Document required environment variables (`GEMINI_API_KEY`, `DATABASE_URL`).
- Add a health/readiness endpoint `/health` to verify service liveness.
- Ensure the Gradio UI remains mounted at `/` alongside the FastAPI API.
- Add deployment‑focused tests that mock Render, Gemini, and Supabase services.
- Preserve all existing HITL approval behavior; no bypass mechanisms are introduced.

## Capabilities
### New Capabilities
- `render-deployment`: Defines the deployment contract for Render, including configuration files, required env vars, and health checks.

### Modified Capabilities
- *None* – existing incident‑triage capabilities remain unchanged.

## Impact
- Adds a new deployment artifact (`render.yaml`).
- Introduces a health endpoint (`/health`).
- Requires environment variables to be set in Render, not committed to source.
- No changes to LangGraph, RAG, or HITL logic.
