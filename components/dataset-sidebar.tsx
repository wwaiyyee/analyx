"use client";

import React, { useRef, useState } from "react";
import {
  api,
  DatasetItem,
  JobStatusResponse,
} from "@/lib/api";
import {
  Database,
  Upload,
  Plus,
  FileSpreadsheet,
  CheckCircle,
  AlertCircle,
  Loader2,
  Table,
  Link as LinkIcon,
  Search,
} from "lucide-react";

interface DatasetSidebarProps {
  datasets: DatasetItem[];
  activeDatasetId: string | null;
  onSelectDataset: (datasetId: string) => void;
  onDatasetAdded: (datasetId: string) => void;
  onOpenDictionary: (datasetId: string) => void;
}

export function DatasetSidebar({
  datasets,
  activeDatasetId,
  onSelectDataset,
  onDatasetAdded,
  onOpenDictionary,
}: DatasetSidebarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [onchainAddress, setOnchainAddress] = useState("");
  const [syncingOnchain, setSyncingOnchain] = useState(false);
  const [showOnchainInput, setShowOnchainInput] = useState(false);

  // Poll background job
  const pollJob = async (jobId: string, datasetId: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const job = await api.jobs.get(jobId);
        if (job.progress) setUploadProgress(job.progress);

        if (job.status === "completed") {
          clearInterval(interval);
          setUploading(false);
          setUploadProgress(null);
          onDatasetAdded(datasetId);
        } else if (job.status === "failed") {
          clearInterval(interval);
          setUploading(false);
          setUploadProgress(null);
          setUploadError(job.error || "Dataset processing failed");
        }
      } catch (err) {
        if (attempts > 30) {
          clearInterval(interval);
          setUploading(false);
        }
      }
    }, 1000);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    setUploadProgress(20);

    try {
      const res = await api.datasets.upload(file, file.name.replace(/\.[^/.]+$/, ""));
      const dsId = res.dataset_id || res.dataset?.id || "";
      if (res.job_id) {
        await pollJob(res.job_id, dsId);
      } else {
        setUploading(false);
        setUploadProgress(null);
        if (dsId) onDatasetAdded(dsId);
      }
    } catch (err: unknown) {
      setUploading(false);
      setUploadProgress(null);
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSyncOnchain = async () => {
    if (!onchainAddress.trim()) return;
    setSyncingOnchain(true);
    setUploadError(null);
    try {
      const res = await api.datasets.syncOnchain(onchainAddress.trim());
      if (res.job_id) {
        // Poll job
        const interval = setInterval(async () => {
          try {
            const job = await api.jobs.get(res.job_id);
            if (job.status === "completed") {
              clearInterval(interval);
              setSyncingOnchain(false);
              setShowOnchainInput(false);
              setOnchainAddress("");
              // Datasets will be reloaded
              const dsList = await api.datasets.list();
              const found = dsList.find((d) => d.name.includes(onchainAddress.slice(0, 8)));
              if (found) onDatasetAdded(found.id);
            } else if (job.status === "failed") {
              clearInterval(interval);
              setSyncingOnchain(false);
              setUploadError(job.error || "On-chain sync failed");
            }
          } catch {
            clearInterval(interval);
            setSyncingOnchain(false);
          }
        }, 1500);
      }
    } catch (err: unknown) {
      setSyncingOnchain(false);
      setUploadError(err instanceof Error ? err.message : "On-chain sync failed");
    }
  };

  return (
    <aside className="w-72 flex-shrink-0 border-r border-zinc-800 bg-zinc-950/90 flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="p-4 border-b border-zinc-800/80">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-cyan-400" />
            <h2 className="text-xs font-mono font-semibold tracking-wider uppercase text-zinc-300">
              Data Sources
            </h2>
          </div>
          <span className="text-[11px] font-mono text-zinc-500">
            {datasets.length} active
          </span>
        </div>

        {/* Upload Actions */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:border-zinc-600 transition disabled:opacity-50"
          >
            {uploading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />
            ) : (
              <Upload className="h-3.5 w-3.5 text-cyan-400" />
            )}
            <span>Upload File</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx"
            onChange={handleFileUpload}
            className="hidden"
          />

          <button
            onClick={() => setShowOnchainInput(!showOnchainInput)}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:border-zinc-600 transition"
          >
            <LinkIcon className="h-3.5 w-3.5 text-indigo-400" />
            <span>Solana Sync</span>
          </button>
        </div>

        {/* On-chain Sync Dropdown */}
        {showOnchainInput && (
          <div className="mt-3 p-2.5 rounded-lg border border-zinc-800 bg-zinc-900/90 space-y-2">
            <label className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 block">
              Treasury / Account Address
            </label>
            <input
              type="text"
              placeholder="e.g. 7xKX...4aB"
              value={onchainAddress}
              onChange={(e) => setOnchainAddress(e.target.value)}
              className="w-full rounded bg-zinc-950 border border-zinc-700 px-2 py-1 text-xs font-mono text-zinc-200 focus:outline-none focus:border-cyan-500"
            />
            <button
              onClick={handleSyncOnchain}
              disabled={syncingOnchain || !onchainAddress.trim()}
              className="w-full flex items-center justify-center gap-1 rounded bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-500 transition disabled:opacity-50"
            >
              {syncingOnchain ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Syncing RPC...</span>
                </>
              ) : (
                <span>Sync On-chain Data</span>
              )}
            </button>
          </div>
        )}

        {/* Progress or error */}
        {uploading && uploadProgress !== null && (
          <div className="mt-3 space-y-1">
            <div className="flex justify-between text-[10px] font-mono text-zinc-400">
              <span>Ingesting & profiling...</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="h-1 w-full bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-cyan-400 transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {uploadError && (
          <div className="mt-2.5 flex items-start gap-1.5 rounded-lg border border-rose-500/30 bg-rose-950/20 p-2 text-[11px] text-rose-300">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
            <span className="leading-tight">{uploadError}</span>
          </div>
        )}
      </div>

      {/* Datasets List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {datasets.length === 0 ? (
          <div className="p-6 text-center text-zinc-500 text-xs">
            No datasets uploaded yet. Upload a CSV/XLSX file or sync a Solana treasury address.
          </div>
        ) : (
          datasets.map((dataset) => {
            const isSelected = dataset.id === activeDatasetId;
            return (
              <div
                key={dataset.id}
                onClick={() => onSelectDataset(dataset.id)}
                className={`group cursor-pointer rounded-xl border p-3 transition ${
                  isSelected
                    ? "border-cyan-500/50 bg-cyan-950/20 shadow-sm"
                    : "border-zinc-800/80 bg-zinc-900/40 hover:border-zinc-700 hover:bg-zinc-900/70"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <FileSpreadsheet
                      className={`h-4 w-4 ${
                        isSelected ? "text-cyan-400" : "text-zinc-400"
                      }`}
                    />
                    <span className="text-xs font-semibold text-zinc-200 truncate max-w-[140px]">
                      {dataset.name}
                    </span>
                  </div>
                  {dataset.source_type === "onchain_rpc" ? (
                    <span className="rounded bg-indigo-950/60 border border-indigo-500/30 px-1.5 py-0.5 text-[9px] font-mono text-indigo-400">
                      ON-CHAIN
                    </span>
                  ) : (
                    <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[9px] font-mono text-zinc-400">
                      CSV
                    </span>
                  )}
                </div>

                <div className="mt-2.5 flex items-center justify-between text-[11px] font-mono text-zinc-400">
                  <span>
                    {dataset.row_count !== undefined
                      ? `${dataset.row_count.toLocaleString()} rows`
                      : "Ready"}
                  </span>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenDictionary(dataset.id);
                    }}
                    title="View Data Dictionary & Schema"
                    className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-cyan-400 transition"
                  >
                    <Table className="h-3 w-3" />
                    <span>Schema</span>
                  </button>
                </div>

                {dataset.version_hash && (
                  <div className="mt-1.5 text-[10px] font-mono text-zinc-500 truncate">
                    root: {dataset.version_hash.slice(0, 16)}...
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
