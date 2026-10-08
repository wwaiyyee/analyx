"use client";

import React, { useEffect, useRef, useState } from "react";
import { BarChart3, Table, Search, Loader2 } from "lucide-react";

interface VegaWrapperProps {
  spec: Record<string, unknown> | string;
  title?: string;
  evidenceId?: string;
  onOpenWhy?: (evidenceId: string) => void;
}

export function VegaWrapper({
  spec,
  title,
  evidenceId,
  onOpenWhy,
}: VegaWrapperProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showData, setShowData] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(true);

  // Parse spec if it was passed as string
  let parsedSpec: Record<string, unknown> = {};
  if (typeof spec === "string") {
    try {
      parsedSpec = JSON.parse(spec);
    } catch {
      parsedSpec = {};
    }
  } else {
    parsedSpec = spec;
  }

  // Extract tabular data if available
  const dataValues = Array.isArray((parsedSpec.data as Record<string, unknown>)?.values)
    ? ((parsedSpec.data as Record<string, unknown>).values as Array<Record<string, unknown>>)
    : [];

  const chartTitle =
    title ||
    (typeof parsedSpec.title === "string" ? parsedSpec.title : "") ||
    "Analytical Visualization";

  useEffect(() => {
    let active = true;
    if (!containerRef.current || showData) return;

    setRendering(true);
    setRenderError(null);

    // Dynamically import vega-embed to avoid SSR issues
    import("vega-embed")
      .then(async (vegaEmbedModule) => {
        if (!active || !containerRef.current) return;
        const embed = vegaEmbedModule.default || vegaEmbedModule;

        const specToRender = {
          ...parsedSpec,
          background: "transparent",
          autosize: { type: "fit", contains: "padding" },
          config: {
            ...((parsedSpec.config as Record<string, unknown>) || {}),
            background: "transparent",
            axis: {
              domainColor: "#3f3f46",
              gridColor: "#27272a",
              labelColor: "#a1a1aa",
              titleColor: "#e4e4e7",
              labelFontSize: 11,
              titleFontSize: 12,
            },
            legend: {
              labelColor: "#a1a1aa",
              titleColor: "#e4e4e7",
            },
            view: { stroke: "transparent" },
          },
        };

        try {
          await embed(containerRef.current, specToRender as never, {
            actions: false,
            renderer: "svg",
          });
          if (active) setRendering(false);
        } catch (err: unknown) {
          if (active) {
            setRendering(false);
            setRenderError(err instanceof Error ? err.message : "Failed to render chart");
          }
        }
      })
      .catch((err) => {
        if (active) {
          setRendering(false);
          setRenderError(err.message || "Failed to load visualization engine");
        }
      });

    return () => {
      active = false;
    };
  }, [parsedSpec, showData]);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 shadow-sm space-y-3">
      {/* Chart Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-cyan-400" />
          <h3 className="text-xs font-semibold text-zinc-100">{chartTitle}</h3>
        </div>

        <div className="flex items-center gap-2">
          {evidenceId && onOpenWhy && (
            <button
              onClick={() => onOpenWhy(evidenceId)}
              className="flex items-center gap-1 rounded-md border border-cyan-500/30 bg-cyan-950/30 px-2 py-1 text-[11px] font-medium text-cyan-300 hover:bg-cyan-900/40 transition"
            >
              <Search className="h-3 w-3" />
              <span>Evidence</span>
            </button>
          )}

          {dataValues.length > 0 && (
            <button
              onClick={() => setShowData(!showData)}
              className="flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-800/80 px-2 py-1 text-[11px] font-medium text-zinc-300 hover:bg-zinc-700 hover:text-white transition"
            >
              <Table className="h-3 w-3 text-zinc-400" />
              <span>{showData ? "Show Chart" : "View Data"}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main View Area */}
      {showData && dataValues.length > 0 ? (
        <div className="overflow-x-auto max-h-64 rounded-lg border border-zinc-800 font-mono text-[11px]">
          <table className="w-full text-left">
            <thead className="border-b border-zinc-800 bg-zinc-900/90 text-[10px] text-zinc-400 uppercase">
              <tr>
                {Object.keys(dataValues[0]).map((col) => (
                  <th key={col} className="px-3 py-2 whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {dataValues.map((row, idx) => (
                <tr key={idx} className="hover:bg-zinc-800/30">
                  {Object.values(row).map((val, cIdx) => (
                    <td
                      key={cIdx}
                      className="px-3 py-1.5 whitespace-nowrap text-zinc-300"
                    >
                      {typeof val === "number" ? val.toLocaleString() : String(val)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative min-h-[260px] flex items-center justify-center">
          {rendering && (
            <div className="absolute inset-0 flex items-center justify-center bg-zinc-900/50 backdrop-blur-xs">
              <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
            </div>
          )}
          {renderError ? (
            <div className="text-center text-xs text-rose-400 p-4">
              {renderError}
            </div>
          ) : (
            <div ref={containerRef} className="w-full flex justify-center py-2" />
          )}
        </div>
      )}
    </div>
  );
}
