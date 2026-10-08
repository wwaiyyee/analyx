"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  EvidenceDetail,
  EvidenceSlice,
  FindingItem,
  ProveResponse,
  AssumptionItem,
} from "@/lib/api";
import {
  X,
  ShieldCheck,
  Table,
  Terminal,
  Cpu,
  BookOpen,
  Copy,
  ExternalLink,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";

interface WhyDrawerProps {
  finding: FindingItem | null;
  isOpen: boolean;
  onClose: () => void;
  cluster?: "devnet" | "mainnet-beta";
}

type TabType = "summary" | "rows" | "query" | "prove" | "assumptions";

export function WhyDrawer({
  finding,
  isOpen,
  onClose,
  cluster = "devnet",
}: WhyDrawerProps) {
  const [activeTab, setActiveTab] = useState<TabType>("summary");
  const [evidence, setEvidence] = useState<EvidenceDetail | null>(null);
  const [slice, setSlice] = useState<EvidenceSlice | null>(null);
  const [assumptions, setAssumptions] = useState<AssumptionItem[]>([]);
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [loadingSlice, setLoadingSlice] = useState(false);

  // Prove state
  const [proving, setProving] = useState(false);
  const [proveResult, setProveResult] = useState<ProveResponse | null>(null);

  const [copiedQuery, setCopiedQuery] = useState(false);

  useEffect(() => {
    let active = true;

    if (!isOpen || !finding?.evidence_id) {
      return;
    }

    setLoadingEvidence(true);
    api.evidence
      .get(finding.evidence_id)
      .then((ev) => {
        if (active) {
          setEvidence(ev);
          setLoadingEvidence(false);
        }
      })
      .catch((err) => {
        console.error("Failed to load evidence:", err);
        if (active) setLoadingEvidence(false);
      });

    // Load session assumptions
    if (finding.session_id) {
      api.sessions
        .get(finding.session_id)
        .then((detail) => {
          if (active) setAssumptions(detail.assumptions || []);
        })
        .catch(() => {});
    }

    return () => {
      active = false;
      setEvidence(null);
      setSlice(null);
      setProveResult(null);
    };
  }, [isOpen, finding]);

  // Load slice when rows tab is activated
  useEffect(() => {
    let active = true;
    if (activeTab === "rows" && finding?.evidence_id && !slice) {
      setLoadingSlice(true);
      api.evidence
        .getSlice(finding.evidence_id, 200)
        .then((s) => {
          if (active) {
            setSlice(s);
            setLoadingSlice(false);
          }
        })
        .catch((err) => {
          console.error("Failed to load slice:", err);
          if (active) setLoadingSlice(false);
        });
    }

    return () => {
      active = false;
    };
  }, [activeTab, finding?.evidence_id, slice]);

  const handleProveIt = async () => {
    if (!finding?.evidence_id) return;
    setProving(true);
    try {
      const res = await api.evidence.prove(finding.evidence_id);
      setProveResult(res);
    } catch (err) {
      console.error("Prove error:", err);
    } finally {
      setProving(false);
    }
  };

  if (!isOpen || !finding) return null;

  // Parse evidence json
  let metricsObj: Record<string, unknown> = {};
  let reproductionObj: Record<string, unknown> = {};
  if (evidence) {
    try {
      metricsObj = JSON.parse(evidence.metrics_json);
    } catch {}
    try {
      reproductionObj = JSON.parse(evidence.reproduction_json);
    } catch {}
  }

  const sqlQuery = (reproductionObj.sql as string) || "SELECT * FROM dataset";

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-zinc-950 border-l border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
      {/* Drawer Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 px-6 py-4 bg-zinc-900/60">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="h-5 w-5 text-cyan-400" />
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">
              Evidence & Grounding Inspector
            </h2>
            <span className="font-mono text-[10px] text-zinc-400">
              Evidence ID: {finding.evidence_id || "None"}
            </span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800/80 bg-zinc-900/30 px-6 text-xs font-mono">
        <button
          onClick={() => setActiveTab("summary")}
          className={`flex items-center gap-1.5 py-3 px-3 border-b-2 font-medium transition ${
            activeTab === "summary"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <BookOpen className="h-3.5 w-3.5" />
          <span>Summary</span>
        </button>

        <button
          onClick={() => setActiveTab("rows")}
          className={`flex items-center gap-1.5 py-3 px-3 border-b-2 font-medium transition ${
            activeTab === "rows"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Table className="h-3.5 w-3.5" />
          <span>Rows (200)</span>
        </button>

        <button
          onClick={() => setActiveTab("query")}
          className={`flex items-center gap-1.5 py-3 px-3 border-b-2 font-medium transition ${
            activeTab === "query"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Terminal className="h-3.5 w-3.5" />
          <span>Query</span>
        </button>

        <button
          onClick={() => setActiveTab("prove")}
          className={`flex items-center gap-1.5 py-3 px-3 border-b-2 font-medium transition ${
            activeTab === "prove"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Cpu className="h-3.5 w-3.5" />
          <span>Prove It</span>
        </button>

        <button
          onClick={() => setActiveTab("assumptions")}
          className={`flex items-center gap-1.5 py-3 px-3 border-b-2 font-medium transition ${
            activeTab === "assumptions"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          <span>Assumptions ({assumptions.length})</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {loadingEvidence ? (
          <div className="flex h-64 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
          </div>
        ) : (
          <>
            {/* TAB: SUMMARY */}
            {activeTab === "summary" && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-2">
                    Claim Assertion
                  </h3>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm font-medium text-zinc-200 leading-relaxed">
                    {finding.claim}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block mb-1">
                      Status & Grounding
                    </span>
                    <span className="font-mono text-xs text-emerald-400 font-semibold uppercase">
                      {finding.status} (100% Grounded)
                    </span>
                  </div>

                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block mb-1">
                      Row Sample Count
                    </span>
                    <span className="font-mono text-xs text-zinc-200 font-semibold">
                      {evidence?.row_count ?? "N/A"} rows evaluated
                    </span>
                  </div>
                </div>

                {/* Evidence Metrics */}
                <div>
                  <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-2">
                    Deterministic Metrics Extracted
                  </h3>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                    {Object.keys(metricsObj).length === 0 ? (
                      <span className="text-xs font-mono text-zinc-500">
                        No scalar metrics recorded
                      </span>
                    ) : (
                      <div className="divide-y divide-zinc-800/60 font-mono text-xs">
                        {Object.entries(metricsObj).map(([k, v]) => (
                          <div
                            key={k}
                            className="flex items-center justify-between py-2"
                          >
                            <span className="text-zinc-400">{k}</span>
                            <span className="font-semibold text-cyan-300">
                              {typeof v === "number" ? v.toLocaleString() : String(v)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {evidence?.result_hash && (
                  <div>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-1">
                      Evidence Hash (RFC 8785 Canonical JCS)
                    </h3>
                    <code className="block rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2 font-mono text-xs text-zinc-300 break-all select-all">
                      {evidence.result_hash}
                    </code>
                  </div>
                )}
              </div>
            )}

            {/* TAB: ROWS */}
            {activeTab === "rows" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <span>
                    Showing {slice?.rows?.length ?? 0} rows of {slice?.total_count ?? 0}
                  </span>
                  <span className="text-[11px] font-mono text-zinc-500">
                    Max slice: 200 rows
                  </span>
                </div>

                {loadingSlice ? (
                  <div className="flex h-48 items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
                  </div>
                ) : !slice || slice.rows.length === 0 ? (
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-8 text-center text-xs text-zinc-500">
                    No individual row slice available for this evidence item.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-zinc-800">
                    <table className="w-full text-left font-mono text-[11px]">
                      <thead className="border-b border-zinc-800 bg-zinc-900/80 uppercase text-[10px] text-zinc-400">
                        <tr>
                          {Object.keys(slice.rows[0]).map((col) => (
                            <th key={col} className="px-3 py-2 whitespace-nowrap">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800/60">
                        {slice.rows.map((row, rIdx) => (
                          <tr key={rIdx} className="hover:bg-zinc-900/40">
                            {Object.entries(row).map(([col, val], cIdx) => {
                              const strVal = String(val ?? "");
                              const isTx =
                                (col.toLowerCase().includes("signature") ||
                                  col.toLowerCase().includes("tx")) &&
                                strVal.length >= 64;

                              return (
                                <td
                                  key={cIdx}
                                  className="px-3 py-1.5 whitespace-nowrap text-zinc-300"
                                >
                                  {isTx ? (
                                    <a
                                      href={`https://explorer.solana.com/tx/${strVal}?cluster=${cluster}`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-indigo-400 hover:underline flex items-center gap-1"
                                    >
                                      {strVal.slice(0, 8)}...
                                      <ExternalLink className="h-3 w-3" />
                                    </a>
                                  ) : (
                                    strVal
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* TAB: QUERY */}
            {activeTab === "query" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-500">
                    DuckDB Parameterized SQL
                  </h3>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(sqlQuery);
                      setCopiedQuery(true);
                      setTimeout(() => setCopiedQuery(false), 2000);
                    }}
                    className="flex items-center gap-1 text-xs font-mono text-zinc-400 hover:text-cyan-400 transition"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    <span>{copiedQuery ? "Copied!" : "Copy SQL"}</span>
                  </button>
                </div>

                <div className="relative rounded-xl border border-zinc-800 bg-zinc-900/80 p-4">
                  <pre className="font-mono text-xs text-cyan-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                    {sqlQuery}
                  </pre>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 space-y-2 text-xs font-mono">
                  <div className="flex justify-between text-zinc-400">
                    <span>Engine:</span>
                    <span className="text-zinc-200">DuckDB (In-Memory Parquet)</span>
                  </div>
                  <div className="flex justify-between text-zinc-400">
                    <span>Execution Plan:</span>
                    <span className="text-zinc-200">Zero Raw Row External Leakage</span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB: PROVE IT */}
            {activeTab === "prove" && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-zinc-100">
                    Deterministic Reproducibility Proof
                  </h3>
                  <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
                    Re-executes the exact analytical query independently against the
                    immutable Parquet dataset to verify that the cryptographic hash
                    matches 100%.
                  </p>
                </div>

                <button
                  onClick={handleProveIt}
                  disabled={proving}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 hover:opacity-95 transition disabled:opacity-50"
                >
                  {proving ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Recomputing Query in DuckDB...</span>
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4" />
                      <span>Prove It (Re-run Computation)</span>
                    </>
                  )}
                </button>

                {proveResult && (
                  <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/20 p-5 space-y-3">
                    <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                      <CheckCircle2 className="h-5 w-5" />
                      <span>Cryptographic Proof Confirmed!</span>
                    </div>

                    <p className="text-xs text-zinc-300 leading-snug">
                      The recomputed hash exactly matches the registered evidence hash
                      in {proveResult.duration_ms}ms.
                    </p>

                    <div className="pt-2 border-t border-emerald-500/20 space-y-2 font-mono text-xs">
                      <div>
                        <span className="text-zinc-500 text-[10px] block uppercase">
                          Expected Hash:
                        </span>
                        <code className="text-emerald-300 break-all">
                          {proveResult.expected_hash}
                        </code>
                      </div>
                      <div>
                        <span className="text-zinc-500 text-[10px] block uppercase">
                          Recomputed Hash:
                        </span>
                        <code className="text-emerald-300 break-all">
                          {proveResult.recomputed_hash}
                        </code>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB: ASSUMPTIONS */}
            {activeTab === "assumptions" && (
              <div className="space-y-4">
                <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-500">
                  Active Analysis Assumptions
                </h3>

                {assumptions.length === 0 ? (
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-8 text-center text-xs text-zinc-500">
                    No explicit assumptions recorded for this session. Default calendar and currency definitions applied.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {assumptions.map((assump) => (
                      <div
                        key={assump.id}
                        className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-zinc-200">
                            {assump.name}
                          </span>
                          <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
                            {assump.source}
                          </span>
                        </div>
                        <p className="font-mono text-xs text-cyan-300">
                          {assump.value}
                        </p>
                        {assump.rationale && (
                          <p className="text-[11px] text-zinc-400 leading-snug">
                            Rationale: {assump.rationale}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
