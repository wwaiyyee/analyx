"""Dataset management endpoints: upload, on-chain sync, profiling, and dictionary CRUD."""

import json
import os
from typing import Annotated, Any, Optional

import base58
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
import pandas as pd
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.api.auth import get_current_workspace
from backend.config import settings
from backend.core.ids import generate_id
from backend.db.models import DataDictionaryEntry, Dataset, DatasetVersion, Job, Workspace
from backend.db.session import get_session
from backend.ingest.normalize import normalize_dataset
from backend.onchain.normalize_transfers import normalize_onchain_transfers
from backend.onchain.rpc_source import RpcSource
from backend.profile.profiler import profile_dataset
from backend.semantic.dictionary import propose_dictionary

router = APIRouter(prefix="/datasets", tags=["datasets"])


class OnchainSyncRequest(BaseModel):
    address: str = Field(..., description="Solana account or treasury public key")
    cluster: str = Field(default="devnet", description="devnet or mainnet-beta")
    max_signatures: Optional[int] = Field(default=1000, description="Max signatures to ingest")


class DictionaryUpdateEntry(BaseModel):
    column_name: str
    role: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    is_pii: Optional[bool] = None


class DictionaryUpdateRequest(BaseModel):
    entries: list[DictionaryUpdateEntry]


class TransformationApprovalRequest(BaseModel):
    approved: bool = True


def _run_onchain_sync(
    job_id: str,
    workspace_id: str,
    address: str,
    cluster: str,
    max_signatures: int,
    session: Session,
) -> None:
    """Background task to sync and normalize on-chain transactions."""
    job = session.get(Job, job_id)
    if not job:
        return

    try:
        job.status = "running"
        job.progress = 10
        session.add(job)
        session.commit()

        # Ingest transactions
        source = RpcSource(cluster=cluster, rpc_url=settings.solana_rpc_url)
        batch = source.fetch_transactions(address, max_signatures=max_signatures)

        job.progress = 50
        session.add(job)
        session.commit()

        # Normalize transfers
        df = normalize_onchain_transfers(batch.raw_transactions, wallet_address=address)

        # Output parquet
        dataset_id = generate_id("ds")
        version_id = generate_id("dv")
        out_dir = os.path.join(settings.data_dir, "datasets", dataset_id)
        os.makedirs(out_dir, exist_ok=True)
        parquet_path = os.path.join(out_dir, "data.parquet")
        df.to_parquet(parquet_path, engine="pyarrow", index=False)

        from backend.core.hashing import canonical_table_hash
        content_hash = canonical_table_hash(parquet_path)

        # Profile and dictionary
        prof = profile_dataset(df)
        dict_entries = propose_dictionary(df, dataset_version_id=version_id)

        dataset = Dataset(
            id=dataset_id,
            workspace_id=workspace_id,
            name=f"Solana Treasury ({address[:4]}...{address[-4:]})",
            kind="onchain",
        )
        session.add(dataset)

        version = DatasetVersion(
            id=version_id,
            dataset_id=dataset_id,
            version_num=1,
            content_hash=content_hash,
            parquet_path=parquet_path,
            row_count=len(df),
            col_count=len(df.columns),
            time_anchor=None,
            columns_json=json.dumps(list(df.columns)),
            transformations_json="[]",
            quality_report_json=json.dumps({"stats": prof}),
        )
        session.add(version)

        for de in dict_entries:
            role_val = de.get("role", "dimension")
            entry = DataDictionaryEntry(
                dataset_id=dataset_id,
                column_name=de["column"],
                description=de.get("description"),
                role=role_val,
                unit=de.get("unit"),
                is_pii=de.get("pii") != "none",
            )
            session.add(entry)

        job.status = "completed"
        job.progress = 100
        job.result_json = json.dumps({"dataset_id": dataset_id, "version_id": version_id})
        session.add(job)
        session.commit()

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        session.add(job)
        session.commit()


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Upload CSV or XLSX dataset, parse, clean, profile, and propose dictionary."""
    filename = file.filename or "upload.csv"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".csv", ".tsv", ".xlsx", ".xls"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": f"Unsupported file extension: {ext}. Expected CSV or XLSX.",
                }
            },
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "EMPTY_FILE", "message": "Uploaded file is empty"}},
        )

    dataset_id = generate_id("ds")
    version_id = generate_id("dv")
    out_dir = os.path.join(settings.data_dir, "datasets", dataset_id)

    try:
        norm_result = normalize_dataset(
            source=content,
            filename=filename,
            output_dir=out_dir,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INGEST_ERROR",
                    "message": f"Failed to normalize dataset: {exc}",
                }
            },
        ) from exc

    # Load dataframe to profile and propose dictionary
    df = pd.read_parquet(norm_result.parquet_path)
    profile = profile_dataset(df)
    dictionary_proposals = propose_dictionary(df, dataset_version_id=version_id)

    # Persist in DB
    dataset = Dataset(
        id=dataset_id,
        workspace_id=workspace.id,
        name=filename,
        kind="xlsx" if ext in [".xlsx", ".xls"] else "csv",
    )
    session.add(dataset)

    columns_data = [c.model_dump() for c in norm_result.columns]
    transforms_data = [t.model_dump() for t in norm_result.transformations]
    quality_data = norm_result.quality_report.model_dump()

    version = DatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        version_num=1,
        content_hash=norm_result.canonical_table_hash,
        parquet_path=norm_result.parquet_path,
        row_count=norm_result.row_count,
        col_count=norm_result.col_count,
        time_anchor=norm_result.time_anchor,
        columns_json=json.dumps(columns_data, default=str),
        transformations_json=json.dumps(transforms_data, default=str),
        quality_report_json=json.dumps(quality_data, default=str),
    )
    session.add(version)

    for prop in dictionary_proposals:
        entry = DataDictionaryEntry(
            dataset_id=dataset_id,
            column_name=prop["column"],
            description=prop.get("description"),
            role=prop.get("role", "dimension"),
            unit=prop.get("unit"),
            is_pii=prop.get("pii") != "none",
        )
        session.add(entry)

    session.commit()
    session.refresh(dataset)
    session.refresh(version)

    return {
        "dataset": dataset.model_dump(),
        "version": version.model_dump(),
        "profile": profile,
        "dictionary_proposal": dictionary_proposals,
        "transformations": transforms_data,
    }


@router.post("/onchain")
def sync_onchain_dataset(
    req: OnchainSyncRequest,
    bg_tasks: BackgroundTasks,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Trigger background ingest job for a Solana wallet/treasury."""
    # Validate address
    try:
        raw = base58.b58decode(req.address)
        if len(raw) != 32:
            raise ValueError()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_ADDRESS",
                    "message": "Invalid Solana address (must be 32-byte base58)",
                }
            },
        )

    job = Job(
        workspace_id=workspace.id,
        kind="sync_onchain",
        status="queued",
        progress=0,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    max_sigs = req.max_signatures or settings.onchain_max_signatures
    bg_tasks.add_task(
        _run_onchain_sync,
        job_id=job.id,
        workspace_id=workspace.id,
        address=req.address,
        cluster=req.cluster,
        max_signatures=max_sigs,
        session=session,
    )

    return {"job_id": job.id}


@router.get("")
def list_datasets(
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """List datasets in current workspace."""
    stmt = select(Dataset).where(Dataset.workspace_id == workspace.id)
    datasets = session.exec(stmt).all()
    return [d.model_dump() for d in datasets]


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get dataset and version history."""
    dataset = session.get(Dataset, dataset_id)
    if not dataset or dataset.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Dataset {dataset_id} not found"}},
        )

    v_stmt = (
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_num.desc())
    )
    versions = session.exec(v_stmt).all()

    return {
        "dataset": dataset.model_dump(),
        "versions": [v.model_dump() for v in versions],
    }


@router.get("/{dataset_id}/profile")
def get_dataset_profile(
    dataset_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get profile and quality report for the latest version of dataset."""
    dataset = session.get(Dataset, dataset_id)
    if not dataset or dataset.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Dataset {dataset_id} not found"}},
        )

    v_stmt = (
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_num.desc())
    )
    latest_version = session.exec(v_stmt).first()
    if not latest_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "No dataset version found"}},
        )

    # Compute profile from parquet
    try:
        df = pd.read_parquet(latest_version.parquet_path)
        profile = profile_dataset(df)
    except Exception:
        profile = {}

    quality_report = json.loads(latest_version.quality_report_json)

    return {
        "dataset_id": dataset_id,
        "version_id": latest_version.id,
        "profile": profile,
        "quality_report": quality_report,
    }


@router.get("/{dataset_id}/dictionary")
def get_dataset_dictionary(
    dataset_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get current semantic data dictionary entries."""
    dataset = session.get(Dataset, dataset_id)
    if not dataset or dataset.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Dataset {dataset_id} not found"}},
        )

    stmt = select(DataDictionaryEntry).where(DataDictionaryEntry.dataset_id == dataset_id)
    entries = session.exec(stmt).all()
    return [e.model_dump() for e in entries]


@router.put("/{dataset_id}/dictionary")
def update_dataset_dictionary(
    dataset_id: str,
    req: DictionaryUpdateRequest,
    workspace: Workspace = Depends(get_current_workspace),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Update semantic roles and annotations in data dictionary."""
    dataset = session.get(Dataset, dataset_id)
    if not dataset or dataset.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Dataset {dataset_id} not found"}},
        )

    stmt = select(DataDictionaryEntry).where(DataDictionaryEntry.dataset_id == dataset_id)
    existing_entries = {e.column_name: e for e in session.exec(stmt).all()}

    for item in req.entries:
        if item.column_name in existing_entries:
            entry = existing_entries[item.column_name]
            if item.role is not None:
                entry.role = item.role
            if item.display_name is not None:
                entry.display_name = item.display_name
            if item.description is not None:
                entry.description = item.description
            if item.unit is not None:
                entry.unit = item.unit
            if item.is_pii is not None:
                entry.is_pii = item.is_pii
            session.add(entry)

    session.commit()

    # Re-fetch updated
    stmt = select(DataDictionaryEntry).where(DataDictionaryEntry.dataset_id == dataset_id)
    updated_entries = session.exec(stmt).all()
    return [e.model_dump() for e in updated_entries]
