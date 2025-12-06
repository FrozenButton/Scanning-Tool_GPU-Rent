import base64
import logging
import os
from typing import Any, Dict, List, Optional

import ollama
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from .config import provider_config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

os.environ.setdefault("CUDA_VISIBLE_DEVICES", provider_config.gpu_device)
client = ollama.Client(host=provider_config.ollama_host)


class RunPayload(BaseModel):
    prompt: str
    model: Optional[str] = None
    images: Optional[List[str]] = None
    options: Optional[Dict[str, Any]] = None


def verify_secret(x_rental_secret: str = Header(default="")) -> None:
    if provider_config.shared_secret and x_rental_secret != provider_config.shared_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid shared secret")


def build_message(prompt: str, images: Optional[List[str]]) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    if images:
        for raw in images:
            try:
                base64.b64decode(raw)
            except Exception as exc:  # keep the job failure visible
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid base64 image: {exc}") from exc
            content.append({"type": "image", "image": raw})
    return [{"role": "user", "content": content}]


app = FastAPI(title="GPU Provider Worker", version="1.0.0")


@app.post("/run")
def run_job(payload: RunPayload, _: None = Depends(verify_secret)) -> Dict[str, Any]:
    model = payload.model or provider_config.default_model
    messages = build_message(payload.prompt, payload.images)
    result = client.chat(model=model, messages=messages, options=payload.options or {})
    message = result.get("message", {})
    content = message.get("content") if isinstance(message, dict) else result
    logger.info("Completed job with model=%s", model)
    return {"response": content, "model": model, "duration": result.get("total_duration")}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "model": provider_config.default_model}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("provider_service.service:app", host=provider_config.bind_host, port=provider_config.bind_port)
