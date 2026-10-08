"use client";

import React, { useState } from "react";
import { Loader2, Sparkles, ChevronDown, ChevronUp, CheckCircle2 } from "lucide-react";

interface StatusLineProps {
  statusText: string | null;
  active: boolean;
  planSteps?: string[];
}

export function StatusLine({
  statusText,
  active,
  planSteps = [],
}: StatusLineProps) {
  const [showPlan, setShowPlan] = useState(false);

  if (!active && !statusText && planSteps.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-3 shadow-inner backdrop-blur-sm transition-all duration-200">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {active ? (
            <div className="relative flex h-4 w-4 items-center justify-center">
              <span className="absolute h-3 w-3 rounded-full bg-cyan-400 opacity-75 animate-ping" />
              <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
            </div>
          ) : (
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          )}

          <span className="font-mono text-xs text-zinc-300">
            {statusText || (active ? "Analyzing query..." : "Analysis ready")}
          </span>
        </div>

        {planSteps.length > 0 && (
          <button
            onClick={() => setShowPlan(!showPlan)}
            className="flex items-center gap-1 text-[11px] font-mono text-zinc-400 hover:text-cyan-400 transition"
          >
            <Sparkles className="h-3 w-3 text-cyan-400" />
            <span>Plan ({planSteps.length} steps)</span>
            {showPlan ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>
        )}
      </div>

      {showPlan && planSteps.length > 0 && (
        <div className="mt-3 border-t border-zinc-800/80 pt-2 space-y-1.5">
          {planSteps.map((step, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2 text-[11px] font-mono text-zinc-400"
            >
              <span className="text-cyan-500 font-semibold">{idx + 1}.</span>
              <span className="text-zinc-300 leading-snug">{step}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
