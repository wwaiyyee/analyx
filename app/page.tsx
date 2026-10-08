"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useWallet } from "@/lib/wallet/provider";
import {
  Shield,
  ArrowRight,
  Database,
  Cpu,
  CheckCircle2,
  Lock,
  Sparkles,
  ExternalLink,
  Code2,
  FileCheck,
  Zap,
} from "lucide-react";

export default function LandingPage() {
  const router = useRouter();
  const { connected, connect, connectDemo, connecting } = useWallet();
  const [demoLoading, setDemoLoading] = useState(false);

  const handleLaunchWorkspace = async () => {
    if (connected) {
      router.push("/workspace");
      return;
    }
    await connect();
    router.push("/workspace");
  };

  const handleLaunchDemo = async () => {
    setDemoLoading(true);
    try {
      await connectDemo();
      router.push("/workspace?demo=true");
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col justify-between overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-cyan-500/10 via-indigo-500/5 to-transparent blur-3xl pointer-events-none -z-10" />
      <div className="absolute bottom-10 right-10 w-[500px] h-[300px] bg-indigo-500/5 blur-3xl pointer-events-none -z-10" />

      {/* Hero Section */}
      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 pt-16 pb-20 text-center">
        {/* Top Tag */}
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-950/40 px-3.5 py-1 text-xs font-mono text-cyan-300 shadow-inner mb-8">
          <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
          <span>Cryptographically Verifiable AI Analytics</span>
          <span className="text-zinc-500">•</span>
          <span className="text-zinc-400">Solana Memo Anchored</span>
        </div>

        {/* Main Headline */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-4xl mx-auto leading-[1.1]">
          Evidence-First AI for{" "}
          <span className="bg-gradient-to-r from-cyan-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
            Deterministic Truth
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mt-6 text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
          Numbers come from an air-gapped deterministic engine, never the LLM.
          Every metric, insight, and chart is backed by cryptographic proof and
          anchored on Solana.
        </p>

        {/* CTA Buttons */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <button
            onClick={handleLaunchWorkspace}
            disabled={connecting}
            className="flex items-center gap-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-cyan-500/25 hover:opacity-95 hover:shadow-cyan-500/40 transition active:scale-[0.99] disabled:opacity-50"
          >
            <span>{connected ? "Open Workspace" : "Connect Solana Wallet"}</span>
            <ArrowRight className="h-4 w-4" />
          </button>

          <button
            onClick={handleLaunchDemo}
            disabled={demoLoading}
            className="flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900/90 px-6 py-3.5 text-sm font-semibold text-zinc-200 hover:bg-zinc-800 hover:text-white hover:border-zinc-600 transition active:scale-[0.99]"
          >
            <Sparkles className="h-4 w-4 text-cyan-400" />
            <span>{demoLoading ? "Preparing Demo..." : "Try Demo Treasury"}</span>
          </button>

          <Link
            href="/verify"
            className="flex items-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-950/60 px-5 py-3.5 text-sm font-medium text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition"
          >
            <FileCheck className="h-4 w-4 text-indigo-400" />
            <span>Public Verifier</span>
          </Link>
        </div>

        {/* Live Proof Demo Card */}
        <div className="mt-16 mx-auto max-w-3xl rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6 text-left shadow-2xl backdrop-blur-sm">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4 mb-4">
            <div className="flex items-center gap-2">
              <span className="flex h-3 w-3 rounded-full bg-emerald-400" />
              <span className="font-mono text-xs uppercase tracking-wider text-zinc-400">
                Verified Finding Snapshot
              </span>
            </div>
            <span className="rounded bg-emerald-950/60 border border-emerald-500/30 px-2 py-0.5 font-mono text-[11px] text-emerald-400 font-medium">
              SUPPORTED (100% GROUNDED)
            </span>
          </div>

          <p className="text-zinc-200 text-base font-medium">
            &ldquo;In November 2024, total treasury outflow was{" "}
            <span className="text-cyan-400 font-mono font-bold">$1,245,820.50</span>{" "}
            across 842 transfers, representing a 14.2% month-over-month increase.&rdquo;
          </p>

          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-zinc-800/50 text-xs font-mono text-zinc-400">
            <div>
              <span className="text-zinc-500 block text-[10px]">EVIDENCE ROOT</span>
              <span className="text-zinc-300">sha256:7b2a9e...f41d</span>
            </div>
            <div>
              <span className="text-zinc-500 block text-[10px]">ENGINE RUNTIME</span>
              <span className="text-zinc-300">DuckDB 1.1 (0.04s)</span>
            </div>
            <div>
              <span className="text-zinc-500 block text-[10px]">SOLANA ATTESTATION</span>
              <span className="text-indigo-400 flex items-center gap-1">
                analyx:v1:7b2a9e...
                <ExternalLink className="h-3 w-3" />
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Grid Pillars */}
      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 border-t border-zinc-900">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Card 1 */}
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-6 hover:border-zinc-700 transition">
            <div className="h-10 w-10 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400 mb-4">
              <Cpu className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-white">
              Deterministic Analytics Engine
            </h3>
            <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
              Every aggregation runs in an isolated SQL engine. The LLM produces
              strict AnalysisSpecs, never computing arithmetic or interpolating numbers.
            </p>
          </div>

          {/* Card 2 */}
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-6 hover:border-zinc-700 transition">
            <div className="h-10 w-10 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400 mb-4">
              <Shield className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-white">
              Solana On-Chain Attestation
            </h3>
            <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
              Reports and evidence are serialized via RFC 8785 canonical JSON and
              anchored to Solana using standard Memo transactions for tamper-proof audit trails.
            </p>
          </div>

          {/* Card 3 */}
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-6 hover:border-zinc-700 transition">
            <div className="h-10 w-10 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-400 mb-4">
              <Lock className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-white">
              Zero Raw Row Leakage
            </h3>
            <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
              Full PII detection and masking. External models receive only column
              schemas and aggregated summary metrics, keeping your raw financial data safe.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-800/80 py-8 px-4 text-center text-xs text-zinc-500">
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-cyan-400" />
            <span className="font-semibold text-zinc-400">Analyx</span>
            <span>— The Evidence-First AI Analyst</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/verify" className="hover:text-zinc-300 transition">
              Verify Report
            </Link>
            <Link href="/workspace" className="hover:text-zinc-300 transition">
              Workspace
            </Link>
            <span className="text-zinc-600">Solana Devnet Ready</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
