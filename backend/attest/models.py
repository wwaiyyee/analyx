"""Pydantic domain models for Solana attestation bundles and records."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class ReportRef(BaseModel):
    """Reference to the hashed analysis report."""

    id: str
    sha256: str  # Lowercase hex SHA-256 of report markdown content
    format: str = "md"


class OnchainRef(BaseModel):
    """On-chain wallet parameters for Solana-sourced datasets."""

    address: str
    from_slot: int | None = None
    to_slot: int | None = None


class DatasetRef(BaseModel):
    """Immutable dataset version reference."""

    id: str
    version_hash: str  # Canonical table hash of normalized data
    kind: str  # csv | xlsx | onchain
    onchain: OnchainRef | None = None


class EvidenceRef(BaseModel):
    """Cryptographic reference to an individual evidence item."""

    id: str
    sha256: str


class EngineRef(BaseModel):
    """Deterministic engine provenance metadata."""

    name: str = "analyx-engine"
    version: str = "0.1.0"
    git_commit: str = "HEAD"


class AttestationBundle(BaseModel):
    """Complete cryptographic payload bound into the Solana attestation root."""

    version: Literal[1] = 1
    report: ReportRef
    datasets: list[DatasetRef] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    engine: EngineRef = Field(default_factory=EngineRef)
    enclave: dict[str, Any] | None = None  # None for P0
    signer: str  # Base58 public key of signer wallet
    created_at: str  # ISO-8601 UTC string


class AttestationRecordModel(BaseModel):
    """Attestation record schema for API transport."""

    id: str
    report_id: str
    root: str  # SHA-256 attestation root
    signer: str
    cluster: Literal["devnet", "mainnet-beta"] = "devnet"
    tx_signature: str | None = None
    slot: int | None = None
    block_time: datetime | None = None
    commitment: Literal["processed", "confirmed", "finalized"] | None = None
    status: Literal["prepared", "confirmed", "failed"] = "prepared"
