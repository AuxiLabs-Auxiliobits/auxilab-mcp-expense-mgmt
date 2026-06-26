"use client";

/**
 * Floating in-app AI Assistant.
 *
 * A conversational front-end over the MCP bridge (`POST /assistant/chat`). It holds no business
 * logic: it sends the user's message + an opaque `context` blob (conversation memory) and renders
 * the reply, the MCP tools that ran (explainability), and role/screen-aware suggestions. Every
 * action is performed by the backend through MCP tools, scoped to the signed-in user.
 */
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Icon } from "@/components/ui/icon";
import { Markdown } from "@/components/shared/markdown";
import { cn } from "@/lib/utils";
import {
  type AssistantContext,
  assistantEnabled,
  getAssistantSuggestions,
  sendAssistantChat,
} from "@/data/assistant-chat";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools?: string[];
  actions?: string[];
  confidence?: "high" | "medium" | "low";
}

const GREETING =
  "Hi! I'm your expense assistant. I can help with expenses, approvals, receipts, policy questions, and reports — all through the same secure actions you'd take yourself. What would you like to do?";

let _id = 0;
const nextId = () => `m${++_id}`;

function screenLabel(pathname: string): string {
  // e.g. /manager/approvals -> "manager", /employee/sheets -> "employee"
  const seg = pathname.split("/").filter(Boolean)[0] ?? "";
  return seg;
}

export function AssistantWidget({ role, pathname }: { role: string; pathname: string }) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [context, setContext] = useState<AssistantContext>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<Record<string, "up" | "down">>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to the latest message.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // On first open: greet + load screen-aware suggestions.
  useEffect(() => {
    if (!open || messages.length > 0) return;
    setMessages([{ id: nextId(), role: "assistant", content: GREETING }]);
    getAssistantSuggestions(screenLabel(pathname))
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, [open, pathname, messages.length]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    setInput("");
    setSuggestions([]);
    setMessages((m) => [...m, { id: nextId(), role: "user", content: trimmed }]);
    setLoading(true);
    abortRef.current = new AbortController();
    try {
      const res = await sendAssistantChat(trimmed, context, abortRef.current.signal);
      setContext(res.context);
      setSuggestions(res.suggestions ?? []);
      setMessages((m) => [
        ...m,
        {
          id: nextId(),
          role: "assistant",
          content: res.reply,
          tools: res.tools_used,
          actions: res.actions,
          confidence: res.confidence,
        },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setMessages((m) => [
        ...m,
        { id: nextId(), role: "assistant", content: `⚠️ ${msg}`, confidence: "low" },
      ]);
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  function exportConversation() {
    const md = messages
      .map((m) => `**${m.role === "user" ? "You" : "Assistant"}:** ${m.content}`)
      .join("\n\n---\n\n");
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "assistant-conversation.md";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Conversation exported");
  }

  function copyMessage(content: string) {
    navigator.clipboard.writeText(content);
    toast.success("Copied");
  }

  function rate(id: string, v: "up" | "down") {
    setFeedback((f) => ({ ...f, [id]: v }));
    toast(v === "up" ? "Thanks for the feedback!" : "Thanks — we'll use this to improve.");
  }

  if (!assistantEnabled) return null;

  return (
    <>
      {/* Floating launcher */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label="Open AI Assistant"
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-on-primary shadow-lg transition-transform hover:scale-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Icon name="smart_toy" className="text-[26px]" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div
          className={cn(
            "fixed z-50 flex flex-col overflow-hidden border border-outline-variant bg-surface text-on-surface shadow-2xl",
            "inset-0 rounded-none", // mobile: full-screen
            "sm:inset-auto sm:bottom-6 sm:right-6 sm:max-h-[90vh] sm:rounded-2xl",
            expanded
              ? "sm:h-[90vh] sm:w-[680px]" // expanded: roomier reading/working area
              : "sm:h-[600px] sm:max-h-[85vh] sm:w-[400px]",
          )}
          role="dialog"
          aria-label="AI Assistant"
        >
          {/* Header */}
          <div className="flex items-center gap-2 border-b border-outline-variant bg-surface-container-low px-4 py-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-primary">
              <Icon name="smart_toy" className="text-[18px]" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">AI Assistant</p>
              <p className="truncate text-xs capitalize text-on-surface-variant">{role} workspace</p>
            </div>
            <button
              onClick={() => setExpanded((v) => !v)}
              aria-label={expanded ? "Collapse assistant" : "Expand assistant"}
              title={expanded ? "Collapse" : "Expand"}
              className="hidden rounded-full p-1.5 text-on-surface-variant hover:bg-surface-container hover:text-on-surface sm:inline-flex"
            >
              <Icon
                name={expanded ? "close_fullscreen" : "open_in_full"}
                className="text-[18px]"
              />
            </button>
            <button
              onClick={exportConversation}
              aria-label="Export conversation"
              className="rounded-full p-1.5 text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
            >
              <Icon name="download" className="text-[18px]" />
            </button>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close assistant"
              className="rounded-full p-1.5 text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
            >
              <Icon name="close" className="text-[18px]" />
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {messages.map((m) => (
              <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm",
                    m.role === "user"
                      ? "bg-primary text-on-primary"
                      : "bg-surface-container-low text-on-surface",
                  )}
                >
                  {m.role === "assistant" ? (
                    <Markdown content={m.content} className="text-sm [&_p]:my-1" />
                  ) : (
                    <span className="whitespace-pre-wrap">{m.content}</span>
                  )}

                  {/* Explainability footer */}
                  {m.role === "assistant" && (m.tools?.length || m.confidence) && (
                    <div className="mt-2 border-t border-outline-variant/60 pt-2">
                      {!!m.tools?.length && (
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="text-[10px] uppercase tracking-wide text-on-surface-variant">
                            via
                          </span>
                          {m.tools.map((t) => (
                            <span
                              key={t}
                              className="rounded-full bg-surface-container px-2 py-0.5 font-mono text-[10px] text-on-surface-variant"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="mt-1.5 flex items-center gap-2">
                        {m.confidence && (
                          <span className="text-[10px] text-on-surface-variant">
                            confidence: {m.confidence}
                          </span>
                        )}
                        <span className="flex-1" />
                        <button
                          onClick={() => copyMessage(m.content)}
                          aria-label="Copy"
                          className="rounded p-1 text-on-surface-variant hover:bg-surface-container"
                        >
                          <Icon name="content_copy" className="text-[14px]" />
                        </button>
                        <button
                          onClick={() => rate(m.id, "up")}
                          aria-label="Helpful"
                          className={cn(
                            "rounded p-1 hover:bg-surface-container",
                            feedback[m.id] === "up" ? "text-primary" : "text-on-surface-variant",
                          )}
                        >
                          <Icon name="thumb_up" className="text-[14px]" filled={feedback[m.id] === "up"} />
                        </button>
                        <button
                          onClick={() => rate(m.id, "down")}
                          aria-label="Not helpful"
                          className={cn(
                            "rounded p-1 hover:bg-surface-container",
                            feedback[m.id] === "down" ? "text-error" : "text-on-surface-variant",
                          )}
                        >
                          <Icon name="thumb_down" className="text-[14px]" filled={feedback[m.id] === "down"} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {loading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1 rounded-2xl bg-surface-container-low px-4 py-3">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-on-surface-variant"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Suggestions */}
          {!loading && suggestions.length > 0 && (
            <div className="flex flex-wrap gap-1.5 border-t border-outline-variant px-4 py-2">
              {suggestions.slice(0, 4).map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-outline-variant bg-surface-container-low px-2.5 py-1 text-xs text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-end gap-2 border-t border-outline-variant bg-surface-container-low px-3 py-2.5"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={1}
              placeholder="Ask anything…"
              className="max-h-28 flex-1 resize-none bg-transparent px-1 py-1.5 text-sm text-on-surface outline-none placeholder:text-on-surface-variant"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Send"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary disabled:opacity-40"
            >
              <Icon name="arrow_upward" className="text-[18px]" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
