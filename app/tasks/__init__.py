from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from celery import Celery
from sqlmodel import Session, select

from app.database import engine, settings
from app.models import AsyncTask, TaskStatus

celery_app = Celery(
    "too_expensive_radar",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_ignore_result=False,
    result_expires=3600,
)


@celery_app.task(bind=True, name="collect_datasource")
def collect_datasource(self, source: str, config: dict | None = None, **kwargs) -> dict:
    from app.scrapers import get_scraper

    task_id = self.request.id
    with Session(engine) as session:
        task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
        if task:
            task.status = TaskStatus.RUNNING
            session.add(task)
            session.commit()

    scraper = get_scraper(source, config)

    try:
        items = scraper.scrape(**kwargs)

        with Session(engine) as session:
            task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
            if task:
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.output_data = json.dumps({"collected": len(items)})
                session.add(task)
                session.commit()

        return {"collected": len(items), "items": [
            {"platform": i.platform, "source_url": i.source_url, "author": i.author, "content": i.content}
            for i in items
        ]}
    except Exception as e:
        with Session(engine) as session:
            task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                session.add(task)
                session.commit()
        raise


@celery_app.task(bind=True, name="analyze_batch")
def analyze_batch(self, items: list[dict], use_llm: bool = False, llm_config: dict | None = None) -> dict:
    import asyncio
    from app.analyzer import analyze_text

    task_id = self.request.id
    total = len(items)

    with Session(engine) as session:
        task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
        if task:
            task.status = TaskStatus.RUNNING
            session.add(task)
            session.commit()

    llm = None
    if use_llm and llm_config:
        from app.llm import get_llm
        llm = get_llm(llm_config.get("provider", "claude"), llm_config.get("api_key", ""), llm_config.get("model", ""))

    results = []
    for i, item in enumerate(items):
        try:
            result = asyncio.run(analyze_text(item.get("content", ""), llm))
            results.append({
                "content": item.get("content", ""),
                "software": result.software,
                "category": result.category,
                "disruption_score": result.disruption_score,
            })
        except Exception:
            results.append({"content": item.get("content", ""), "software": "Unknown", "category": "Unknown", "disruption_score": 0})

        if (i + 1) % 10 == 0:
            progress = int((i + 1) / total * 100)
            with Session(engine) as session:
                task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
                if task:
                    task.progress = progress
                    session.add(task)
                    session.commit()

    with Session(engine) as session:
        task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
        if task:
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.output_data = json.dumps({"analyzed": len(results)})
            session.add(task)
            session.commit()

    return {"analyzed": len(results), "results": results}


@celery_app.task(name="update_task_status")
def update_task_status(task_id: str, status: str, progress: float = 0, error_message: str = "") -> dict:
    with Session(engine) as session:
        task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
        if task:
            task.status = status
            task.progress = progress
            if error_message:
                task.error_message = error_message
            task.updated_at = datetime.now(timezone.utc)
            session.add(task)
            session.commit()
    return {"task_id": task_id, "status": status}


def create_task(task_type: str, input_data: dict | None = None) -> AsyncTask:
    from app.models import AsyncTask

    with Session(engine) as session:
        task = AsyncTask(task_type=task_type, input_data=json.dumps(input_data or {}), status=TaskStatus.PENDING)
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def get_task_status(task_id: str) -> Optional[AsyncTask]:
    with Session(engine) as session:
        return session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()