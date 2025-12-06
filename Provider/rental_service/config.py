import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = Path(
    os.environ.get("RENTAL_CONFIG_PATH", BASE_DIR / "rental_config.json")
)


@dataclass
class CreditPack:
    credits: int
    stripe_price: str


class RentalConfig:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.credit_packs: Dict[str, CreditPack] = {}
        self.gpu_worker_url = os.environ.get("GPU_WORKER_URL", "http://127.0.0.1:5001/run")
        self.gpu_worker_secret = os.environ.get("GPU_WORKER_SECRET", "")
        self.jwt_secret = os.environ.get("RENTAL_JWT_SECRET", "change-me")
        self.jwt_algorithm = "HS256"
        self.token_exp_minutes = int(os.environ.get("RENTAL_TOKEN_EXP_MINUTES", "60"))
        self.stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
        self.stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        default_db_path = BASE_DIR / "rental_service.db"
        self.database_url = os.environ.get(
            "RENTAL_DATABASE_URL", f"sqlite:///{default_db_path.as_posix()}"
        )
        self.max_worker_concurrency = int(os.environ.get("GPU_MAX_CONCURRENCY", "1"))
        self.load()

    def load(self) -> None:
        if not self.config_path.exists():
            self._seed_default_config()
        data = json.loads(self.config_path.read_text())
        packs = data.get("credit_packs", {})
        for pack_id, pack_data in packs.items():
            try:
                credits = int(pack_data["credits"])
                price = str(pack_data["stripe_price"])
            except (KeyError, ValueError, TypeError):
                continue
            self.credit_packs[pack_id] = CreditPack(credits=credits, stripe_price=price)
        self.gpu_worker_url = data.get("gpu_worker_url", self.gpu_worker_url)
        self.max_worker_concurrency = int(data.get("max_worker_concurrency", self.max_worker_concurrency))
        self.gpu_worker_secret = data.get("gpu_worker_secret", self.gpu_worker_secret)

    def _seed_default_config(self) -> None:
        default = {
            "gpu_worker_url": self.gpu_worker_url,
            "gpu_worker_secret": self.gpu_worker_secret,
            "max_worker_concurrency": self.max_worker_concurrency,
            "credit_packs": {
                "starter_10": {"credits": 10, "stripe_price": "price_replace_me"},
                "pro_50": {"credits": 50, "stripe_price": "price_replace_me"},
            },
        }
        self.config_path.write_text(json.dumps(default, indent=2))


rental_config = RentalConfig()
