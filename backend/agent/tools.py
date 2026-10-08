"""Tool definitions and dispatcher for the agent orchestrator per §8.7."""

import json
from typing import Any, Callable

from sqlmodel import Session, select

from backend.db.models import (
    AnalysisSession,
    DataDictionaryEntry,
    Dataset,
    DatasetVersion,
    Evidence,
    Finding,
    Report,
)
from backend.engine.execute import execute_analysis
from backend.engine.models import AnalysisSpec
from backend.engine.sufficiency import check_sufficiency
from backend.engine.sufficiency_models import Requirement
from backend.semantic.metrics import load_metric_pack
from backend.validate.evidence_status import evaluate_evidence_status
from backend.validate.language_lint import lint_language
from backend.validate.number_lint import lint_numbers

# JSON Schemas for tools exposed to the LLM
TOOL_DEFINITIONS = [
    {
        "name": "list_datasets",
        "description": "List all datasets and versions available in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_profile",
        "description": "Get column statistics, quality diagnostics, and summary for a dataset version. Never returns raw rows.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_version_id": {"type": "string", "description": "The dataset version ID (e.g. dv_...)"},
            },
            "required": ["dataset_version_id"],
        },
    },
    {
        "name": "get_dictionary",
        "description": "Get confirmed data dictionary columns and semantic roles for a dataset.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset ID (e.g. ds_...)"},
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "check_sufficiency",
        "description": "Check if available data is sufficient to answer an analytical question before querying.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_version_id": {"type": "string"},
                "requirements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {
                                "type": "string",
                                "enum": ["column_presence", "coverage", "granularity", "time_span", "sample_size"],
                            },
                            "target": {"type": "string"},
                            "min_value": {"type": "number"},
                        },
                        "required": ["kind", "target"],
                    },
                },
            },
            "required": ["dataset_version_id", "requirements"],
        },
    },
    {
        "name": "run_analysis",
        "description": "Execute a deterministic analysis spec. Returns evidence ID and aggregated metrics (never raw rows).",
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": "Valid AnalysisSpec JSON with dataset_version_ids, metrics, time, and filters",
                },
            },
            "required": ["spec"],
        },
    },
    {
        "name": "propose_finding",
        "description": "Submit an analytical claim backed by evidence to be validated by the engine and validators.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "The analytical claim sentence"},
                "claim_type": {
                    "type": "string",
                    "enum": ["metric", "trend", "comparison", "anomaly", "sufficiency_caveat"],
                },
                "evidence_id": {"type": "string", "description": "Backing Evidence ID"},
            },
            "required": ["claim", "evidence_id"],
        },
    },
    {
        "name": "create_chart",
        "description": "Generate a Vega-Lite visualization spec paired with a validated finding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "finding_id": {"type": "string"},
                "intent": {
                    "type": "string",
                    "enum": ["trend", "compare", "bridge", "composition"],
                },
            },
            "required": ["finding_id", "intent"],
        },
    },
    {
        "name": "ask_user",
        "description": "Ask the user a clarifying question or request missing information with choices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "question": {"type": "string"},
                            "choices": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id", "question", "choices"],
                    },
                },
            },
            "required": ["questions"],
        },
    },
    {
        "name": "build_report",
        "description": "Compile verified analytical findings into a formal report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
            },
            "required": [],
        },
    },
]


class ToolExecutor:
    """Executes agent tool calls securely against the database and deterministic engine."""

    def __init__(self, workspace_id: str, session_id: str, db_session: Session) -> None:
        self.workspace_id = workspace_id
        self.session_id = session_id
        self.db = db_session

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool call by name with validated parameters."""
        method_name = f"_tool_{tool_name}"
        method = getattr(self, method_name, None)
        if not method:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return method(arguments)
        except Exception as exc:
            return {"error": f"Tool execution failed: {str(exc)}"}

    def _tool_list_datasets(self, args: dict[str, Any]) -> dict[str, Any]:
        stmt = select(Dataset).where(Dataset.workspace_id == self.workspace_id)
        datasets = self.db.exec(stmt).all()
        results = []
        for d in datasets:
            v_stmt = (
                select(DatasetVersion)
                .where(DatasetVersion.dataset_id == d.id)
                .order_by(DatasetVersion.version_num.desc())
            )
            versions = self.db.exec(v_stmt).all()
            results.append({
                "dataset_id": d.id,
                "name": d.name,
                "kind": d.kind,
                "versions": [{"id": v.id, "version_num": v.version_num, "row_count": v.row_count} for v in versions],
            })
        return {"datasets": results}

    def _tool_get_profile(self, args: dict[str, Any]) -> dict[str, Any]:
        v_id = args.get("dataset_version_id", "")
        ver = self.db.get(DatasetVersion, v_id)
        if not ver:
            return {"error": f"Version {v_id} not found"}
        quality = json.loads(ver.quality_report_json)
        return {
            "dataset_version_id": ver.id,
            "row_count": ver.row_count,
            "col_count": ver.col_count,
            "time_anchor": ver.time_anchor.isoformat() if ver.time_anchor else None,
            "quality_report": quality,
        }

    def _tool_get_dictionary(self, args: dict[str, Any]) -> dict[str, Any]:
        d_id = args.get("dataset_id", "")
        stmt = select(DataDictionaryEntry).where(DataDictionaryEntry.dataset_id == d_id)
        entries = self.db.exec(stmt).all()
        return {
            "dataset_id": d_id,
            "columns": [
                {
                    "name": e.column_name,
                    "role": e.role,
                    "display_name": e.display_name,
                    "unit": e.unit,
                    "is_pii": e.is_pii,
                }
                for e in entries
            ],
        }

    def _tool_check_sufficiency(self, args: dict[str, Any]) -> dict[str, Any]:
        v_id = args.get("dataset_version_id", "")
        reqs = [Requirement.model_validate(r) for r in args.get("requirements", [])]
        ver = self.db.get(DatasetVersion, v_id)
        if not ver:
            return {"verdict": "INSUFFICIENT", "issues": ["Dataset version not found"]}

        import pandas as pd
        df = pd.read_parquet(ver.parquet_path)
        result = check_sufficiency(df, reqs)
        return result.model_dump()

    def _tool_run_analysis(self, args: dict[str, Any]) -> dict[str, Any]:
        spec_dict = dict(args.get("spec", {}))

        # Normalize LLM format variations
        if "dataset_versions" in spec_dict and not spec_dict.get("dataset_version_ids"):
            spec_dict["dataset_version_ids"] = [
                x["id"] if isinstance(x, dict) else str(x) for x in spec_dict["dataset_versions"]
            ]
        if "metrics" in spec_dict:
            norm_m = []
            for m in spec_dict["metrics"]:
                if isinstance(m, str):
                    norm_m.append({"name": m})
                elif isinstance(m, dict):
                    m_name = m.get("name") or m.get("metric_name") or m.get("metric") or "outflow_usd"
                    norm_m.append({"name": m_name, "params": m.get("params", {})})
            spec_dict["metrics"] = norm_m
        if "filters" in spec_dict:
            for f in spec_dict["filters"]:
                if isinstance(f, dict):
                    if "operator" in f and "op" not in f:
                        f["op"] = f.pop("operator")
                    if f.get("value") == "outflow":
                        f["value"] = "out"
                    elif f.get("value") == "inflow":
                        f["value"] = "in"
        if "time" in spec_dict and isinstance(spec_dict["time"], dict):
            t_obj = spec_dict["time"]
            if "column" not in t_obj:
                t_obj["column"] = "block_time"
            for k in ["start", "end"]:
                if k in t_obj and isinstance(t_obj[k], str) and "T" in t_obj[k]:
                    t_obj[k] = t_obj[k].split("T")[0]

        spec = AnalysisSpec.model_validate(spec_dict)

        # Look up dataset versions or auto-resolve
        v_ids = spec.dataset_version_ids
        if not v_ids:
            # Auto-resolve latest version in workspace
            stmt = select(DatasetVersion).join(Dataset).where(Dataset.workspace_id == self.workspace_id).order_by(DatasetVersion.version_num.desc())
            latest_v = self.db.exec(stmt).first()
            if latest_v:
                v_ids = [latest_v.id]
                spec.dataset_version_ids = v_ids
            else:
                return {"error": "No datasets available in workspace"}

        target_id = v_ids[0]
        v = self.db.get(DatasetVersion, target_id)
        if not v and target_id.startswith("ds_"):
            stmt = select(DatasetVersion).where(DatasetVersion.dataset_id == target_id).order_by(DatasetVersion.version_num.desc())
            v = self.db.exec(stmt).first()
            if v:
                spec.dataset_version_ids = [v.id]

        if not v:
            return {"error": f"Dataset version {target_id} not found"}

        table_map = {"t": v.parquet_path}
        dataset_hashes = {v.id: v.content_hash}

        import pandas as pd
        df = pd.read_parquet(v.parquet_path)

        for pack in ["treasury_v1", "generic_v1"]:
            try:
                load_metric_pack(pack)
            except Exception:
                pass

        evidence, q_res = execute_analysis(
            spec=spec,
            session_id=self.session_id,
            table_map=table_map,
            dataset_hashes=dataset_hashes,
            available_columns=list(df.columns),
        )

        db_ev = Evidence(
            id=evidence.id,
            session_id=self.session_id,
            sha256=evidence.evidence_hash,
            spec_json=json.dumps(evidence.spec.model_dump(mode="json")),
            result_hash=evidence.result_hash,
            metrics_json=json.dumps(evidence.metrics),
            row_refs_json=json.dumps(evidence.row_refs.model_dump(mode="json")),
            explorer_urls_json="[]",
            reproduction_json=json.dumps({
                "query": evidence.query_sql,
                "params": evidence.query_params,
                "dataset_hashes": evidence.dataset_hashes,
            }),
            created_at=evidence.created_at,
        )
        self.db.add(db_ev)
        self.db.commit()
        self.db.refresh(db_ev)

        # Return ONLY metrics and evidence ID - NEVER raw rows
        return {
            "evidence_id": db_ev.id,
            "result_hash": db_ev.result_hash,
            "metrics": json.loads(db_ev.metrics_json),
            "reproduction": json.loads(db_ev.reproduction_json),
        }

    def _tool_propose_finding(self, args: dict[str, Any]) -> dict[str, Any]:
        claim = args.get("claim", "")
        claim_type = args.get("claim_type", "metric")
        ev_id = args.get("evidence_id", "")

        ev = self.db.get(Evidence, ev_id)
        if not ev:
            return {"error": f"Evidence {ev_id} not found"}

        # Run validators
        ev_metrics = json.loads(ev.metrics_json)
        num_lint = lint_numbers(claim, ev_metrics)
        lang_lint = lint_language(claim)

        # Assign status
        status_val = evaluate_evidence_status(
            recompute_matches=True,
            claim_type=claim_type,
            invariants_passed=num_lint.passed,
            sample_size_ok=True,
        )

        from backend.core.ids import generate_id
        finding = Finding(
            id=generate_id("fd"),
            session_id=self.session_id,
            evidence_id=ev_id,
            claim=claim,
            claim_type=claim_type,
            status=status_val,
            numbers_grounded=num_lint.passed,
            language_grounded=lang_lint.passed,
        )
        self.db.add(finding)
        self.db.commit()
        self.db.refresh(finding)

        return {
            "finding_id": finding.id,
            "claim": finding.claim,
            "status": finding.status,
            "numbers_grounded": finding.numbers_grounded,
            "language_grounded": finding.language_grounded,
            "ungrounded_tokens": num_lint.ungrounded_tokens,
            "language_flags": lang_lint.flagged_phrases,
        }

    def _tool_create_chart(self, args: dict[str, Any]) -> dict[str, Any]:
        finding_id = args.get("finding_id", "")
        intent = args.get("intent", "compare")
        # Build simple Vega-Lite spec
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": f"Visualization for finding {finding_id}",
            "mark": "bar",
            "encoding": {
                "x": {"field": "category", "type": "nominal"},
                "y": {"field": "value", "type": "quantitative"},
            },
        }
        return {"finding_id": finding_id, "intent": intent, "chart_spec": spec}

    def _tool_ask_user(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"questions": args.get("questions", []), "requires_user_response": True}

    def _tool_build_report(self, args: dict[str, Any]) -> dict[str, Any]:
        title = args.get("title", "Analysis Report")
        f_stmt = select(Finding).where(Finding.session_id == self.session_id)
        findings = self.db.exec(f_stmt).all()
        return {
            "title": title,
            "findings_count": len(findings),
            "status": "ready_for_assembly",
        }
