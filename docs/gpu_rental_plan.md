# GPU Credit System Integration Plan

This document outlines how to adapt the existing Star Citizen Deposit Scanner into a paid, per-"ping" service backed by credits, authentication, and payment processing. The design keeps GPU usage behind a single metered entry point while staying compatible with the current Python/Flask + Tkinter stack.

## Paid ping contract

A "ping" represents one end-to-end scan invocation (including OCR + model call). All GPU-bound actions must route through a single function so billing and concurrency remain consistent:

```python
def run_paid_ping(user_id: str, payload: dict) -> dict:
    """Single paid scan execution."""
    consume_credit(user_id)
    job_id = enqueue_scan(payload, user_id=user_id)
    result = wait_for_job(job_id)
    return result
```

Key rules:
- **One credit per job**: The credit is consumed before the job starts.
- **Idempotent**: `consume_credit` must be transactional so retries do not double-charge.
- **Single entry point**: CLI, GUI button, and HTTP overlay should all call this helper.

## Authentication and user model

Use API-key auth for programmatic access and email/password for the GUI overlay. Minimal schema (SQLAlchemy):
- `users(id, email, password_hash, created_at, is_active)`
- `api_keys(id, user_id, key, active, created_at)`

Request flow:
- GUI overlay signs in via `/auth/login` (sets session/JWT).
- Programmatic clients send `Authorization: Bearer <API_KEY>` to `/api/scan`.

## Credits and transactions

Credits are stored separately from users so history is auditable:
- `user_credits(user_id, balance)` — cached balance per user.
- `transactions(id, user_id, amount, type, metadata, created_at)` where `type` is `purchase | usage | manual_adjustment`.

Helpers (all DB-transactional):
- `get_credit_balance(user_id) -> int`
- `add_credits(user_id, amount, payment_id=None)` adds a `purchase` transaction and increments `balance`.
- `consume_credit(user_id)` inserts a `usage` transaction and decrements `balance`; rejects when balance is zero.

## Payment integration (Stripe example)

### Checkout session
- Endpoint: `POST /payments/checkout`
- Input: `{ "pack_id": "starter_10" }`
- Action: Creates a Stripe Checkout Session using price IDs stored in config and attaches `user_id` metadata.
- Response: Checkout URL for the frontend to redirect.

### Webhook handler
- Endpoint: `POST /payments/webhook`
- Validates Stripe signature using `STRIPE_WEBHOOK_SECRET`.
- On `checkout.session.completed`, reads `user_id` + `pack_id` from metadata, determines credit quantity, then calls `add_credits(user_id, pack_credits, payment_id=session.id)`.

### Packs configuration
Define packs in `config.json` (or `.env`) to avoid hard-coding:
```json
{
  "credit_packs": {
    "starter_10": { "credits": 10, "stripe_price": "price_123" },
    "pro_50": { "credits": 50, "stripe_price": "price_456" }
  }
}
```

## Paid scan API surface

- `POST /api/scan` — authenticated. Body is the existing scan payload. Steps:
  1) `consume_credit(user.id)`
  2) `enqueue_scan(payload, user_id=user.id)`
  3) Return `job_id`.
- `GET /api/jobs/{job_id}` — returns `{ status, result }` for polling.
- `GET /me/credits` — returns current balance and last N transactions.

## Queueing and worker

Introduce a lightweight queue to shield the 3090 worker:
- **Broker**: Redis (preferred) or in-process `queue.Queue` for MVP.
- **Producer**: API server enqueues jobs with payload and `user_id`.
- **Worker**: Long-running process on the GPU box consuming the queue and invoking the existing scan routine or remote Ollama call.
- **Statuses**: `QUEUED → RUNNING → DONE/FAILED` stored in a `jobs` table keyed by `job_id`.

Minimal worker loop:
```python
def worker():
    while True:
        job = queue.take()
        update_status(job.id, "RUNNING")
        try:
            job.result = perform_scan(job.payload)
            update_status(job.id, "DONE", result=job.result)
        except Exception as exc:
            update_status(job.id, "FAILED", error=str(exc))
```

## Rate limiting and abuse protection

- Per-user limit: e.g., `N` scan requests per minute enforced via Redis counters or `slowapi` middleware.
- Payload validation: Max image size / token count before enqueueing.
- Concurrency guard: Worker only runs `K` concurrent GPU jobs to keep VRAM stable.

## Admin controls

Expose `/admin` (protected) for the GPU owner:
- View user balances, recent transactions, and job counts.
- Manually adjust credits (`manual_adjustment` transaction).
- Disable a user or API key.
- Pause job ingestion when the GPU is needed for other tasks.

## Failure/consistency notes

- Wrap `consume_credit` and job creation in one DB transaction so credits are only deducted when a job ID is issued.
- On worker crash, resume by retrying `QUEUED` jobs; do not re-consume credits.
- Emit structured logs (JSON) for each transaction and job state change for later reporting.

## MVP checklist

1. FastAPI/Flask routes for auth, credits, and paid scan endpoint.
2. SQLAlchemy models and migrations for users, credits, transactions, and jobs.
3. Stripe Checkout session creator + webhook handler wired to `add_credits`.
4. Queue-backed worker on the GPU host calling the existing scan function/HTTP endpoint.
5. Rate limiting and payload validation at the API edge.
6. Admin page/API for balances and job oversight.
