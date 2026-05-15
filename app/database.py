from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from urllib.parse import urlparse

import yaml
from pydantic_settings import BaseSettings
from sqlmodel import Session, SQLModel, create_engine, select

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./too_expensive.db")

def load_yaml_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}

_yaml_config = load_yaml_config()

_parsed = urlparse(DATABASE_URL)
is_sqlite = _parsed.scheme == "sqlite"

if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


class Settings(BaseSettings):
    database_url: str = "sqlite:///./too_expensive.db"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1"
    minimax_model: str = "MiniMax-Text-01"
    default_llm_provider: str = "minimax"
    default_llm_model: str = "MiniMax-Text-01"
    use_llm: bool = True

    model_config = {"env_file": ".env"}


settings = Settings()

def get_yaml_config() -> dict:
    return _yaml_config

def get_llm_config_for_provider(provider: str) -> dict:
    llm = _yaml_config.get("llm", {})
    if provider == "minimax":
        provider = "openai"
    provider_config = llm.get(provider, llm.get("openai", {}))
    return provider_config

def get_search_api_key(provider: str = "bochaai") -> str:
    apis = _yaml_config.get("search_apis", {})
    return apis.get(provider, {}).get("api_key", "")

def get_github_token() -> str:
    return _yaml_config.get("github", {}).get("token", "")

def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


async def get_session_async() -> AsyncGenerator[Session, None]:
    async with Session(engine) as session:
        yield session