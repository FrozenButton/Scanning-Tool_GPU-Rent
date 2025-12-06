# Two-part rental deployment

This project now ships as two separate binaries or scripts so the roles are clearly separated:

1. **Player client agent (gaming PC)** — signs in, buys credits, submits scan payloads, and polls job status from the rental backend.
2. **GPU provider worker (renter PC)** — binds Ollama to a specific GPU, exposes a `/run` endpoint for queued jobs, and accepts calls only when the shared secret matches.

## Player client agent

- Location: `client_agent/agent.py`
- Config: `client_config.json` (or `CLIENT_CONFIG_PATH` env var). Set `base_url` to the rental backend URL. Environment variable `CLIENT_API_KEY` can override the stored API key.
- Commands:
  - `python -m client_agent.agent login --email you@example.com --password ...` — store a bearer token in `client_config.json`.
  - `python -m client_agent.agent create-key` — mint an API key tied to your account.
  - `python -m client_agent.agent scan --payload payload.json` — submit a scan job (payload is JSON or path).
  - `python -m client_agent.agent poll --job-id <id>` — check job status/results.
- Packaging: `pyinstaller --onefile client_agent/agent.py` yields a standalone client binary; bundle `client_config.json` alongside the executable for overrides.

## GPU provider worker

- Location: `provider_service/service.py`
- Config: `provider_config.json` (or `PROVIDER_CONFIG_PATH`). Key fields:
  - `gpu_device`: GPU index passed to `CUDA_VISIBLE_DEVICES` to pin Ollama workloads.
  - `ollama_host`: where the local Ollama daemon listens (typically `http://127.0.0.1:11434`).
  - `shared_secret`: must match the `X-Rental-Secret` header from the rental backend.
  - `default_model`: fallback Ollama model name when a job omits `model`.
- Run locally: `python -m provider_service.service` (FastAPI on `bind_host:bind_port`).
- Packaging: `pyinstaller --onefile provider_service/service.py` creates a renter-side executable. Keep `provider_config.json` in the same folder or set `PROVIDER_CONFIG_PATH`.

## Wiring the pieces

1. **Start provider worker** on the renter GPU box with `PROVIDER_SHARED_SECRET` set; ensure Ollama is installed and serving on the configured host.
2. **Set rental backend** (`rental_service/config.py` or `rental_config.json`) to point `gpu_worker_url` at the provider worker URL and include the same `X-Rental-Secret` header value via a reverse proxy or gateway.
3. **Players run the client agent** to login, create an API key, and submit scan payloads. The backend meters credits, enqueues jobs, and forwards to the provider worker; results flow back through `/api/jobs/{id}`.

This split keeps the player’s machine lightweight while the renter controls GPU allocation, Ollama runtime, and network exposure separately.
