"use client";

import React, { useState } from "react";
import { QuestionCard } from "@/lib/sse";
import { HelpCircle, Check, Sparkles } from "lucide-react";

interface QuestionCardsProps {
  questions: QuestionCard[];
  onSubmitAnswers: (answers: Record<string, string>) => void;
}

export function QuestionCards({
  questions,
  onSubmitAnswers,
}: QuestionCardsProps) {
  const [selectedChoices, setSelectedChoices] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    questions.forEach((q) => {
      initial[q.id] = q.default_choice || q.choices[0] || "Use your best guess and flag it";
    });
    return initial;
  });

  const handleSelect = (questionId: string, choice: string) => {
    setSelectedChoices((prev) => ({ ...prev, [questionId]: choice }));
  };

  const handleSubmit = () => {
    onSubmitAnswers(selectedChoices);
  };

  const handleBestGuessAll = () => {
    const bestGuessAnswers: Record<string, string> = {};
    questions.forEach((q) => {
      bestGuessAnswers[q.id] = "Use your best guess and flag it";
    });
    onSubmitAnswers(bestGuessAnswers);
  };

  if (!questions || questions.length === 0) return null;

  return (
    <div className="rounded-2xl border border-indigo-500/30 bg-indigo-950/20 p-5 shadow-lg backdrop-blur-sm space-y-4">
      <div className="flex items-center justify-between border-b border-indigo-500/20 pb-3">
        <div className="flex items-center gap-2">
          <HelpCircle className="h-4 w-4 text-indigo-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-indigo-300">
            Clarification Needed ({questions.length} questions)
          </h3>
        </div>
        <button
          onClick={handleBestGuessAll}
          className="flex items-center gap-1.5 rounded-lg border border-indigo-500/40 bg-indigo-900/40 px-2.5 py-1 text-xs font-medium text-indigo-200 hover:bg-indigo-800/60 transition"
        >
          <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
          <span>Use best guess & flag</span>
        </button>
      </div>

      <div className="space-y-4">
        {questions.map((q, idx) => (
          <div key={q.id || idx} className="space-y-2">
            <p className="text-xs font-medium text-zinc-200 leading-snug">
              {idx + 1}. {q.question}
            </p>

            {q.context && (
              <p className="text-[11px] text-zinc-400 font-sans italic">
                Context: {q.context}
              </p>
            )}

            <div className="flex flex-wrap gap-2 pt-1">
              {q.choices.map((choice) => {
                const isSelected = selectedChoices[q.id] === choice;
                return (
                  <button
                    key={choice}
                    onClick={() => handleSelect(q.id, choice)}
                    className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                      isSelected
                        ? "border-cyan-400 bg-cyan-950/60 text-cyan-200 shadow-sm"
                        : "border-zinc-800 bg-zinc-900/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                    }`}
                  >
                    {isSelected && <Check className="h-3 w-3 text-cyan-400" />}
                    <span>{choice}</span>
                  </button>
                );
              })}

              {/* Standard fallback option */}
              {!q.choices.includes("Use your best guess and flag it") && (
                <button
                  onClick={() =>
                    handleSelect(q.id, "Use your best guess and flag it")
                  }
                  className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                    selectedChoices[q.id] === "Use your best guess and flag it"
                      ? "border-indigo-400 bg-indigo-950/60 text-indigo-200 shadow-sm"
                      : "border-zinc-800/80 bg-zinc-900/60 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300"
                  }`}
                >
                  {selectedChoices[q.id] === "Use your best guess and flag it" && (
                    <Check className="h-3 w-3 text-indigo-400" />
                  )}
                  <span>Use best guess & flag it</span>
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end pt-2 border-t border-indigo-500/20">
        <button
          onClick={handleSubmit}
          className="rounded-lg bg-gradient-to-r from-cyan-500 to-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-cyan-500/20 hover:opacity-95 transition"
        >
          Confirm & Continue Analysis
        </button>
      </div>
    </div>
  );
}
