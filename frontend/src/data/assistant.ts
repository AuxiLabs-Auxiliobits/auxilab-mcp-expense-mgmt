import { composeAnswer, retrieve, type PolicyClause } from "./policy-kb";

/**
 * Simulated streaming RAG run for the Policy Assistant. Emits the same shape a
 * real LangGraph/SSE stream would: a retrieval step, the cited clauses, then the
 * answer token-by-token. Abortable via an AbortSignal (stop / regenerate).
 */
export type AssistantEvent =
  | { type: "step"; text: string }
  | { type: "citations"; clauses: PolicyClause[] }
  | { type: "token"; text: string }
  | { type: "done"; full: string };

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export async function* streamPolicyAnswer(
  query: string,
  agencyId: string,
  agencyName: string,
  signal?: AbortSignal,
): AsyncGenerator<AssistantEvent> {
  yield { type: "step", text: "Retrieving agency policy (hybrid + semantic)…" };
  await delay(700, signal);

  const clauses = retrieve(query, agencyId);
  yield { type: "citations", clauses };

  yield {
    type: "step",
    text: clauses.length
      ? `Grounding answer in ${clauses.length} clause${clauses.length === 1 ? "" : "s"}…`
      : "No matching clause — preparing guidance…",
  };
  await delay(500, signal);

  const full = composeAnswer(query, clauses, agencyName);
  const tokens = full.match(/\s+|\S+/g) ?? [full];
  for (const tok of tokens) {
    yield { type: "token", text: tok };
    await delay(14, signal);
  }
  yield { type: "done", full };
}

export const SUGGESTED_PROMPTS = [
  "What's the Wi-Fi reimbursement cap?",
  "What are the meal and hotel limits?",
  "Do I need a receipt, and over what amount?",
  "When is the submission deadline?",
  "How are duplicates detected?",
];
