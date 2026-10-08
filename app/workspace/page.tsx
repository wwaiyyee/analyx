"use client";

import React, { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useWallet } from "@/lib/wallet/provider";
import { api } from "@/lib/api";
import { Loader2, Sparkles, Database } from "lucide-react";

export default function WorkspaceEntryPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemo = searchParams.get("demo") === "true";
  const { connected, connectDemo } = useWallet();

  const [status, setStatus] = useState("Initializing workspace session...");

  useEffect(() => {
    let mounted = true;

    async function initWorkspace() {
      try {
        if (!connected && isDemo) {
          setStatus("Authenticating demo wallet session...");
          await connectDemo();
        }

        setStatus("Setting up analysis workspace...");
        // Check existing datasets
        let datasetIds: string[] = [];
        try {
          const datasets = await api.datasets.list();
          datasetIds = datasets.map((d) => d.id);
        } catch {
          // In case fresh session needed
        }

        // Create new session
        const session = await api.sessions.create(
          isDemo ? "Solana Treasury Analysis (Demo)" : "New Analysis Session",
          datasetIds
        );

        if (mounted) {
          router.replace(`/workspace/${session.id}`);
        }
      } catch (err: unknown) {
        console.error("Failed to initialize workspace session:", err);
        // Fallback default redirect
        if (mounted) {
          router.replace(`/workspace/ses_default_session`);
        }
      }
    }

    initWorkspace();

    return () => {
      mounted = false;
    };
  }, [connected, isDemo, connectDemo, router]);

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center bg-[#090a0f] p-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 mb-6 shadow-xl shadow-cyan-500/10">
        <Database className="h-8 w-8 animate-pulse" />
      </div>

      <h2 className="text-base font-semibold text-zinc-100">
        Preparing Evidence Workspace
      </h2>
      <p className="mt-2 text-xs font-mono text-zinc-400 flex items-center gap-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />
        <span>{status}</span>
      </p>
    </div>
  );
}
