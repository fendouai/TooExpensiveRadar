import os
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db

init_db()
client = TestClient(app)


def test_ingest_text_and_list():
    payload = {
        "content": "Zapier pricing sucks for multi-step automation. Looking for a cheaper alternative.",
        "platform": "test",
    }
    res = client.post("/api/ingest/text", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["software"] == "Zapier"
    assert data["disruption_score"] > 0

    res2 = client.get("/api/opportunities")
    assert res2.status_code == 200
    assert len(res2.json()) >= 1


def test_stats():
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "avg_score" in data
    assert "top_software" in data
    assert "top_categories" in data
    assert "llm_enabled" in data


def test_seed():
    res = client.post("/api/seed")
    assert res.status_code == 200
    data = res.json()
    assert data["created"] >= 8


def test_datasources():
    res = client.get("/api/datasources")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 4


def test_llm_configs():
    res = client.get("/api/llm/configs")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 2


def test_tasks():
    res = client.get("/api/tasks")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_ingest_empty_content():
    payload = {"content": "", "platform": "test"}
    res = client.post("/api/ingest/text", json=payload)
    assert res.status_code == 400


def test_list_opportunities_with_filter():
    res = client.get("/api/opportunities?min_score=8")
    assert res.status_code == 200
    data = res.json()
    for item in data:
        assert item["disruption_score"] >= 8