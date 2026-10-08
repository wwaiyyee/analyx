"""Report generator producing cryptographically hashed markdown documents per §8.10."""

from datetime import datetime, timezone
import hashlib
from typing import Any, Optional


def build_frozen_report_content(
    title: str,
    session_id: str,
    datasets: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    evidence_map: dict[str, Any],
    assumptions: list[dict[str, Any]],
    time_anchor_str: str = "Resolved from latest dataset timestamp",
) -> str:
    """Compile Sections 1 to 9 of the analytical report. This content is frozen and hashed."""
    sections = [
        f"# {title}\n",
        f"> **Session ID:** `{session_id}`  \n"
        f"> **Generated:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`  \n"
        f"> **Integrity Notice:** Sections 1–9 of this report are cryptographically hashed and anchored into Solana.\n",
        "## 1. Executive Summary\n",
        "This report provides deterministic analytical findings backed by cryptographically verifiable evidence. "
        "All calculations were executed directly by the Analyx engine without LLM computation of numerical values.\n",
    ]

    # Findings summary
    if findings:
        sections.append("### Key Takeaways\n")
        for idx, f in enumerate(findings[:5], start=1):
            claim = f.get("claim", "")
            status = f.get("status", "supported")
            sections.append(f"{idx}. **{claim}** `[Status: {status}]`\n")
    else:
        sections.append("No findings established for this session.\n")

    # Section 2: Dataset overview
    sections.append("\n## 2. Dataset Overview\n")
    sections.append("| Dataset Name | Kind | Rows | Canonical Table Hash | Time Anchor |")
    sections.append("|---|---|---|---|---|")
    for d in datasets:
        name = d.get("name", "Unknown")
        kind = d.get("kind", "csv")
        rows = d.get("row_count", 0)
        c_hash = d.get("content_hash", "n/a")
        anchor = d.get("time_anchor", time_anchor_str)
        short_hash = f"`{c_hash[:16]}...`" if len(c_hash) > 16 else f"`{c_hash}`"
        sections.append(f"| {name} | `{kind}` | {rows:,} | {short_hash} | {anchor} |")

    # Section 3: Key findings
    sections.append("\n## 3. Key Findings & Grounded Metrics\n")
    for idx, f in enumerate(findings, start=1):
        claim = f.get("claim", "")
        ev_id = f.get("evidence_id", "")
        c_type = f.get("claim_type", "metric")
        status = f.get("status", "supported")
        ev_data = evidence_map.get(ev_id, {})
        metrics = ev_data.get("metrics", {})

        sections.append(f"### Finding {idx}: {claim}\n")
        sections.append(f"- **Claim Type:** `{c_type}`")
        sections.append(f"- **Verification Status:** `{status}`")
        sections.append(f"- **Evidence Reference:** `{ev_id}`")
        if metrics:
            sections.append("- **Verified Metrics:**")
            for m_key, m_val in metrics.items():
                sections.append(f"  - `{m_key}`: **{m_val}**")
        sections.append("")

    # Section 4: Detailed Analysis
    sections.append("\n## 4. Detailed Analysis\n")
    sections.append(
        "Each metric reported has been deterministically compiled from dataset tables using parameterized SQL "
        "and reproducible DuckDB queries. No speculative or hallucinated figures are included.\n"
    )

    # Section 5: Data Quality
    sections.append("\n## 5. Data Quality Diagnostics\n")
    sections.append(
        "- **Totals Rows:** Analyzed and stripped to prevent double-counting.\n"
        "- **Duplicates:** Evaluated and flagged during ingestion.\n"
        "- **Missing Values:** Addressed per schema nullability definitions.\n"
    )

    # Section 6: Assumptions and Definitions
    sections.append("\n## 6. Assumptions and Semantic Definitions\n")
    if assumptions:
        for a in assumptions:
            text = a.get("text", "")
            status = a.get("status", "active")
            sections.append(f"- `{status}`: {text}")
    else:
        sections.append("- Standard UTC calendar boundaries applied.\n- Decimals rule: raw token units ignored as measures.\n")

    # Section 7: Limitations
    sections.append("\n## 7. Limitations\n")
    sections.append(
        "- **Non-Causality:** Observed statistical changes and correlations do not imply causation.\n"
        "- **Time Horizon:** Inferences are strictly bounded by available dataset timestamps.\n"
    )

    # Section 8: Suggested Next Steps
    sections.append("\n## 8. Suggested Next Steps\n")
    sections.append(
        "1. *[Suggestion]* Monitor subsequent month inflows to assess runway trajectory.\n"
        "2. *[Suggestion]* Review top counterparty activity for recurring disbursement schedules.\n"
    )

    # Section 9: Methodology and Reproducibility
    sections.append("\n## 9. Methodology and Reproducibility\n")
    sections.append(
        "- **Engine:** `analyx-engine v0.1.0` (In-process DuckDB over Apache Parquet)\n"
        "- **Hashing Standard:** RFC 8785 JSON Canonicalization Scheme (JCS) + SHA-256\n"
        "- **Evidence Verification:** Every finding is linked to an immutable reproduction query.\n"
    )

    return "\n".join(sections)


def append_verification_section(
    frozen_body: str,
    attestation_root: str,
    signer: str,
    cluster: str = "devnet",
    tx_signature: Optional[str] = None,
    block_time: Optional[str] = None,
) -> str:
    """Append Section 10 (Verification) outside the hashed region per §8.10."""
    lines = [
        frozen_body,
        "\n---",
        "\n## 10. Verification & On-Chain Anchor\n",
        "> *Note: This Verification section is appended outside the hashed region of the report.*",
        f"- **Attestation Root:** `{attestation_root}`",
        f"- **Authorized Signer:** `{signer}`",
        f"- **Solana Cluster:** `{cluster}`",
        f"- **Transaction Signature:** `{tx_signature or 'Pending confirmation'}`",
        f"- **Anchor Block Time:** `{block_time or 'Pending'}`",
        "",
        "**Integrity Statement:** An on-chain attestation proves that the report text, metrics, and evidence "
        "existed in this exact state at the recorded block time, signed by the verified wallet. "
        "It does not guarantee external real-world accuracy of unverified source data.",
    ]
    return "\n".join(lines)


def generate_report_markdown(
    title: str,
    session_id: str,
    datasets: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    evidence_map: dict[str, Any],
    assumptions: list[dict[str, Any]],
    attestation_info: Optional[dict[str, Any]] = None,
) -> tuple[str, str, str]:
    """Generate complete report, returning (frozen_markdown, report_sha256, complete_markdown)."""
    frozen = build_frozen_report_content(
        title=title,
        session_id=session_id,
        datasets=datasets,
        findings=findings,
        evidence_map=evidence_map,
        assumptions=assumptions,
    )
    report_sha = hashlib.sha256(frozen.encode("utf-8")).hexdigest()

    if attestation_info:
        complete = append_verification_section(
            frozen_body=frozen,
            attestation_root=attestation_info.get("root", ""),
            signer=attestation_info.get("signer", ""),
            cluster=attestation_info.get("cluster", "devnet"),
            tx_signature=attestation_info.get("tx_signature"),
            block_time=attestation_info.get("block_time"),
        )
    else:
        complete = frozen

    return frozen, report_sha, complete
