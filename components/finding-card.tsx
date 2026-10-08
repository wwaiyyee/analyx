"use client";

import React from "react";
import { FindingItem } from "@/lib/api";
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  HelpCircle,
  Search,
  Hash,
  ShieldCheck,
} from "lucide-react";

interface FindingCardProps {
  finding: FindingItem;
  onOpenWhy: (finding: FindingItem) => void;
}

export function FindingCard({ finding, onOpenWhy }: FindingCardProps) {
  const getStatusBadge = (status: FindingItem["status"]) => {
    switch (status) {
      case "supported":
        return (
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-950/60 border border-emerald-500/30 px-2 py-0.5 font-mono text-[11px] font-medium text-emerald-400">
            <CheckCircle2 className="h-3 w-3" />
            SUPPORTED
          </span>
        );
      case "partially_supported":
        return (
          <span className="inline-flex items-center gap-1 rounded-md bg-amber-950/60 border border-amber-500/30 px-2 py-0.5 font-mono text-[11px] font-medium text-amber-400">
            <AlertTriangle className="h-3 w-3" />
            PARTIALLY SUPPORTED
          </span>
        );
      case "insufficient":
        return (
          <span className="inline-flex items-center gap-1 rounded-md bg-rose-950/60 border border-rose-500/30 px-2 py-0.5 font-mono text-[11px] font-medium text-rose-400">
            <AlertOctagon className="h-3 w-3" />
            INSUFFICIENT EVIDENCE
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-md bg-zinc-900 border border-zinc-700 px-2 py-0.5 font-mono text-[11px] font-medium text-zinc-400">
            <HelpCircle className="h-3 w-3" />
            N/A
          </span>
        );
    }
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 hover:border-zinc-700/80 transition-all duration-200">
      {/* Top Header: Status & Claim Type */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/60 pb-3 mb-3">
        <div className="flex items-center gap-2">
          {getStatusBadge(finding.status)}
          <span className="rounded bg-zinc-800/80 px-2 py-0.5 font-mono text-[10px] text-zinc-300 uppercase">
            {finding.claim_type}
          </span>
        </div>

        {finding.numbers_grounded ? (
          <span className="flex items-center gap-1 font-mono text-[10px] text-emerald-400/90">
            <ShieldCheck className="h-3.5 w-3.5" />
            100% Grounded Numbers
          </span>
        ) : (
          <span className="flex items-center gap-1 font-mono text-[10px] text-amber-400/90">
            <AlertTriangle className="h-3.5 w-3.5" />
            Ungrounded Numerical Claims
          </span>
        )}
      </div>

      {/* Claim Body */}
      <p className="text-sm font-medium text-zinc-100 leading-relaxed">
        {finding.claim}
      </p>

      {/* Action Footer */}
      <div className="mt-4 flex items-center justify-between pt-2 border-t border-zinc-800/50">
        <div className="flex items-center gap-1.5 font-mono text-[10px] text-zinc-500">
          <Hash className="h-3 w-3" />
          <span>{finding.id}</span>
        </div>

        <button
          onClick={() => onOpenWhy(finding)}
          className="flex items-center gap-1.5 rounded-lg border border-cyan-500/30 bg-cyan-950/30 px-3 py-1 text-xs font-medium text-cyan-300 hover:bg-cyan-900/40 hover:border-cyan-500/50 hover:text-cyan-200 transition active:scale-[0.98]"
        >
          <Search className="h-3 w-3" />
          <span>Why? (Evidence)</span>
        </button>
      </div>
    </div>
  );
}
