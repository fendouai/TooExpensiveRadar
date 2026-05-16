from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    pass


def _utcnow():
    return datetime.now(timezone.utc)


class DataSource(str, Enum):
    REDDIT = "reddit"
    G2 = "g2"
    CAPTERRA = "capterra"
    HACKER_NEWS = "hackernews"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    RSS = "rss"
    AI_FILTER = "ai_filter"
    MANUAL = "manual"
    CSV = "csv"


class SoftwareCategory(str, Enum):
    CRM = "CRM / Marketing Automation"
    PROPOSAL = "Proposal / Document"
    AUTOMATION = "Automation"
    PROJECT_MANAGEMENT = "Project Management"
    CUSTOMER_SUPPORT = "Customer Support"
    KNOWLEDGE_MANAGEMENT = "Knowledge Management"
    INTERNAL_TOOLS = "Internal Tools / Database"
    E_SIGNATURE = "E-signature"
    HR = "HR Workflow"
    UNKNOWN = "Unknown"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LLMProvider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"


class RawSignal(SQLModel, table=True):
    __tablename__ = "raw_signals"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(default=DataSource.MANUAL, index=True)
    platform: str = Field(default="manual")
    source_url: str = Field(default="", index=True)
    author: str = Field(default="")
    author_metadata: Optional[str] = None
    content: str = Field(index=True)
    raw_content: str = ""
    collected_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)


class Complaint(SQLModel, table=True):
    __tablename__ = "complaints"

    id: Optional[int] = Field(default=None, primary_key=True)
    raw_signal_id: Optional[int] = Field(default=None, foreign_key="raw_signals.id", index=True)
    complaint_type: str = Field(default="", index=True)
    pricing_signal: bool = Field(default=False, index=True)
    bloat_signal: bool = Field(default=False)
    smb_signal: bool = Field(default=False)
    emotion_score: float = Field(default=0)
    software_name: str = Field(default="", index=True)
    workflow_keywords: str = ""
    detected_keywords: str = ""
    sentiment_polarity: float = Field(default=0)
    created_at: datetime = Field(default_factory=_utcnow)


class WorkflowGraph(SQLModel, table=True):
    __tablename__ = "workflow_graphs"

    id: Optional[int] = Field(default=None, primary_key=True)
    complaint_id: Optional[int] = Field(default=None, foreign_key="complaints.id", index=True)
    workflow_name: str = Field(default="Unknown")
    workflow_steps: str = ""
    manual_handoffs: str = ""
    software_dependencies: str = ""
    workflow_complexity: float = Field(default=0)
    frequency_hint: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class Opportunity(SQLModel, table=True):
    __tablename__ = "opportunities"

    id: Optional[int] = Field(default=None, primary_key=True)
    complaint_id: Optional[int] = Field(default=None, foreign_key="complaints.id", index=True)
    workflow_graph_id: Optional[int] = Field(default=None, foreign_key="workflow_graphs.id")
    software: str = Field(default="Unknown", index=True)
    category: str = Field(default=SoftwareCategory.UNKNOWN, index=True)
    complaint_summary: str = ""
    actual_workflow: str = Field(default="")
    ai_native_replacement: str = Field(default="")
    existing_price: str = ""
    possible_price: str = ""
    pricing_pain_score: float = Field(default=0)
    feature_bloat_score: float = Field(default=0)
    smb_overkill_score: float = Field(default=0)
    ai_compression_score: float = Field(default=0)
    workflow_simplicity_score: float = Field(default=0)
    replacement_feasibility_score: float = Field(default=0)
    disruption_score: float = Field(default=0, index=True)
    evidence: str = ""
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class AlternativeCandidate(SQLModel, table=True):
    __tablename__ = "alternative_candidates"

    id: Optional[int] = Field(default=None, primary_key=True)
    complaint_id: Optional[int] = Field(default=None, foreign_key="complaints.id", index=True)
    original_software: str = Field(default="", index=True)
    alternative_name: str = Field(default="", index=True)
    pricing_tier: str = ""
    affiliate_support: str = ""
    affiliate_url: str = ""
    price_advantage: str = ""
    verification_source: str = ""
    verification_details: str = ""
    disruption_score_boost: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=_utcnow)


class AlternativeCandidateRead(SQLModel):
    id: int
    original_software: str
    alternative_name: str
    pricing_tier: str
    affiliate_support: str
    affiliate_url: str
    price_advantage: str
    verification_source: str
    verification_details: str
    disruption_score_boost: float
    created_at: datetime


class BusinessLayer(SQLModel, table=True):
    __tablename__ = "business_layers"

    id: Optional[int] = Field(default=None, primary_key=True)
    opportunity_id: Optional[int] = Field(default=None, foreign_key="opportunities.id", index=True)
    possible_saas_name: str = ""
    pricing_gap: str = ""
    estimated_arpu: float = Field(default=0)
    go_to_market: str = ""
    target_segment: str = ""
    key_differentiator: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class DataSourceConfig(SQLModel, table=True):
    __tablename__ = "data_source_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(default=DataSource.MANUAL, unique=True, index=True)
    enabled: bool = Field(default=False)
    config: str = ""
    last_collected_at: Optional[datetime] = None
    total_collected: int = Field(default=0)
    success_count: int = Field(default=0)
    error_count: int = Field(default=0)
    updated_at: datetime = Field(default_factory=_utcnow)


class LLMConfig(SQLModel, table=True):
    __tablename__ = "llm_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(default=LLMProvider.CLAUDE, unique=True, index=True)
    api_key: str = ""
    model: str = Field(default="claude-3-5-sonnet-20241023")
    base_url: str = ""
    enabled: bool = Field(default=False)
    is_default: bool = Field(default=False)
    config: str = ""
    updated_at: datetime = Field(default_factory=_utcnow)


class AsyncTask(SQLModel, table=True):
    __tablename__ = "async_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(default="", unique=True, index=True)
    task_type: str = Field(default="", index=True)
    status: str = Field(default=TaskStatus.PENDING, index=True)
    progress: float = Field(default=0)
    input_data: str = ""
    output_data: str = ""
    error_message: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TextIngestRequest(SQLModel):
    content: str
    platform: str = "manual"
    source_url: str = ""
    author: str = ""


class OpportunityRead(SQLModel):
    id: int
    software: str
    category: str
    complaint_summary: str
    actual_workflow: str
    ai_native_replacement: str
    existing_price: str
    possible_price: str
    pricing_pain_score: float
    feature_bloat_score: float
    smb_overkill_score: float
    ai_compression_score: float
    workflow_simplicity_score: float
    replacement_feasibility_score: float
    disruption_score: float
    evidence: str
    created_at: datetime


class DataSourceConfigRead(SQLModel):
    id: int
    source: str
    enabled: bool
    last_collected_at: Optional[datetime]
    total_collected: int
    success_count: int
    error_count: int


class LLMConfigRead(SQLModel):
    id: int
    provider: str
    model: str
    base_url: str
    enabled: bool
    is_default: bool


class AsyncTaskRead(SQLModel):
    id: int
    task_id: str
    task_type: str
    status: str
    progress: float
    error_message: str
    created_at: datetime


class StatsResponse(SQLModel):
    total: int
    avg_score: float
    top_software: list
    top_categories: list
    total_complaints: int
    total_datasources: int
    llm_enabled: bool