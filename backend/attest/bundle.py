"""AttestationBundle constructor building cryptographic payload per §11.1."""

from datetime import datetime, timezone
from typing import Any, Optional

from backend.attest.models import (
    AttestationBundle,
    DatasetRef,
    EngineRef,
    EvidenceRef,
    ReportRef,
)


def build_attestation_bundle(
    report_id: str,
    report_sha256: str,
    datasets: list[DatasetRef | dict[str, Any]],
    evidence: list[EvidenceRef | dict[str, Any]],
    signer: str,
    created_at: Optional[str] = None,
    enclave: Optional[dict[str, Any]] = None,
) -> AttestationBundle:
    """Construct a complete, well-formed AttestationBundle ready for RFC 8785 hashing."""
    report_ref = ReportRef(id=report_id, sha256=report_sha256, format="md")

    # Normalize dataset refs and deduplicate
    parsed_datasets: list[DatasetRef] = []
    seen_hashes = set()
    for d in datasets:
        d_obj = d if isinstance(d, DatasetRef) else DatasetRef.model_validate(d)
        if d_obj.version_hash not in seen_hashes:
            seen_hashes.add(d_obj.version_hash)
            parsed_datasets.append(d_obj)

    # Normalize evidence refs
    parsed_evidence: list[EvidenceRef] = []
    seen_ev = set()
    for e in evidence:
        e_obj = e if isinstance(e, EvidenceRef) else EvidenceRef.model_validate(e)
        if e_obj.sha256 not in seen_ev:
            seen_ev.add(e_obj.sha256)
            parsed_evidence.append(e_obj)

    ts_iso = created_at or datetime.now(timezone.utc).isoformat()

    return AttestationBundle(
        version=1,
        report=report_ref,
        datasets=parsed_datasets,
        evidence=parsed_evidence,
        engine=EngineRef(name="analyx-engine", version="0.1.0", git_commit="wy"),
        enclave=enclave,
        signer=signer,
        created_at=ts_iso,
    )
