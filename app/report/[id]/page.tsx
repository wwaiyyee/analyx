"use client";

import React, { Suspense, use, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ReportItem } from "@/lib/api";
import { AttestButton } from "@/components/attest-button";
import {
  FileText,
  Download,
  ShieldCheck,
  CheckCircle2,
  Copy,
  ExternalLink,
  Lock,
  ArrowLeft,
  Loader2,
  FileCheck,
} from "lucide-react";

interface ReportDetailPageProps {
  params: Promise<{ id: string }>;
}

function ReportDetailContent({ params }: ReportDetailPageProps) {
  const resolvedParams = use(params);
  const reportId = resolvedParams.id;
  const searchParams = useSearchParams();
  const autoAttest = searchParams.get("attest") === "true";

  const [report, setReport] = useState<ReportItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.reports
      .get(reportId)
      .then((data) => {
        if (mounted) {
          setReport(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || "Failed to load report");
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [reportId]);

  const handleDownloadMarkdown = () => {
    if (!report) return;
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
    if (!report) return;
    navigator.clipboard.writeText(report.sha256);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#090a0f]">
        <Loader2 className="h-8 w-8 animate-spin text-cyan-400" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center bg-[#090a0f] p-4 text-center">
        <h2 className="text-lg font-semibold text-rose-400">
          Report Not Found
        </h2>
        <p className="mt-2 text-xs text-zinc-400">{error || "Could not retrieve report data."}</p>
        <Link
          href="/workspace"
          className="mt-6 flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs text-zinc-200 hover:bg-zinc-800"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Return to Workspace</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#090a0f] py-10 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Navigation & Action Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800 pb-5">
          <Link
            href={`/workspace/${report.session_id}`}
            className="flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-cyan-400 transition"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Workspace</span>
          </Link>

          <div className="flex items-center gap-3">
            <button
              onClick={handleDownloadMarkdown}
              className="flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3.5 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 transition"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Download .md</span>
            </button>

            <Link
              href="/verify"
              className="flex items-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-900/60 px-3.5 py-2 text-xs font-medium text-zinc-300 hover:text-white hover:border-zinc-700 transition"
            >
              <FileCheck className="h-3.5 w-3.5 text-indigo-400" />
              <span>Public Verifier</span>
            </Link>

            <AttestButton reportId={report.id} cluster="devnet" />
          </div>
        </div>

        {/* Report Card */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="p-8 border-b border-zinc-800/80 bg-zinc-900/40 space-y-3">
            <div className="flex items-center gap-2">
              <span className="rounded bg-indigo-950/60 border border-indigo-500/30 px-2 py-0.5 font-mono text-[11px] text-indigo-300 font-medium">
                VERIFIED ANALYTICAL REPORT
              </span>
              <span className="text-zinc-600">•</span>
              <span className="font-mono text-xs text-zinc-400">
                Session: {report.session_id}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {report.title}
            </h1>

            <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-zinc-400 pt-1">
              <span>Report ID: {report.id}</span>
              <span>•</span>
              <span>
                Generated:{" "}
                {report.created_at
                  ? new Date(report.created_at).toLocaleString()
                  : "Recently"}
              </span>
            </div>
          </div>

          {/* Frozen Region Banner */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 bg-zinc-900/20 px-8 py-3 text-xs font-mono">
            <div className="flex items-center gap-2 text-zinc-400">
              <Lock className="h-3.5 w-3.5 text-cyan-400" />
              <span>Frozen Region SHA-256 (Sections 1–9):</span>
              <code className="text-zinc-200 select-all">{report.sha256}</code>
            </div>

            <button
              onClick={handleCopyHash}
              className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-cyan-400 transition"
            >
              <Copy className="h-3 w-3" />
              <span>{copiedHash ? "Copied!" : "Copy Hash"}</span>
            </button>
          </div>

          {/* Report Body */}
          <div className="p-8 sm:p-10 font-sans text-sm text-zinc-200 leading-relaxed">
            <div className="prose prose-invert max-w-none">
              <pre className="whitespace-pre-wrap font-sans text-zinc-300 bg-transparent p-0 leading-relaxed text-sm">
                {report.markdown_content}
              </pre>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-zinc-800 px-8 py-4 bg-zinc-900/30 text-xs font-mono text-zinc-500">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>All numbers grounded and reproducible</span>
            </div>
            <span>Analyx Evidence Engine v0.1.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReportDetailPage({ params }: ReportDetailPageProps) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#090a0f]">
          <Loader2 className="h-8 w-8 animate-spin text-cyan-400" />
        </div>
      }
    >
      <ReportDetailContent params={params} />
    </Suspense>
  );
}
