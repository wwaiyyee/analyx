"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  api,
  FindingItem,
  ReportItem,
} from "@/lib/api";
import {
  streamChat,
  AgentEvent,
  QuestionCard,
} from "@/lib/sse";
import { FindingCard } from "./finding-card";
import { VegaWrapper } from "@/charts/vega-wrapper";
import { StatusLine } from "./status-line";
import { QuestionCards } from "./question-cards";
import {
  Send,
  Sparkles,
  FileText,
  User,
  Bot,
  Loader2,
  AlertCircle,
} from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  findings?: FindingItem[];
  charts?: Array<{ id: string; title: string; vega_spec_json: string; evidence_id?: string }>;
}

interface ChatProps {
  sessionId: string;
  onOpenWhy: (finding: FindingItem) => void;
  onReportGenerated: (report: ReportItem) => void;
}

const QUICK_PROMPTS = [
  "What was total outflow last complete month?",
  "Top 5 counterparties by outflow",
  "Month-over-month net flow change",
  "Check for outflow anomalies or spikes",
];

export function Chat({
  sessionId,
  onOpenWhy,
  onReportGenerated,
}: ChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);

  // Live SSE state
  const [statusText, setStatusText] = useState<string | null>(null);
  const [planSteps, setPlanSteps] = useState<string[]>([]);
  const [activeQuestions, setActiveQuestions] = useState<QuestionCard[]>([]);
  const [currentStreamFindings, setCurrentStreamFindings] = useState<FindingItem[]>([]);
  const [currentStreamCharts, setCurrentStreamCharts] = useState<Array<{ id: string; title: string; vega_spec_json: string; evidence_id?: string }>>([]);
  const [currentDelta, setCurrentDelta] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusText, currentDelta, activeQuestions]);

  // Load existing session history on mount
  useEffect(() => {
    if (!sessionId) return;
    let mounted = true;

    api.sessions
      .get(sessionId)
      .then((detail) => {
        if (!mounted) return;
        const mapped: ChatMessage[] = (detail.messages || []).map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          findings: m.role === "assistant" ? detail.findings : [],
        }));
        setMessages(mapped);
      })
      .catch((err) => {
        console.warn("Could not load past session messages:", err);
      });

    return () => {
      mounted = false;
    };
  }, [sessionId]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || streaming) return;

    setInputText("");
    const userMsgId = `user_${Date.now()}`;
    setMessages((prev) => [...prev, { id: userMsgId, role: "user", content: text }]);

    // Reset turn state
    setStreaming(true);
    setStatusText("Initializing analysis turn...");
    setPlanSteps([]);
    setActiveQuestions([]);
    setCurrentStreamFindings([]);
    setCurrentStreamCharts([]);
    setCurrentDelta("");

    let accumulatedDelta = "";
    const accumulatedFindings: FindingItem[] = [];
    const accumulatedCharts: Array<{ id: string; title: string; vega_spec_json: string; evidence_id?: string }> = [];

    await streamChat({
      sessionId,
      text,
      onEvent: (event: AgentEvent) => {
        switch (event.type) {
          case "status":
            setStatusText(event.data.text);
            break;
          case "plan":
            setPlanSteps(event.data.steps);
            break;
          case "question_cards":
            setActiveQuestions(event.data.questions);
            break;
          case "finding": {
            const f = event.data.finding as FindingItem;
            accumulatedFindings.push(f);
            setCurrentStreamFindings([...accumulatedFindings]);
            break;
          }
          case "chart": {
            accumulatedCharts.push(event.data.chart);
            setCurrentStreamCharts([...accumulatedCharts]);
            break;
          }
          case "answer_delta": {
            accumulatedDelta += event.data.delta;
            setCurrentDelta(accumulatedDelta);
            break;
          }
          case "done": {
            setStatusText(null);
            break;
          }
          case "error": {
            setStatusText(`Error: ${event.data.message}`);
            break;
          }
        }
      },
      onError: (err) => {
        setStreaming(false);
        setStatusText(`Error: ${err.message}`);
      },
      onDone: () => {
        setStreaming(false);
        const assistantMsgId = `asst_${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: "assistant",
            content: accumulatedDelta || "Analysis completed.",
            findings: accumulatedFindings,
            charts: accumulatedCharts,
          },
        ]);
        setStatusText(null);
        setCurrentDelta("");
        setCurrentStreamFindings([]);
        setCurrentStreamCharts([]);
      },
    });
  };

  const handleClarificationAnswers = (answers: Record<string, string>) => {
    setActiveQuestions([]);
    const formatted = Object.entries(answers)
      .map(([k, v]) => `${k}: ${v}`)
      .join(", ");
    handleSendMessage(`Clarification response: ${formatted}`);
  };

  const handleCompileReport = async () => {
    if (!sessionId || generatingReport) return;
    setGeneratingReport(true);
    try {
      const rep = await api.reports.generate(sessionId, "Verified Analysis Report");
      onReportGenerated(rep);
    } catch (err) {
      console.error("Failed to generate report:", err);
    } finally {
      setGeneratingReport(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-4rem)] bg-zinc-950">
      {/* Chat Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {messages.length === 0 && !streaming && (
          <div className="my-auto flex flex-col items-center justify-center text-center p-8 max-w-md mx-auto">
            <div className="h-12 w-12 rounded-2xl bg-cyan-500/10 flex items-center justify-center text-cyan-400 mb-4 shadow-inner">
              <Bot className="h-6 w-6" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-100">
              Analyx Deterministic Analyst
            </h3>
            <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
              Ask any question about your data. The engine compiles strict SQL queries
              and cryptographically verifies all claims before answering.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 max-w-3xl ${
              msg.role === "user" ? "ml-auto justify-end" : "mr-auto"
            }`}
          >
            {msg.role === "assistant" && (
              <div className="h-7 w-7 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 flex-shrink-0 mt-0.5">
                <Bot className="h-4 w-4" />
              </div>
            )}

            <div
              className={`space-y-3 ${
                msg.role === "user"
                  ? "rounded-2xl bg-gradient-to-r from-cyan-600 to-indigo-600 px-4 py-2.5 text-xs text-white shadow-md max-w-xl"
                  : "w-full space-y-3"
              }`}
            >
              {msg.role === "assistant" ? (
                <>
                  {/* Composed text answer */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 text-xs text-zinc-200 leading-relaxed">
                    {msg.content}
                  </div>

                  {/* Findings */}
                  {msg.findings && msg.findings.length > 0 && (
                    <div className="space-y-2 pt-1">
                      {msg.findings.map((f) => (
                        <FindingCard
                          key={f.id}
                          finding={f}
                          onOpenWhy={onOpenWhy}
                        />
                      ))}
                    </div>
                  )}

                  {/* Charts */}
                  {msg.charts && msg.charts.length > 0 && (
                    <div className="space-y-3 pt-1">
                      {msg.charts.map((ch) => (
                        <VegaWrapper
                          key={ch.id}
                          spec={ch.vega_spec_json}
                          title={ch.title}
                          evidenceId={ch.evidence_id}
                          onOpenWhy={(evId) =>
                            onOpenWhy({
                              id: ch.id,
                              session_id: sessionId,
                              claim: ch.title,
                              claim_type: "trend",
                              status: "supported",
                              evidence_id: evId,
                              numbers_grounded: true,
                            })
                          }
                        />
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="font-sans text-xs leading-relaxed">{msg.content}</div>
              )}
            </div>

            {msg.role === "user" && (
              <div className="h-7 w-7 rounded-lg bg-zinc-800 flex items-center justify-center text-zinc-400 flex-shrink-0 mt-0.5">
                <User className="h-4 w-4" />
              </div>
            )}
          </div>
        ))}

        {/* Live Streaming Assistant Response */}
        {streaming && (
          <div className="flex gap-3 max-w-3xl mr-auto w-full">
            <div className="h-7 w-7 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 flex-shrink-0 mt-0.5">
              <Bot className="h-4 w-4" />
            </div>

            <div className="w-full space-y-3">
              {/* Activity Status Line */}
              <StatusLine
                statusText={statusText}
                active={streaming}
                planSteps={planSteps}
              />

              {/* Clarification Questions Cards */}
              {activeQuestions.length > 0 && (
                <QuestionCards
                  questions={activeQuestions}
                  onSubmitAnswers={handleClarificationAnswers}
                />
              )}

              {/* Streaming Answer Deltas */}
              {currentDelta && (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 text-xs text-zinc-200 leading-relaxed">
                  {currentDelta}
                </div>
              )}

              {/* Streamed Findings */}
              {currentStreamFindings.map((f) => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  onOpenWhy={onOpenWhy}
                />
              ))}

              {/* Streamed Charts */}
              {currentStreamCharts.map((ch) => (
                <VegaWrapper
                  key={ch.id}
                  spec={ch.vega_spec_json}
                  title={ch.title}
                  evidenceId={ch.evidence_id}
                  onOpenWhy={() => {}}
                />
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Bar */}
      <div className="px-4 py-2 border-t border-zinc-800/60 bg-zinc-950/60 flex items-center gap-2 overflow-x-auto">
        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 flex-shrink-0">
          Suggested:
        </span>
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => handleSendMessage(prompt)}
            disabled={streaming}
            className="flex-shrink-0 rounded-full border border-zinc-800 bg-zinc-900/80 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-cyan-500/40 hover:text-cyan-300 transition disabled:opacity-40"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Input Box & Report Button */}
      <div className="p-4 border-t border-zinc-800 bg-zinc-900/40">
        <div className="flex items-center gap-3">
          <button
            onClick={handleCompileReport}
            disabled={generatingReport || streaming || messages.length === 0}
            title="Compile verified session findings into a cryptographically anchored markdown report"
            className="flex items-center gap-1.5 rounded-xl border border-indigo-500/40 bg-indigo-950/40 px-3.5 py-3 text-xs font-semibold text-indigo-300 hover:bg-indigo-900/60 hover:text-white transition disabled:opacity-40 flex-shrink-0"
          >
            {generatingReport ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FileText className="h-4 w-4" />
            )}
            <span className="hidden sm:inline">Compile Report</span>
          </button>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex-1 flex items-center gap-2"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Ask an analytical question (e.g. 'What was total outflow in November?')..."
              disabled={streaming}
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-3 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-cyan-500 transition"
            />
            <button
              type="submit"
              disabled={streaming || !inputText.trim()}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 text-white shadow-md shadow-cyan-500/20 hover:opacity-95 transition disabled:opacity-40 flex-shrink-0"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
