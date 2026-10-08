"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  DataDictionaryEntry,
} from "@/lib/api";
import {
  X,
  Save,
  Table,
  ShieldAlert,
  CheckCircle2,
  Loader2,
  Info,
} from "lucide-react";

interface DictionaryEditorProps {
  datasetId: string;
  isOpen: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

const SEMANTIC_ROLES = [
  "time",
  "measure",
  "dimension",
  "entity_id",
  "currency",
  "status",
  "unknown",
];

const MASKING_RULES = [
  "none",
  "redact",
  "mask_email",
  "mask_phone",
  "hash_sha256",
];

export function DictionaryEditor({
  datasetId,
  isOpen,
  onClose,
  onSaved,
}: DictionaryEditorProps) {
  const [entries, setEntries] = useState<DataDictionaryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!isOpen || !datasetId) return;

    let mounted = true;
    setLoading(true);
    setError(null);
    setSaveSuccess(false);

    api.datasets
      .getDictionary(datasetId)
      .then((data) => {
        if (mounted) {
          setEntries(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || "Failed to load data dictionary");
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [isOpen, datasetId]);

  const handleFieldChange = (
    index: number,
    field: keyof DataDictionaryEntry,
    value: unknown
  ) => {
    setEntries((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.datasets.updateDictionary(datasetId, entries);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
      if (onSaved) onSaved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update dictionary");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-5xl max-h-[90vh] flex flex-col rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4 bg-zinc-900/50">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400">
              <Table className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">
                Data Dictionary & Semantic Schema
              </h2>
              <p className="text-xs text-zinc-400">
                Verify semantic roles, metric units, and PII masking rules.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Table */}
        <div className="flex-1 overflow-auto p-6">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
            </div>
          ) : error ? (
            <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-4 text-xs text-rose-300">
              {error}
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-zinc-800">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-zinc-800 bg-zinc-900/80 font-mono uppercase text-[10px] text-zinc-400">
                  <tr>
                    <th className="px-4 py-3">Column Name</th>
                    <th className="px-4 py-3">Inferred Type</th>
                    <th className="px-4 py-3">Semantic Role</th>
                    <th className="px-4 py-3">Unit</th>
                    <th className="px-4 py-3">PII</th>
                    <th className="px-4 py-3">Masking Rule</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 font-mono">
                  {entries.map((entry, idx) => (
                    <tr
                      key={entry.id || entry.column_name}
                      className="hover:bg-zinc-900/40 transition"
                    >
                      {/* Name */}
                      <td className="px-4 py-3 font-semibold text-zinc-200">
                        {entry.column_name}
                      </td>

                      {/* Data Type */}
                      <td className="px-4 py-3 text-zinc-400">
                        <span className="rounded bg-zinc-800/80 px-2 py-0.5 text-[10px]">
                          {entry.data_type}
                        </span>
                      </td>

                      {/* Semantic Role */}
                      <td className="px-4 py-3">
                        <select
                          value={entry.semantic_role}
                          onChange={(e) =>
                            handleFieldChange(idx, "semantic_role", e.target.value)
                          }
                          className="rounded bg-zinc-900 border border-zinc-700 px-2 py-1 text-xs text-cyan-400 font-sans focus:outline-none focus:border-cyan-500"
                        >
                          {SEMANTIC_ROLES.map((role) => (
                            <option key={role} value={role}>
                              {role}
                            </option>
                          ))}
                        </select>
                      </td>

                      {/* Unit */}
                      <td className="px-4 py-3">
                        <input
                          type="text"
                          value={entry.unit || ""}
                          placeholder="e.g. USD, SOL"
                          onChange={(e) =>
                            handleFieldChange(idx, "unit", e.target.value)
                          }
                          className="w-24 rounded bg-zinc-900 border border-zinc-700 px-2 py-1 text-xs text-zinc-300 font-sans focus:outline-none focus:border-cyan-500"
                        />
                      </td>

                      {/* PII Toggle */}
                      <td className="px-4 py-3">
                        <label className="inline-flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={entry.is_pii}
                            onChange={(e) =>
                              handleFieldChange(idx, "is_pii", e.target.checked)
                            }
                            className="rounded border-zinc-700 text-rose-500 focus:ring-0"
                          />
                          {entry.is_pii ? (
                            <span className="text-rose-400 font-sans text-[11px] flex items-center gap-1">
                              <ShieldAlert className="h-3 w-3" /> PII
                            </span>
                          ) : (
                            <span className="text-zinc-500 font-sans text-[11px]">
                              Safe
                            </span>
                          )}
                        </label>
                      </td>

                      {/* Masking Rule */}
                      <td className="px-4 py-3">
                        <select
                          value={entry.masking_rule || "none"}
                          disabled={!entry.is_pii}
                          onChange={(e) =>
                            handleFieldChange(idx, "masking_rule", e.target.value)
                          }
                          className="rounded bg-zinc-900 border border-zinc-700 px-2 py-1 text-xs text-zinc-300 font-sans disabled:opacity-30 focus:outline-none"
                        >
                          {MASKING_RULES.map((rule) => (
                            <option key={rule} value={rule}>
                              {rule}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-zinc-800 px-6 py-4 bg-zinc-900/50">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Info className="h-4 w-4 text-cyan-400" />
            <span>
              All analysis specs strictly enforce these semantic roles and units.
            </span>
          </div>

          <div className="flex items-center gap-3">
            {saveSuccess && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                <CheckCircle2 className="h-4 w-4" />
                Dictionary updated!
              </span>
            )}

            <button
              onClick={onClose}
              className="rounded-lg border border-zinc-700 px-4 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-800 transition"
            >
              Cancel
            </button>

            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:opacity-95 transition disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              <span>Save Changes</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
