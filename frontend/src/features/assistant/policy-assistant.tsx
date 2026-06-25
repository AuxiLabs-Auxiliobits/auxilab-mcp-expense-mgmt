"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useCurrentUser } from "@/data/hooks";
import { streamPolicyAnswer, SUGGESTED_PROMPTS } from "@/data/assistant";
import type { PolicyClause } from "@/data/policy-kb";
import type { Role } from "@/data/types";
import { Markdown } from "@/components/shared/markdown";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  clauses?: PolicyClause[];
  step?: string;
  streaming?: boolean;
  error?: boolean;
}

let idSeq = 0;
const nextId = () => `m${++idSeq}-${Math.floor(Math.random() * 1e6)}`;

function prettyAgency(agencyId: string) {
  const raw = agencyId.replace(/^AGY-/, "").toLowerCase();
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export function PolicyAssistant({ role }: { role: Role }) {
  const { data: user } = useCurrentUser(role);
  const agencyId = user?.agencyId ?? "AGY-CRISPIN";
  // Prefer the real agency name (never expose the raw agency id in the UI).
  const agencyName = user?.agencyName || prettyAgency(agencyId);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function patch(id: string, fn: (m: ChatMessage) => ChatMessage) {
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));
  }

  async function runStream(question: string, assistantId: string) {
    const ac = new AbortController();
    abortRef.current = ac;
    setStreaming(true);
    try {
      for await (const ev of streamPolicyAnswer(question, agencyId, agencyName, ac.signal)) {
        if (ev.type === "step") patch(assistantId, (m) => ({ ...m, step: ev.text }));
        else if (ev.type === "citations") patch(assistantId, (m) => ({ ...m, clauses: ev.clauses }));
        else if (ev.type === "token")
          patch(assistantId, (m) => ({ ...m, content: m.content + ev.text, step: undefined }));
        else if (ev.type === "done")
          patch(assistantId, (m) => ({ ...m, content: ev.full, streaming: false, step: undefined }));
      }
    } catch (err) {
      if ((err as Error)?.name === "AbortError") {
        patch(assistantId, (m) => ({ ...m, streaming: false, step: undefined }));
      } else {
        patch(assistantId, (m) => ({
          ...m,
          streaming: false,
          step: undefined,
          error: true,
          content: m.content || "Sorry — I couldn't complete that request. Please try again.",
        }));
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function ask(question: string) {
    const q = question.trim();
    if (!q || streaming) return;
    const assistantId = nextId();
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: q },
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);
    setInput("");
    setAttachments([]);
    void runStream(q, assistantId);
  }

  function regenerate() {
    if (streaming) return;
    // find last user message
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    const assistantId = nextId();
    // drop the trailing assistant message, add a fresh one
    setMessages((prev) => {
      const trimmed = prev[prev.length - 1]?.role === "assistant" ? prev.slice(0, -1) : prev;
      return [...trimmed, { id: assistantId, role: "assistant", content: "", streaming: true }];
    });
    void runStream(lastUser.content, assistantId);
  }

  function stop() {
    abortRef.current?.abort();
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  }

  function onPickFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const names = Array.from(e.target.files ?? []).map((f) => f.name);
    if (names.length) setAttachments((p) => [...p, ...names]);
    if (fileRef.current) fileRef.current.value = "";
  }

  function voiceInput() {
    const SR =
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognitionLike })
        .webkitSpeechRecognition ??
      (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionLike }).SpeechRecognition;
    if (!SR) {
      toast("Voice input isn't supported in this browser.");
      return;
    }
    const rec = new SR();
    rec.lang = "en-US";
    rec.onresult = (e: { results: { 0: { 0: { transcript: string } } } }) => {
      setInput((prev) => (prev ? `${prev} ` : "") + e.results[0][0].transcript);
    };
    rec.start();
    toast("Listening…");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask(input);
    }
  }

  const empty = messages.length === 0;
  const lastAssistantId = [...messages].reverse().find((m) => m.role === "assistant")?.id;

  return (
    <div className="flex h-[calc(100dvh-4rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-outline-variant px-gutter py-3 md:px-margin-page">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Icon name="smart_toy" />
          </div>
          <div>
            <h2 className="text-body-lg font-semibold text-on-surface">Policy Assistant</h2>
            <p className="font-mono text-label-sm text-on-surface-variant">
              RAG over {agencyName} policy · cited answers
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setMessages([])} disabled={streaming}>
            <Icon name="restart_alt" /> New chat
          </Button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="scrollbar-thin flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-gutter py-6 md:px-margin-page">
          {empty ? (
            <div className="flex flex-col items-center py-10 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Icon name="smart_toy" className="text-[28px]" />
              </div>
              <h3 className="text-headline-md font-semibold text-on-surface">
                Ask about {agencyName}&apos;s expense policy
              </h3>
              <p className="mt-1 max-w-md text-body-sm text-on-surface-variant">
                Answers are grounded in your agency&apos;s policy documents and cite the
                governing clause. The assistant routes to a human when policy is missing or
                ambiguous.
              </p>
              <div className="mt-6 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
                {SUGGESTED_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => ask(p)}
                    className="rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2.5 text-left text-body-sm text-on-surface transition-colors hover:border-secondary hover:bg-surface-container-low"
                  >
                    <Icon name="bolt" className="mr-1.5 align-middle text-[16px] text-secondary" />
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((m) => (
                <MessageRow
                  key={m.id}
                  message={m}
                  onCopy={copy}
                  onRegenerate={m.id === lastAssistantId && !streaming ? regenerate : undefined}
                  userInitials={initials(user?.name)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-outline-variant bg-surface px-gutter py-3 md:px-margin-page">
        <div className="mx-auto w-full max-w-3xl">
          {attachments.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {attachments.map((name, i) => (
                <span
                  key={`${name}-${i}`}
                  className="inline-flex items-center gap-1 rounded border border-outline-variant bg-surface-container-low px-2 py-1 font-mono text-label-sm text-on-surface-variant"
                >
                  <Icon name="attach_file" className="text-[12px]" />
                  {name}
                  <button
                    onClick={() => setAttachments((p) => p.filter((_, idx) => idx !== i))}
                    aria-label="Remove attachment"
                    className="hover:text-error"
                  >
                    <Icon name="close" className="text-[12px]" />
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="flex items-end gap-2 rounded-xl border border-outline-variant bg-surface-container-lowest p-2 focus-within:border-secondary">
            <button
              onClick={() => fileRef.current?.click()}
              className="rounded p-2 text-on-surface-variant hover:bg-surface-container-low hover:text-primary"
              aria-label="Attach file"
            >
              <Icon name="attach_file" className="text-[20px]" />
            </button>
            <input ref={fileRef} type="file" multiple className="hidden" onChange={onPickFiles} />
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Ask about caps, receipts, deadlines…"
              className="max-h-40 flex-1 resize-none bg-transparent py-2 text-body-md text-on-surface placeholder:text-on-surface-variant/60 focus:outline-none"
            />
            <button
              onClick={voiceInput}
              className="rounded p-2 text-on-surface-variant hover:bg-surface-container-low hover:text-primary"
              aria-label="Voice input"
            >
              <Icon name="mic" className="text-[20px]" />
            </button>
            {streaming ? (
              <Button variant="outline" size="icon" onClick={stop} aria-label="Stop">
                <Icon name="stop" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={() => ask(input)}
                disabled={!input.trim()}
                aria-label="Send"
              >
                <Icon name="arrow_upward" />
              </Button>
            )}
          </div>
          <p className="mt-2 text-center font-mono text-label-sm text-on-surface-variant">
            Enter to send · Shift+Enter for a new line · answers cite policy clauses
          </p>
        </div>
      </div>
    </div>
  );
}

function initials(name?: string) {
  return (name ?? "You")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function MessageRow({
  message,
  onCopy,
  onRegenerate,
  userInitials,
}: {
  message: ChatMessage;
  onCopy: (text: string) => void;
  onRegenerate?: () => void;
  userInitials: string;
}) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <Avatar className="mt-0.5 h-8 w-8 shrink-0">
        <AvatarFallback
          className={cn(
            isUser ? "bg-secondary text-on-secondary" : "bg-primary/10 text-primary",
          )}
        >
          {isUser ? userInitials : <Icon name="smart_toy" className="text-[18px]" />}
        </AvatarFallback>
      </Avatar>

      <div className={cn("min-w-0 max-w-[85%]", isUser && "flex flex-col items-end")}>
        {isUser ? (
          <div className="rounded-xl rounded-tr-sm bg-secondary-container px-3.5 py-2 text-body-sm text-on-surface">
            {message.content}
          </div>
        ) : (
          <div className="w-full rounded-xl rounded-tl-sm border border-outline-variant bg-surface-container-lowest px-4 py-3">
            {message.step && !message.content && (
              <div className="flex items-center gap-2 text-body-sm text-on-surface-variant">
                <Icon name="progress_activity" className="animate-spin text-[18px] text-secondary" />
                {message.step}
              </div>
            )}

            {message.content && (
              <>
                <Markdown content={message.content} />
                {message.streaming && (
                  <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-middle" />
                )}
              </>
            )}

            {/* Citations */}
            {message.clauses && message.clauses.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-outline-variant pt-2">
                <span className="font-mono text-label-sm uppercase text-on-surface-variant">
                  Cited:
                </span>
                {message.clauses.map((c) => (
                  <span
                    key={c.id}
                    title={`${c.title} — ${c.source}`}
                    className="inline-flex items-center gap-1 rounded-full border border-outline-variant bg-surface-container-low px-2 py-0.5 font-mono text-label-sm text-secondary"
                  >
                    <Icon name="link" className="text-[12px]" />
                    {c.id}
                  </span>
                ))}
              </div>
            )}

            {/* Actions */}
            {!message.streaming && message.content && (
              <div className="mt-2 flex items-center gap-1">
                <button
                  onClick={() => onCopy(message.content)}
                  className="flex items-center gap-1 rounded px-1.5 py-1 font-mono text-label-sm text-on-surface-variant hover:bg-surface-container-low hover:text-primary"
                >
                  <Icon name="content_copy" className="text-[14px]" /> Copy
                </button>
                {onRegenerate && (
                  <button
                    onClick={onRegenerate}
                    className="flex items-center gap-1 rounded px-1.5 py-1 font-mono text-label-sm text-on-surface-variant hover:bg-surface-container-low hover:text-primary"
                  >
                    <Icon name="refresh" className="text-[14px]" /> Regenerate
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface SpeechRecognitionLike {
  lang: string;
  onresult: (e: { results: { 0: { 0: { transcript: string } } } }) => void;
  start: () => void;
}
