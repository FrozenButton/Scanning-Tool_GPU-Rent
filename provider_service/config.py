import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


DEFAULT_PROVIDER_CONFIG_PATH = Path(os.environ.get("PROVIDER_CONFIG_PATH", "provider_config.json"))


@dataclass
class ProviderConfig:
    bind_host: str = "0.0.0.0"
    bind_port: int = 5001
    ollama_host: str = "http://127.0.0.1:11434"
    gpu_device: str = "0"
    default_model: str = "qwen2.5vl:3b"
    shared_secret: str = ""

    def load(self, config_path: Path = DEFAULT_PROVIDER_CONFIG_PATH) -> None:
        if not config_path.exists():
            self._seed(config_path)
        data: Dict[str, Any] = json.loads(config_path.read_text())
        self.bind_host = str(data.get("bind_host", self.bind_host))
        self.bind_port = int(data.get("bind_port", self.bind_port))
        self.ollama_host = str(data.get("ollama_host", self.ollama_host))
        self.gpu_device = str(data.get("gpu_device", self.gpu_device))
        self.default_model = str(data.get("default_model", self.default_model))
        self.shared_secret = os.environ.get("PROVIDER_SHARED_SECRET", str(data.get("shared_secret", self.shared_secret)))

    def _seed(self, config_path: Path) -> None:
        default = {
            "bind_host": self.bind_host,
            "bind_port": self.bind_port,
            "ollama_host": self.ollama_host,
            "gpu_device": self.gpu_device,
            "default_model": self.default_model,
            "shared_secret": self.shared_secret,
        }
        config_path.write_text(json.dumps(default, indent=2))


provider_config = ProviderConfig()
provider_config.load()
