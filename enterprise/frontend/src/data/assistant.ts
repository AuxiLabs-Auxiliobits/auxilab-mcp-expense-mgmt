import { composeAnswer, retrieve, type PolicyClause } from "./policy-kb";
import { queryPolicyAssistant } from "./api";
import { USE_BACKEND } from "./http";

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

  // Backend path: real RAG over the agency policy via Azure Foundry (offline composer when
  // Azure isn't configured). The answer streams in token-by-token for the same UX.
  if (USE_BACKEND) {
    try {
      const res = await queryPolicyAssistant(query);
      yield { type: "citations", clauses: res.citations };
      yield {
        type: "step",
        text: res.citations.length
          ? `Grounding answer in ${res.citations.length} clause${res.citations.length === 1 ? "" : "s"}…`
          : "Preparing guidance…",
      };
      await delay(250, signal);
      const tokens = res.answer.match(/\s+|\S+/g) ?? [res.answer];
      for (const tok of tokens) {
        yield { type: "token", text: tok };
        await delay(12, signal);
      }
      yield { type: "done", full: res.answer };
      return;
    } catch (err) {
      if ((err as Error)?.name === "AbortError") throw err;
      // Backend unreachable → fall back to the offline knowledge base below.
    }
  }

  await delay(500, signal);
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
