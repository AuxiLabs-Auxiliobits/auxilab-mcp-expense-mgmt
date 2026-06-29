"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

function CodeBlock({ children }: { children?: React.ReactNode }) {
  const ref = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);

  function copy() {
    const text = ref.current?.textContent ?? "";
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="group relative my-3">
      <button
        onClick={copy}
        className="absolute right-2 top-2 flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-1 font-mono text-[10px] text-white/70 opacity-0 transition-opacity hover:bg-white/10 group-hover:opacity-100"
        aria-label="Copy code"
      >
        <Icon name={copied ? "check" : "content_copy"} className="text-[12px]" />
        {copied ? "Copied" : "Copy"}
      </button>
      <pre
        ref={ref}
        className="scrollbar-thin overflow-x-auto rounded-lg border border-outline-variant bg-deep-onyx p-4 text-[13px] leading-relaxed"
      >
        {children}
      </pre>
    </div>
  );
}

export function Markdown({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn("text-body-sm leading-relaxed text-on-surface", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          p: (_props) => <p className="my-2 first:mt-0 last:mb-0" {..._props} />,
          a: (_props) => (
            <a
              target="_blank"
              rel="noreferrer"
              className="text-secondary underline underline-offset-2 hover:text-primary"
              {..._props}
            />
          ),
          ul: (_props) => <ul className="my-2 list-disc space-y-1 pl-5" {..._props} />,
          ol: (_props) => <ol className="my-2 list-decimal space-y-1 pl-5" {..._props} />,
          li: (_props) => <li className="leading-relaxed" {..._props} />,
          h1: (_props) => <h1 className="mb-2 mt-3 text-body-lg font-semibold" {..._props} />,
          h2: (_props) => <h2 className="mb-2 mt-3 text-body-md font-semibold" {..._props} />,
          h3: (_props) => <h3 className="mb-1 mt-2 text-body-sm font-semibold" {..._props} />,
          strong: (_props) => <strong className="font-semibold text-on-surface" {..._props} />,
          blockquote: (_props) => (
            <blockquote
              className="my-2 border-l-2 border-secondary/50 bg-surface-container-low/50 py-1 pl-3 text-on-surface-variant"
              {..._props}
            />
          ),
          table: (_props) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-left text-body-sm" {..._props} />
            </div>
          ),
          th: (_props) => (
            <th className="border-b border-outline-variant px-2 py-1 font-mono text-label-sm uppercase text-on-surface-variant" {..._props} />
          ),
          td: (_props) => <td className="border-b border-outline-variant px-2 py-1" {..._props} />,
          pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
          code: ({ className: cls, children, ...props }) => {
            const isBlock = /language-/.test(cls ?? "");
            if (isBlock) {
              return (
                <code className={cls} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded bg-surface-container-high px-1.5 py-0.5 font-mono text-[12px] text-on-surface"
                {...props}
              >
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
