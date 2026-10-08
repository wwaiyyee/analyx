"""SQLModel database entity tables for Analyx."""

from datetime import datetime, timezone
from typing import Any, Optional
from sqlmodel import Field, SQLModel

from backend.core.ids import generate_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(SQLModel, table=True):
    """User workspace tied to a Solana wallet address."""

    __tablename__ = "workspaces"

    id: str = Field(default_factory=lambda: generate_id("wk"), primary_key=True)
    wallet_address: str = Field(index=True, unique=True)
    name: str = Field(default="Default Workspace")
    created_at: datetime = Field(default_factory=utc_now)


class Dataset(SQLModel, table=True):
    """Logical dataset container."""

    __tablename__ = "datasets"

    id: str = Field(default_factory=lambda: generate_id("ds"), primary_key=True)
    workspace_id: str = Field(foreign_key="workspaces.id", index=True)
    name: str
    kind: str = Field(default="csv", index=True)  # csv | xlsx | onchain
    created_at: datetime = Field(default_factory=utc_now)


class DatasetVersion(SQLModel, table=True):
    """Immutable snapshot of a dataset with Parquet file and canonical table hash."""

    __tablename__ = "dataset_versions"

    id: str = Field(default_factory=lambda: generate_id("dv"), primary_key=True)
    dataset_id: str = Field(foreign_key="datasets.id", index=True)
    version_num: int = Field(default=1)
    content_hash: str = Field(index=True)  # SHA-256 canonical_table_hash
    parquet_path: str
    row_count: int = Field(default=0)
    col_count: int = Field(default=0)
    time_anchor: Optional[datetime] = None
    columns_json: str = Field(default="[]")  # List of ColumnSchema
    transformations_json: str = Field(default="[]")  # List of TransformationStep
    quality_report_json: str = Field(default="{}")  # QualityReport
    created_at: datetime = Field(default_factory=utc_now)


class DataDictionaryEntry(SQLModel, table=True):
    """Semantic annotations and roles per dataset column."""

    __tablename__ = "data_dictionary_entries"

    id: str = Field(default_factory=lambda: generate_id("dd"), primary_key=True)
    dataset_id: str = Field(foreign_key="datasets.id", index=True)
    column_name: str = Field(index=True)
    display_name: Optional[str] = None
    description: Optional[str] = None
    role: str = Field(default="dimension")  # identifier | timestamp | metric | dimension | ignored
    unit: Optional[str] = None
    is_pii: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AnalysisSession(SQLModel, table=True):
    """Interactive conversational analysis session."""

    __tablename__ = "analysis_sessions"

    id: str = Field(default_factory=lambda: generate_id("ses"), primary_key=True)
    workspace_id: str = Field(foreign_key="workspaces.id", index=True)
    title: str = Field(default="New Analysis")
    time_anchor: Optional[datetime] = None
    messages_json: str = Field(default="[]")  # Conversation turns
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Evidence(SQLModel, table=True):
    """Deterministic computational evidence record produced by the engine."""

    __tablename__ = "evidence"

    id: str = Field(default_factory=lambda: generate_id("ev"), primary_key=True)
    session_id: str = Field(foreign_key="analysis_sessions.id", index=True)
    sha256: str = Field(index=True)  # Hash of canonical evidence representation
    spec_json: str  # AnalysisSpec JSON
    result_hash: str  # SHA-256 of result rows
    metrics_json: str = Field(default="{}")  # Computed metrics map
    row_refs_json: str = Field(default="[]")  # Row references
    explorer_urls_json: str = Field(default="[]")  # Solana explorer links
    reproduction_json: str = Field(default="{}")  # SQL query, params, engine version
    created_at: datetime = Field(default_factory=utc_now)


class Finding(SQLModel, table=True):
    """Individual analytical claim verified against evidence."""

    __tablename__ = "findings"

    id: str = Field(default_factory=lambda: generate_id("fd"), primary_key=True)
    session_id: str = Field(foreign_key="analysis_sessions.id", index=True)
    evidence_id: str = Field(foreign_key="evidence.id", index=True)
    claim: str
    claim_type: str = Field(default="metric")  # metric | trend | comparison | anomaly | sufficiency_caveat
    status: str = Field(default="supported")  # supported | partially_supported | insufficient | not_applicable
    numbers_grounded: bool = Field(default=True)
    language_grounded: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)


class Assumption(SQLModel, table=True):
    """Explicit assumption tracked across analysis turns."""

    __tablename__ = "assumptions"

    id: str = Field(default_factory=lambda: generate_id("as"), primary_key=True)
    session_id: str = Field(foreign_key="analysis_sessions.id", index=True)
    text: str
    source: str = Field(default="heuristic")  # heuristic | user | llm
    status: str = Field(default="active")  # active | overridden | confirmed
    created_at: datetime = Field(default_factory=utc_now)


class Chart(SQLModel, table=True):
    """Visualization spec paired with a finding and evidence."""

    __tablename__ = "charts"

    id: str = Field(default_factory=lambda: generate_id("ch"), primary_key=True)
    session_id: str = Field(foreign_key="analysis_sessions.id", index=True)
    finding_id: Optional[str] = Field(default=None, foreign_key="findings.id")
    vega_spec_json: str
    chart_type: str = Field(default="trend")  # trend | compare | bridge | composition
    title: str = Field(default="")
    created_at: datetime = Field(default_factory=utc_now)


class Report(SQLModel, table=True):
    """Generated markdown report with frozen-region hash tracking."""

    __tablename__ = "reports"

    id: str = Field(default_factory=lambda: generate_id("rp"), primary_key=True)
    workspace_id: str = Field(foreign_key="workspaces.id", index=True)
    session_id: str = Field(foreign_key="analysis_sessions.id", index=True)
    title: str = Field(default="Analysis Report")
    markdown_content: str
    sha256: str = Field(index=True)  # SHA-256 of markdown_content
    frozen_region_hashes_json: str = Field(default="[]")
    created_at: datetime = Field(default_factory=utc_now)


class AttestationRecord(SQLModel, table=True):
    """On-chain Solana Memo attestation record."""

    __tablename__ = "attestation_records"

    id: str = Field(default_factory=lambda: generate_id("at"), primary_key=True)
    report_id: str = Field(foreign_key="reports.id", index=True)
    root: str = Field(index=True)  # SHA-256 attestation root
    signer: str = Field(index=True)  # Wallet base58 public key
    cluster: str = Field(default="devnet")  # devnet | mainnet-beta
    tx_signature: Optional[str] = Field(default=None, index=True)
    slot: Optional[int] = None
    block_time: Optional[datetime] = None
    commitment: Optional[str] = None  # processed | confirmed | finalized
    status: str = Field(default="prepared")  # prepared | confirmed | failed
    bundle_json: str = Field(default="{}")  # Complete AttestationBundle JSON
    created_at: datetime = Field(default_factory=utc_now)


class Job(SQLModel, table=True):
    """Background asynchronous processing task."""

    __tablename__ = "jobs"

    id: str = Field(default_factory=lambda: generate_id("job"), primary_key=True)
    workspace_id: Optional[str] = Field(default=None, foreign_key="workspaces.id", index=True)
    kind: str = Field(index=True)  # ingest | sync_onchain | profile | analysis
    status: str = Field(default="queued", index=True)  # queued | running | completed | failed
    progress: int = Field(default=0)  # 0 to 100
    error: Optional[str] = None
    result_json: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Nonce(SQLModel, table=True):
    """One-time sign-in challenge nonce for wallet authentication."""

    __tablename__ = "nonces"

    id: str = Field(default_factory=lambda: generate_id("nc"), primary_key=True)
    wallet_address: str = Field(index=True)
    nonce: str = Field(unique=True, index=True)
    issued_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    used: bool = Field(default=False)
