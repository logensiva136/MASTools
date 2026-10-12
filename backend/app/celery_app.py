from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "mastools",
    broker=settings.broker_url,
    backend=settings.result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
