import queue
import threading
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from sqlalchemy.orm import Session

from .config import rental_config
from .models import Job


class JobQueue:
    def __init__(self) -> None:
        self._queue: "queue.Queue[str]" = queue.Queue()

    def push(self, job_id: str) -> None:
        self._queue.put(job_id)

    def take(self, timeout: Optional[int] = None) -> Optional[str]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None


class Worker(threading.Thread):
    def __init__(self, db_factory, job_queue: JobQueue):
        super().__init__(daemon=True)
        self.db_factory = db_factory
        self.job_queue = job_queue
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            job_id = self.job_queue.take(timeout=1)
            if not job_id:
                continue
            self.process(job_id)

    def process(self, job_id: str) -> None:
        db: Session = self.db_factory()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            job.status = "RUNNING"
            job.started_at = datetime.utcnow()
            db.commit()
            try:
                job.result = perform_gpu_job(job.payload)
                job.status = "DONE"
            except Exception as exc:  # broad to persist error state
                job.error = str(exc)
                job.status = "FAILED"
            finally:
                job.finished_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()


def perform_gpu_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(rental_config.gpu_worker_url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def enqueue_job(db: Session, user_id: str, payload: Dict[str, Any]) -> Job:
    job = Job(user_id=user_id, payload=payload, status="QUEUED")
    db.add(job)
    db.flush()
    return job


def requeue_outstanding_jobs(db: Session, job_queue: JobQueue) -> None:
    queued_jobs = db.query(Job).filter(Job.status == "QUEUED").all()
    for job in queued_jobs:
        job_queue.push(job.id)
    db.commit()
