import argparse
import json
from pathlib import Path
from typing import Any, Dict

import requests

from .config import client_config


class ClientAgent:
    def __init__(self, base_url: str, api_key: str, access_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.access_token = access_token

    def login(self, email: str, password: str) -> str:
        resp = requests.post(f"{self.base_url}/auth/login", json={"email": email, "password": password}, timeout=10)
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("No token returned")
        self.access_token = token
        return token

    def create_api_key(self) -> str:
        headers = self._auth_headers()
        resp = requests.post(f"{self.base_url}/auth/api-keys", headers=headers, timeout=10)
        resp.raise_for_status()
        key = resp.json().get("key")
        if not key:
            raise RuntimeError("No API key returned")
        self.api_key = key
        return key

    def submit_scan(self, payload: Dict[str, Any]) -> str:
        headers = self._api_headers()
        resp = requests.post(f"{self.base_url}/api/scan", headers=headers, json={"payload": payload}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("job_id")

    def poll_job(self, job_id: str) -> Dict[str, Any]:
        headers = self._api_headers()
        resp = requests.get(f"{self.base_url}/api/jobs/{job_id}", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _api_headers(self) -> Dict[str, str]:
        headers = self._auth_headers()
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _auth_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers



def load_payload(payload_arg: str) -> Dict[str, Any]:
    path = Path(payload_arg)
    if path.exists():
        return json.loads(path.read_text())
    return json.loads(payload_arg)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local client agent for the GPU rental backend.")
    parser.add_argument("command", choices=["login", "create-key", "scan", "poll"], help="Command to execute")
    parser.add_argument("--email", help="Email for login")
    parser.add_argument("--password", help="Password for login")
    parser.add_argument("--payload", help="JSON payload or path for scan requests")
    parser.add_argument("--job-id", help="Job ID to poll")
    parser.add_argument("--base-url", default=client_config.base_url, help="Rental backend base URL")
    parser.add_argument("--api-key", default=client_config.api_key, help="API key for requests")
    parser.add_argument("--token", default=client_config.access_token, help="Bearer token for requests")
    args = parser.parse_args()

    agent = ClientAgent(base_url=args.base_url, api_key=args.api_key, access_token=args.token)

    if args.command == "login":
        if not args.email or not args.password:
            raise SystemExit("--email and --password are required for login")
        token = agent.login(args.email, args.password)
        client_config.access_token = token
        client_config.save()
        print(token)
    elif args.command == "create-key":
        key = agent.create_api_key()
        client_config.api_key = key
        client_config.save()
        print(key)
    elif args.command == "scan":
        if not args.payload:
            raise SystemExit("--payload is required for scan")
        payload = load_payload(args.payload)
        job_id = agent.submit_scan(payload)
        print(job_id)
    elif args.command == "poll":
        if not args.job_id:
            raise SystemExit("--job-id is required for poll")
        result = agent.poll_job(args.job_id)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
