"use client";

import React, { useState } from "react";
import { FullVerificationResult } from "@/lib/verify";
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  XCircle,
  Copy,
  ExternalLink,
  Shield,
  Clock,
  Cpu,
} from "lucide-react";

interface VerifyResultProps {
  result: FullVerificationResult;
}

export function VerifyResult({ result }: VerifyResultProps) {
  const [copiedRoot, setCopiedRoot] = useState(false);

  const getStatusBanner = () => {
    switch (result.status) {
      case "VERIFIED":
        return {
          icon: <CheckCircle2 className="h-6 w-6 text-emerald-400" />,
          title: "VERIFIED ON SOLANA",
          desc: "Cryptographic root and on-chain memo match byte-for-byte. The report is authentic and unmodified.",
          badgeBg: "bg-emerald-950/40 border-emerald-500/40 text-emerald-300",
        };
      case "MODIFIED":
        return {
          icon: <AlertOctagon className="h-6 w-6 text-rose-400" />,
          title: "TAMPER DETECTED / MODIFIED",
          desc: "The report markdown or evidence does not match the cryptographic root anchored in the transaction.",
          badgeBg: "bg-rose-950/40 border-rose-500/40 text-rose-300",
        };
      case "NOT_ANCHORED":
        return {
          icon: <AlertTriangle className="h-6 w-6 text-amber-400" />,
          title: "VALID BUNDLE — NOT YET ANCHORED",
          desc: "The bundle is cryptographically consistent, but no confirmed transaction memo was found on-chain.",
          badgeBg: "bg-amber-950/40 border-amber-500/40 text-amber-300",
        };
      default:
        return {
          icon: <XCircle className="h-6 w-6 text-rose-400" />,
          title: "INVALID BUNDLE",
          desc: "The uploaded attestation bundle does not match the Analyx canonical schema.",
          badgeBg: "bg-rose-950/40 border-rose-500/40 text-rose-300",
        };
    }
  };

  const banner = getStatusBanner();

  return (
    <div className="space-y-6">
      {/* Top Status Banner */}
      <div
        className={`rounded-2xl border p-6 flex items-start gap-4 ${banner.badgeBg}`}
      >
        <div className="flex-shrink-0 mt-0.5">{banner.icon}</div>
        <div>
          <h2 className="text-base font-bold font-mono tracking-wide">
            {banner.title}
          </h2>
          <p className="mt-1 text-xs text-zinc-300 leading-relaxed">
            {banner.desc}
          </p>
        </div>
      </div>

      {/* Attestation Root Card */}
      {result.computedRoot && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-400">
              Computed Attestation Root (RFC 8785)
            </span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(result.computedRoot);
                setCopiedRoot(true);
                setTimeout(() => setCopiedRoot(false), 2000);
              }}
              className="flex items-center gap-1 text-[11px] font-mono text-zinc-400 hover:text-cyan-400 transition"
            >
              <Copy className="h-3 w-3" />
              <span>{copiedRoot ? "Copied!" : "Copy"}</span>
            </button>
          </div>
          <code className="block font-mono text-xs text-cyan-300 break-all select-all">
            {result.computedRoot}
          </code>
        </div>
      )}

      {/* On-Chain Details (if anchored) */}
      {result.onChain && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-3">
            <Shield className="h-4 w-4 text-indigo-400" />
            <h3 className="text-xs font-semibold text-zinc-200">
              Solana Blockchain Anchoring Details
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
            <div>
              <span className="text-zinc-500 block text-[10px] uppercase">
                Cluster
              </span>
              <span className="text-zinc-200 font-semibold uppercase">
                {result.onChain.cluster}
              </span>
            </div>

            <div>
              <span className="text-zinc-500 block text-[10px] uppercase">
                Block Time
              </span>
              <span className="text-zinc-300">
                {result.onChain.block_time
                  ? new Date(result.onChain.block_time).toLocaleString()
                  : "Confirmed"}
              </span>
            </div>

            <div className="sm:col-span-2">
              <span className="text-zinc-500 block text-[10px] uppercase">
                Transaction Signature
              </span>
              <a
                href={result.onChain.explorer_url}
                target="_blank"
                rel="noreferrer"
                className="text-cyan-400 hover:underline flex items-center gap-1.5 break-all"
              >
                <span>{result.onChain.tx_signature}</span>
                <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
              </a>
            </div>

            <div className="sm:col-span-2">
              <span className="text-zinc-500 block text-[10px] uppercase">
                Signer Public Key
              </span>
              <span className="text-zinc-300 break-all">
                {result.onChain.signer}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Verification Checklist */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono">
          Integrity Checks Checklist ({result.checks.length})
        </h3>

        <div className="divide-y divide-zinc-800/60 font-mono text-xs">
          {result.checks.map((chk, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 py-2.5 first:pt-1 last:pb-1"
            >
              {chk.passed ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              ) : (
                <XCircle className="h-4 w-4 text-rose-400 flex-shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <span className="font-semibold text-zinc-200 block">
                  {chk.name.replace(/_/g, " ").toUpperCase()}
                </span>
                <span className="text-[11px] text-zinc-400 leading-snug">
                  {chk.detail}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
