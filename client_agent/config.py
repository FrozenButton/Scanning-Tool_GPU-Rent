import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


DEFAULT_CLIENT_CONFIG_PATH = Path(os.environ.get("CLIENT_CONFIG_PATH", "client_config.json"))


@dataclass
class ClientConfig:
    base_url: str = "http://127.0.0.1:5002"
    api_key: str = ""
    access_token: str = ""

    def load(self, config_path: Path = DEFAULT_CLIENT_CONFIG_PATH) -> None:
        if not config_path.exists():
            self._seed(config_path)
        data: Dict[str, Any] = json.loads(config_path.read_text())
        self.base_url = str(data.get("base_url", self.base_url))
        self.api_key = os.environ.get("CLIENT_API_KEY", str(data.get("api_key", self.api_key)))
        self.access_token = str(data.get("access_token", self.access_token))

    def save(self, config_path: Path = DEFAULT_CLIENT_CONFIG_PATH) -> None:
        data = {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "access_token": self.access_token,
        }
        config_path.write_text(json.dumps(data, indent=2))

    def _seed(self, config_path: Path) -> None:
        default = {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "access_token": self.access_token,
        }
        config_path.write_text(json.dumps(default, indent=2))


client_config = ClientConfig()
client_config.load()
