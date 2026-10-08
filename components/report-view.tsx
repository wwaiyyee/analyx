"use client";

import React, { useState } from "react";
import { ReportItem } from "@/lib/api";
import {
  FileText,
  Download,
  ShieldCheck,
  CheckCircle2,
  Copy,
  ExternalLink,
  Lock,
  X,
  FileCode,
} from "lucide-react";

interface ReportViewProps {
  report: ReportItem;
  isOpen: boolean;
  onClose: () => void;
  onAttestOnChain?: () => void;
}

export function ReportView({
  report,
  isOpen,
  onClose,
  onAttestOnChain,
}: ReportViewProps) {
  const [copiedHash, setCopiedHash] = useState(false);

  if (!isOpen) return null;

  const handleDownloadMarkdown = () => {
    const blob = new Blob([report.markdown_content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.title.toLowerCase().replace(/\s+/g, "_")}_${report.id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopyHash = () => {
    navigator.clipboard.writeText(report.sha256);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4 bg-zinc-900/60">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">
                {report.title}
              </h2>
              <div className="flex items-center gap-3 text-xs font-mono text-zinc-400">
                <span>ID: {report.id}</span>
                <span>•</span>
                <span className="text-zinc-500">
                  {report.created_at ? new Date(report.created_at).toLocaleDateString() : ""}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDownloadMarkdown}
              className="flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 transition"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Download .md</span>
            </button>

            {onAttestOnChain && (
              <button
                onClick={onAttestOnChain}
                className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-cyan-500/20 hover:opacity-95 transition"
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                <span>Attest on Solana</span>
              </button>
            )}

            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition ml-2"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Frozen Region Hash Banner */}
        <div className="flex items-center justify-between border-b border-zinc-800/80 bg-zinc-900/30 px-6 py-2.5 font-mono text-xs">
          <div className="flex items-center gap-2 text-zinc-400">
            <Lock className="h-3.5 w-3.5 text-cyan-400" />
            <span>Frozen Region Hash (Sections 1–9):</span>
            <code className="text-zinc-200">{report.sha256}</code>
          </div>

          <button
            onClick={handleCopyHash}
            className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-cyan-400 transition"
          >
            <Copy className="h-3 w-3" />
            <span>{copiedHash ? "Copied!" : "Copy Hash"}</span>
          </button>
        </div>

        {/* Markdown Content Viewer */}
        <div className="flex-1 overflow-y-auto p-8 font-sans text-sm text-zinc-200 leading-relaxed space-y-4">
          <div className="prose prose-invert max-w-none">
            <pre className="whitespace-pre-wrap font-sans text-zinc-300 bg-transparent p-0 leading-relaxed text-sm">
              {report.markdown_content}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-zinc-800 px-6 py-3 bg-zinc-900/40 text-xs font-mono text-zinc-500">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            <span>All numbers deterministically compiled from evidence ledger</span>
          </div>
          <span>Analyx v0.1.0</span>
        </div>
      </div>
    </div>
  );
}
