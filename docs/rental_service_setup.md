# GPU rental service runtime guide

This guide shows how to run the paid-per-ping backend and package it as a standalone executable so it can be deployed privately alongside the Star Citizen scanner.

## Features provided
- User signup/login (JWT) and API-key authentication.
- Credit ledger with transactional usage/purchase tracking.
- Stripe Checkout session creation and webhook to grant packs.
- Paid scan endpoint that consumes one credit per job and enqueues work for the GPU worker.
- Job status polling so clients can wait for GPU results.

## Configuration
Settings are read from `rental_config.json` (auto-created on first run) and environment variables.

Key options:
- `gpu_worker_url`: HTTP endpoint the worker will call to execute the actual scan payload.
- `max_worker_concurrency`: number of concurrent worker threads to launch.
- `credit_packs`: pack IDs, credit amounts, and Stripe price IDs.
- Environment variables:
  - `RENTAL_JWT_SECRET`: secret for JWT signing (required in production).
  - `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`: Stripe credentials.
  - `RENTAL_DATABASE_URL`: defaults to SQLite `rental_service.db` in the working directory.

## Running the API locally
```bash
python -m rental_service.server
```
This starts FastAPI on `http://0.0.0.0:5002` with background workers that pick up queued jobs.

### Minimal API flow
1. `POST /auth/signup` with email/password → returns JWT.
2. `POST /auth/api-keys` with `Authorization: Bearer <token>` → returns `X-API-Key` for programmatic use.
3. `POST /payments/checkout` with `pack_id` to start Stripe Checkout.
4. Stripe webhook calls `POST /payments/webhook`; credits are added.
5. `POST /api/scan` with `X-API-Key` and a `payload` dict → returns `job_id`.
6. `GET /api/jobs/{job_id}` to poll status/result.

## Packaging as a Windows/Linux executable
Use PyInstaller to keep the code closed-source when distributing to customers:
```bash
pyinstaller --onefile --name rental_service_api rental_service/server.py
```
Place the generated executable next to your scanner assets. Ensure `rental_config.json` and `rental_service.db` are stored in a writable location for the service account.

## GPU worker expectations
The worker posts the `payload` to `gpu_worker_url`. Point this at your existing Ollama/scanner HTTP endpoint or wrap `scan_deposits.py` behind a small `/run` route. Ensure the endpoint replies with JSON; any non-2xx is recorded as a failed job.
