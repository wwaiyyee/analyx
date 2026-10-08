/**
 * Analyx Server-Sent Events (SSE) Stream Consumer
 * Handles real-time streaming of agent status, plans, findings, charts, and answer deltas.
 */

import { API_BASE_URL, getStoredToken } from "./api";

export type AgentEventType =
  | "status"
  | "plan"
  | "question_cards"
  | "finding"
  | "chart"
  | "answer_delta"
  | "assumption"
  | "done"
  | "error";

export interface StatusEventData {
  text: string;
}

export interface PlanEventData {
  steps: string[];
}

export interface QuestionCard {
  id: string;
  question: string;
  context?: string;
  choices: string[];
  default_choice?: string;
}

export interface QuestionCardsEventData {
  questions: QuestionCard[];
}

export interface FindingEventData {
  finding: {
    id: string;
    session_id: string;
    claim: string;
    claim_type: string;
    status: "supported" | "partially_supported" | "insufficient" | "not_applicable";
    evidence_id?: string;
    numbers_grounded: boolean;
    validation_json?: string;
  };
}

export interface ChartEventData {
  chart: {
    id: string;
    session_id: string;
    title: string;
    vega_spec_json: string;
    evidence_id?: string;
  };
}

export interface AnswerDeltaEventData {
  delta: string;
}

export interface AssumptionEventData {
  assumption: {
    id: string;
    name: string;
    value: string;
    rationale?: string;
    source: string;
  };
}

export interface DoneEventData {
  session_id: string;
  tool_calls_used: number;
}

export interface ErrorEventData {
  code: string;
  message: string;
}

export type AgentEvent =
  | { type: "status"; data: StatusEventData }
  | { type: "plan"; data: PlanEventData }
  | { type: "question_cards"; data: QuestionCardsEventData }
  | { type: "finding"; data: FindingEventData }
  | { type: "chart"; data: ChartEventData }
  | { type: "answer_delta"; data: AnswerDeltaEventData }
  | { type: "assumption"; data: AssumptionEventData }
  | { type: "done"; data: DoneEventData }
  | { type: "error"; data: ErrorEventData };

export interface StreamChatOptions {
  sessionId: string;
  text: string;
  token?: string | null;
  signal?: AbortSignal;
  onEvent: (event: AgentEvent) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
}

/**
 * Stream conversational analysis response from the agent via SSE.
 */
export async function streamChat({
  sessionId,
  text,
  token,
  signal,
  onEvent,
  onError,
  onDone,
}: StreamChatOptions): Promise<void> {
  const authToken = token || getStoredToken();
  const url = `${API_BASE_URL}/sessions/${sessionId}/messages`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };

  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  try {
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ text }),
      signal,
    });

    if (!response.ok) {
      let errMessage = `Chat request failed with HTTP ${response.status}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          errMessage = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fallback message
      }
      const err = new Error(errMessage);
      if (onError) onError(err);
      return;
    }

    if (!response.body) {
      const err = new Error("Response body is null (streaming not supported)");
      if (onError) onError(err);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      // The last element is either incomplete or empty
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        let payloadStr: string | null = null;
        if (trimmed.startsWith("data:")) {
          payloadStr = trimmed.slice(5).trim();
        }

        if (payloadStr) {
          try {
            const rawParsed = JSON.parse(payloadStr);
            if (rawParsed && rawParsed.type) {
              const event = rawParsed as AgentEvent;
              onEvent(event);
              if (event.type === "error" && onError) {
                onError(new Error(event.data.message));
              }
            }
          } catch (jsonErr) {
            console.warn("Failed to parse SSE line JSON:", payloadStr, jsonErr);
          }
        }
      }
    }

    // Process any remaining bytes in buffer
    const remainingTrimmed = buffer.trim();
    if (remainingTrimmed && remainingTrimmed.startsWith("data:")) {
      const payloadStr = remainingTrimmed.slice(5).trim();
      try {
        const rawParsed = JSON.parse(payloadStr);
        if (rawParsed && rawParsed.type) {
          onEvent(rawParsed as AgentEvent);
        }
      } catch {
        // ignore trailing invalid chunk
      }
    }

    if (onDone) {
      onDone();
    }
  } catch (err: unknown) {
    if (signal?.aborted) {
      return;
    }
    const error = err instanceof Error ? err : new Error(String(err));
    if (onError) {
      onError(error);
    } else {
      console.error("SSE stream error:", error);
    }
  }
}
