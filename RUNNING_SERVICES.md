# Running the Rental Services (Client + Provider)

This guide shows how to start each side of the two-part rental system:

- **Client** (player gaming PC) — submits scans to the rental backend.
- **Provider** (GPU renter) — runs the rental API and the Ollama worker.

Both bundles ship with Windows batch launchers and can also be started directly with Python.

## Prerequisites (both sides)
- Python 3.11+ installed and on your PATH.
- Internet access for first-time dependency installs.
- Configuration files are already in each folder (`Client/client_config.json`, `Provider/rental_config.json`, `Provider/provider_config.json`). Adjust them before first launch if needed.

---

## Client (player side)
Folder: `Client/`

### Fast start on Windows
1) Open a terminal in `Client/` (or right-click → **Open PowerShell window here**).
2) Run `run_client.bat` and follow the prompts printed in the window. The script keeps the window open if any error occurs so you can read it.

### Direct Python usage (any OS)
From inside `Client/`:
```bash
python -m client_agent.agent login --email you@example.com --password YOURPASS
python -m client_agent.agent create-key --email you@example.com --password YOURPASS
python -m client_agent.agent scan --payload path/to/payload.json --api-key YOUR_API_KEY
python -m client_agent.agent poll --job-id JOB_ID --api-key YOUR_API_KEY
```

### Key settings
- `client_config.json` controls the backend URL (`base_url`), stored token/api key paths, and default payload path.
- Override the config path with `CLIENT_CONFIG_PATH="C:\path\to\custom_client_config.json"`.

---

## Provider (GPU renter side)
Folder: `Provider/`

### Fast start on Windows
1) Open a terminal in `Provider/` (or right-click → **Open PowerShell window here**).
2) Run `run_provider.bat`. It will:
   - Install/upgrade dependencies (including `email-validator`).
   - Start the rental API (`rental_service.server`).
   - Start the Ollama worker (`provider_service.service`).
   Two windows will appear; keep both running.

### Direct Python usage (any OS)
From inside `Provider/`:
```bash
python -m rental_service.server
python -m provider_service.service
```
(Use two terminals, one per service.)

### Key settings
- `rental_config.json` — credit packs, database path, and JWT/API configuration.
- `provider_config.json` — Ollama host, GPU device ID, queue settings, and the shared secret used to authorize calls from the rental API.
- Override paths with env vars: `RENTAL_CONFIG_PATH` and `PROVIDER_CONFIG_PATH`.

---

## Packaging notes
- To build private executables, run `pyinstaller --onefile client_agent/agent.py` from `Client/` and `pyinstaller --onefile rental_service/server.py` plus `pyinstaller --onefile provider_service/service.py` from `Provider/`.
- Ensure the generated binaries can find their respective JSON config files (ship them alongside the executables or bake defaults into your build pipeline).

## Troubleshooting tips
- **Missing package errors:** Re-run the batch script; it installs dependencies automatically.
- **Cannot reach backend from client:** Confirm `base_url` in `client_config.json` points to the provider’s rental API host/port and that firewalls allow inbound traffic.
- **GPU selection issues:** Set `gpu_device` in `provider_config.json` to the correct device index recognized by Ollama on the provider machine.
- **Auth errors:** Make sure the shared secret matches between `rental_config.json` (outbound to worker) and `provider_config.json` (worker inbound validation).

