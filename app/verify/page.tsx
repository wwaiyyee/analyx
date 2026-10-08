"use client";

import React, { useState } from "react";
import { verifyFullAttestation, FullVerificationResult } from "@/lib/verify";
import { VerifyResult } from "@/components/verify-result";
import {
  ShieldCheck,
  Upload,
  FileCode,
  FileText,
  Loader2,
  Sparkles,
  Search,
} from "lucide-react";

const SAMPLE_BUNDLE = {
  version: "1.0",
  report: {
    id: "rp_sample_report",
    title: "Treasury Solvency Audit",
    sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  },
  datasets: [
    {
      dataset_id: "ds_sample_treasury",
      version_hash: "7b2a9e01884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      row_count: 1250,
    },
  ],
  evidence: [
    {
      evidence_id: "ev_outflow_nov",
      sha256: "4a2b9e01884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    },
  ],
  engine: {
    name: "DuckDB",
    version: "1.1.0",
  },
};

export default function PublicVerifyPage() {
  const [bundleInput, setBundleInput] = useState("");
  const [reportMarkdown, setReportMarkdown] = useState("");
  const [txSignature, setTxSignature] = useState("");
  const [cluster, setCluster] = useState<"devnet" | "mainnet-beta">("devnet");

  const [verifying, setVerifying] = useState(false);
  const [result, setResult] = useState<FullVerificationResult | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const handleLoadSample = () => {
    setBundleInput(JSON.stringify(SAMPLE_BUNDLE, null, 2));
    setReportMarkdown("# Treasury Solvency Audit\n\nVerified report markdown.");
    setTxSignature("5Hw...sample_solana_signature");
    setParseError(null);
  };

  const handleVerify = async () => {
    setParseError(null);
    setResult(null);

    let parsedBundle: Record<string, unknown>;
    try {
      parsedBundle = JSON.parse(bundleInput);
    } catch {
      setParseError("Invalid JSON in Attestation Bundle input.");
      return;
    }

    setVerifying(true);
    try {
      const res = await verifyFullAttestation({
        bundle: parsedBundle,
        reportMarkdown: reportMarkdown.trim() ? reportMarkdown : undefined,
        txSignature: txSignature.trim() ? txSignature.trim() : undefined,
        cluster,
      });
      setResult(res);
    } catch (err: unknown) {
      setParseError(
        err instanceof Error ? err.message : "Verification execution failed"
      );
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#090a0f] py-12 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl space-y-8">
        {/* Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-950/40 px-3 py-1 text-xs font-mono text-cyan-300">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Public Attestation Verifier</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            Verify Report Integrity & Solana Anchors
          </h1>
          <p className="text-sm text-zinc-400 max-w-xl mx-auto">
            Input an Analyx Attestation Bundle JSON to independently verify canonical
            hashes and check on-chain Solana blockchain proof.
          </p>
        </div>

        {/* Verification Form */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 sm:p-8 shadow-2xl backdrop-blur-sm space-y-6">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
            <h2 className="text-sm font-semibold text-zinc-200">
              Attestation Input Data
            </h2>
            <button
              onClick={handleLoadSample}
              className="flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-300 hover:text-white hover:bg-zinc-700 transition"
            >
              <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
              <span>Load Sample Bundle</span>
            </button>
          </div>

          {/* Bundle JSON Input */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <FileCode className="h-3.5 w-3.5 text-cyan-400" />
                <span>Attestation Bundle JSON *</span>
              </label>
              <span className="text-[11px] font-mono text-zinc-500">
                Required
              </span>
            </div>
            <textarea
              rows={8}
              value={bundleInput}
              onChange={(e) => setBundleInput(e.target.value)}
              placeholder="Paste AttestationBundle JSON payload here (e.g. { 'version': '1.0', 'report': {...}, 'datasets': [...], 'evidence': [...] })"
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Optional Report Markdown */}
          <div className="space-y-2">
            <label className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5 text-indigo-400" />
              <span>Report Markdown Content (Optional)</span>
            </label>
            <textarea
              rows={4}
              value={reportMarkdown}
              onChange={(e) => setReportMarkdown(e.target.value)}
              placeholder="Paste raw markdown text to verify frozen region hash matching..."
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Optional Tx Signature & Cluster */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2 space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-zinc-400">
                Solana Transaction Signature (Optional)
              </label>
              <input
                type="text"
                value={txSignature}
                onChange={(e) => setTxSignature(e.target.value)}
                placeholder="e.g. 5Hw94... (Base58 tx signature)"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-zinc-400">
                Solana Cluster
              </label>
              <select
                value={cluster}
                onChange={(e) =>
                  setCluster(e.target.value as "devnet" | "mainnet-beta")
                }
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs font-mono text-zinc-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="devnet">Devnet</option>
                <option value="mainnet-beta">Mainnet-Beta</option>
              </select>
            </div>
          </div>

          {parseError && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-300">
              {parseError}
            </div>
          )}

          {/* Submit Button */}
          <button
            onClick={handleVerify}
            disabled={verifying || !bundleInput.trim()}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 py-3.5 text-xs font-semibold text-white shadow-lg shadow-cyan-500/20 hover:opacity-95 transition disabled:opacity-40"
          >
            {verifying ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Running Cryptographic & Solana RPC Verification...</span>
              </>
            ) : (
              <>
                <Search className="h-4 w-4" />
                <span>Verify Attestation Integrity</span>
              </>
            )}
          </button>
        </div>

        {/* Verification Result Display */}
        {result && <VerifyResult result={result} />}
      </div>
    </div>
  );
}
