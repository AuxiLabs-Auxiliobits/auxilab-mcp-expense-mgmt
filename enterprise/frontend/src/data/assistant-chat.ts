/**
 * Client for the in-app AI Assistant (the MCP bridge: `POST /assistant/chat`).
 *
 * The assistant runs entirely server-side through the MCP tool layer — this module only carries
 * the user's message + an opaque `context` blob (host-owned conversation memory) back and forth.
 * Auth is attached automatically by `apiPost` (the signed-in user's bearer token), so every action
 * the assistant performs is scoped to that user by the backend.
 */
import { apiPost, USE_BACKEND } from "./http";

/** Opaque conversation state echoed back each turn — pending action, last numbered list, etc. */
export type AssistantContext = Record<string, unknown> | null;

export interface AssistantChatResponse {
  reply: string;
  tools_used: string[];
  actions: string[];
  suggestions: string[];
  needs: string[] | null;
  pending: Record<string, unknown> | null;
  context: AssistantContext;
  confidence: "high" | "medium" | "low";
}

export const assistantEnabled = USE_BACKEND;

export function sendAssistantChat(
  message: string,
  context: AssistantContext,
  signal?: AbortSignal,
): Promise<AssistantChatResponse> {
  return apiPost<AssistantChatResponse>("/assistant/chat", { message, context }, signal);
}

export function getAssistantSuggestions(screen: string | null): Promise<string[]> {
  return apiPost<{ suggestions: string[] }>("/assistant/suggestions", { screen }).then(
    (r) => r.suggestions ?? [],
  );
}
