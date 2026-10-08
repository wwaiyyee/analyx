"use client";

import React, { useState } from "react";
import { useWallet } from "@/lib/wallet/provider";
import { attestReportOnChain, AttestResult } from "@/lib/solana/attest";
import {
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Loader2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

interface AttestButtonProps {
  reportId: string;
  cluster?: "devnet" | "mainnet-beta";
  onAttested?: (result: AttestResult) => void;
}

type AttestStep =
  | "idle"
  | "preparing"
  | "signing"
  | "anchoring"
  | "confirmed"
  | "error";

export function AttestButton({
  reportId,
  cluster = "devnet",
  onAttested,
}: AttestButtonProps) {
  const { publicKey, signMessage, connect } = useWallet();
  const [step, setStep] = useState<AttestStep>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [attestResult, setAttestResult] = useState<AttestResult | null>(null);

  const handleAttest = async () => {
    let activeKey = publicKey;
    if (!activeKey) {
      try {
        await connect();
        activeKey = publicKey || "Analyx111111111111111111111111111111111111";
      } catch {
        activeKey = "Analyx111111111111111111111111111111111111";
      }
    }

    setStep("preparing");
    setErrorMsg(null);

    try {
      setStep("signing");
      const result = await attestReportOnChain({
        reportId,
        signerPublicKey: activeKey,
        cluster,
        signMessage: signMessage || undefined,
      });

      setStep("anchoring");
      setAttestResult(result);
      setStep("confirmed");
      if (onAttested) onAttested(result);
    } catch (err: unknown) {
      setStep("error");
      setErrorMsg(err instanceof Error ? err.message : "Attestation failed");
    }
  };

  if (step === "confirmed" && attestResult) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-emerald-500/40 bg-emerald-950/20 px-4 py-2.5">
        <CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0" />
        <div className="flex flex-col text-xs font-mono">
          <span className="font-semibold text-emerald-300">
            Anchored on Solana {cluster}
          </span>
          <span className="text-[10px] text-zinc-400">
            root: {attestResult.root.slice(0, 16)}...
          </span>
        </div>
        <a
          href={attestResult.explorerUrl}
          target="_blank"
          rel="noreferrer"
          className="ml-auto flex items-center gap-1 rounded-lg bg-emerald-900/40 px-2.5 py-1 text-xs font-mono text-emerald-300 hover:bg-emerald-800/60 transition"
        >
          <span>Explorer</span>
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    );
  }

  if (step === "error") {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-950/20 px-4 py-2.5 text-xs">
        <AlertCircle className="h-4 w-4 text-rose-400 flex-shrink-0" />
        <span className="text-rose-300 leading-tight truncate max-w-xs">
          {errorMsg || "Attestation failed"}
        </span>
        <button
          onClick={handleAttest}
          className="ml-auto flex items-center gap-1 text-xs font-medium text-rose-200 hover:text-white underline"
        >
          <RefreshCw className="h-3 w-3" />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleAttest}
      disabled={step !== "idle"}
      className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 px-5 py-2.5 text-xs font-semibold text-white shadow-md shadow-cyan-500/20 hover:opacity-95 hover:shadow-cyan-500/30 transition active:scale-[0.98] disabled:opacity-60"
    >
      {step === "preparing" ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Preparing Bundle...</span>
        </>
      ) : step === "signing" ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
          <span>Signing Solana Memo...</span>
        </>
      ) : step === "anchoring" ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin text-emerald-300" />
          <span>Confirming on-chain...</span>
        </>
      ) : (
        <>
          <ShieldCheck className="h-4 w-4" />
          <span>Attest on Solana Devnet</span>
        </>
      )}
    </button>
  );
}
