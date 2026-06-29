import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../api';
import { humanizeCategory, rupees } from '../utils/format';

// Tailwind styling for rendered markdown. Tables render as real HTML tables
// (remark-gfm), so we style th/td here rather than leaving raw pipes.
const MARKDOWN_CLASS = [
  'space-y-2 text-[14px]',
  '[&_p]:leading-relaxed',
  '[&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1',
  '[&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1',
  '[&_li]:leading-relaxed',
  '[&_strong]:font-semibold',
  '[&_em]:italic',
  '[&_a]:text-cyan-300 [&_a]:underline',
  '[&_h1]:text-base [&_h1]:font-bold [&_h2]:text-sm [&_h2]:font-bold [&_h3]:font-semibold',
  '[&_code]:rounded [&_code]:bg-slate-950/60 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12px] [&_code]:text-cyan-100',
  '[&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-slate-950/60 [&_pre]:p-3 [&_pre]:text-[12px]',
  '[&_pre_code]:bg-transparent [&_pre_code]:p-0',
  // Real tables
  '[&_table]:my-1 [&_table]:w-full [&_table]:border-collapse [&_table]:overflow-hidden [&_table]:rounded-lg [&_table]:text-[13px]',
  '[&_thead]:bg-slate-950/60',
  '[&_th]:border [&_th]:border-white/10 [&_th]:px-3 [&_th]:py-1.5 [&_th]:text-left [&_th]:font-semibold [&_th]:text-slate-300',
  '[&_td]:border [&_td]:border-white/10 [&_td]:px-3 [&_td]:py-1.5 [&_td]:align-top',
  '[&_tbody_tr:nth-child(even)]:bg-white/[0.03]',
  '[&_blockquote]:border-l-2 [&_blockquote]:border-cyan-400/40 [&_blockquote]:pl-3 [&_blockquote]:text-slate-300',
].join(' ');

const SUGGESTIONS = [
  'Plan a 3 day trip to Bangalore for a client meeting',
  'Check if this is compliant',
  'Approve this trip',
  'Generate my expense report',
];

const WELCOME = {
  role: 'assistant',
  text:
    "Hi! I'm TripSense. Ask me in plain English - I'll plan trip budgets, check policy " +
    'compliance, pre-approve trips, parse receipts, detect duplicate claims, and generate ' +
    'expense reports. I decide which tools to call based on what you say.',
  toolCalls: [],
};

const toolMatches = (name, aliases) => aliases.includes(name);

function CardShell({ children, tone = 'cyan' }) {
  const tones = {
    cyan: 'border-cyan-400/20',
    green: 'border-emerald-400/25',
    amber: 'border-amber-400/25',
    red: 'border-rose-400/25',
    slate: 'border-white/10',
  };

  return (
    <div className={`rounded-card border ${tones[tone]} bg-white/[0.05] p-4 text-sm text-slate-100 shadow-card`}>
      {children}
    </div>
  );
}

function Pill({ children, tone = 'slate' }) {
  const tones = {
    green: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
    amber: 'border-amber-400/30 bg-amber-400/10 text-amber-300',
    red: 'border-rose-400/30 bg-rose-400/10 text-rose-300',
    cyan: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200',
    slate: 'border-white/10 bg-white/5 text-slate-300',
  };

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

function Meter({ value, tone = 'cyan' }) {
  const pct = Math.max(0, Math.min(100, Math.round(Number(value || 0) * 100)));
  const colors = {
    cyan: 'bg-cyan-300',
    green: 'bg-emerald-300',
    amber: 'bg-amber-300',
    red: 'bg-rose-300',
    slate: 'bg-slate-400',
  };

  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">Confidence</span>
        <span className="font-mono text-slate-200">{pct}%</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-950/70">
        <div className={`h-full rounded-full ${colors[tone]}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function RawToolDetails({ call }) {
  return (
    <details className="rounded-lg border border-dashed border-white/15 bg-white/[0.04] text-xs">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-1.5">
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
        <span className="font-mono text-[12px] font-medium text-slate-200">{call.name}</span>
        <span className="font-mono text-[11px] text-emerald-300">completed</span>
        <span className="ml-auto text-[11px] text-cyan-300">view I/O</span>
      </summary>
      <div className="space-y-2 border-t border-dashed border-white/10 px-3 py-2">
        <div>
          <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wide text-slate-500">
            Input
          </p>
          <pre className="overflow-x-auto rounded bg-slate-950/70 p-2 font-mono text-[11px] text-slate-200">
            {JSON.stringify(call.input, null, 2)}
          </pre>
        </div>
        <div>
          <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wide text-slate-500">
            Result
          </p>
          <pre className="overflow-x-auto rounded bg-slate-950/70 p-2 font-mono text-[11px] text-slate-200">
            {JSON.stringify(call.result, null, 2)}
          </pre>
        </div>
      </div>
    </details>
  );
}

function ToolCallLog({ calls }) {
  if (!calls?.length) return null;
  return (
    <div className="mt-2 space-y-2">
      {calls.map((call, i) => (
        <ToolResultCard key={i} call={call} />
      ))}
    </div>
  );
}

function ReceiptCard({ data }) {
  if (data.error) {
    return (
      <CardShell tone="red">
        <p className="font-semibold text-rose-200">Receipt parse failed</p>
        <p className="mt-1 text-rose-100">{data.error}</p>
      </CardShell>
    );
  }
  const items = data.line_items || [];
  const itemsTotal = items.reduce((s, it) => s + (Number(it.amount) || 0), 0);
  const confidence = Number(data.ocr_confidence || 0);
  return (
    <CardShell>
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="font-semibold text-white">Receipt parsed</p>
        <Pill tone={confidence >= 0.8 ? 'green' : 'amber'}>OCR</Pill>
      </div>
      <dl className="space-y-1">
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Merchant</dt>
          <dd className="font-medium text-slate-100">{data.merchant_name || '-'}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Date</dt>
          <dd className="font-mono text-xs text-slate-200">{data.date || '-'}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Total</dt>
          <dd className="font-mono font-bold text-white">{rupees(data.total_amount)}</dd>
        </div>
      </dl>

      {items.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Line items
          </p>
          <ul className="divide-y divide-white/10 rounded-lg border border-white/10 bg-slate-950/30">
            {items.map((it, i) => (
              <li key={i} className="flex justify-between gap-4 px-3 py-1.5">
                <span className="text-slate-200">{it.description}</span>
                <span className="font-mono font-medium text-slate-100">{rupees(Number(it.amount))}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.reconciliation_flag && (
        <div className="mt-3 rounded-lg border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs text-rose-100">
          Reconciliation warning: line items ({rupees(itemsTotal)}) do not match the stated
          total ({rupees(data.total_amount)}).
        </div>
      )}

      <Meter value={confidence} tone={confidence >= 0.8 ? 'green' : 'amber'} />
    </CardShell>
  );
}

function PolicyCheckCard({ data }) {
  const violations = data.violations || [];
  const action = data.recommended_action || (data.compliant ? 'Auto-approve' : 'Flag for review');
  const normalizedAction = action.toLowerCase();
  const tone = data.compliant ? 'green' : normalizedAction.includes('reject') ? 'red' : 'amber';
  const decisionLabel = normalizedAction.includes('reject')
    ? 'Reject'
    : normalizedAction.includes('flag')
      ? 'Flag'
      : 'Auto-approve';

  return (
    <CardShell tone={tone}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-white">Policy check</p>
          <p className="mt-0.5 text-xs text-slate-400">
            {data.employee_id ? `Employee ${data.employee_id}` : 'Compliance result'}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-1">
          <Pill tone={data.compliant ? 'green' : 'red'}>
            {data.compliant ? 'Compliant' : 'Non-compliant'}
          </Pill>
          <Pill tone={tone}>{decisionLabel}</Pill>
        </div>
      </div>

      <div className="mt-3 rounded-lg bg-slate-950/35 px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Violation reason
        </p>
        {violations.length ? (
          <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-slate-200">
            {violations.map((violation, i) => (
              <li key={i}>{violation}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-slate-200">No policy violations found.</p>
        )}
      </div>
    </CardShell>
  );
}

function CategoryCard({ data }) {
  const confidence = Number(data.confidence_score || data.confidence || 0);
  return (
    <CardShell>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-white">Spend category</p>
          <p className="mt-1 text-lg font-semibold text-cyan-100">
            {data.display_category || humanizeCategory(data.category)}
          </p>
        </div>
        <Pill tone={confidence >= 0.75 ? 'green' : confidence >= 0.5 ? 'amber' : 'slate'}>
          Classifier
        </Pill>
      </div>

      <Meter value={confidence} tone={confidence >= 0.75 ? 'green' : confidence >= 0.5 ? 'amber' : 'slate'} />

      {data.matched_signals?.length > 0 && (
        <p className="mt-2 text-xs text-slate-400">
          Matched signals: <span className="text-slate-200">{data.matched_signals.join(', ')}</span>
        </p>
      )}
    </CardShell>
  );
}

function DuplicateCard({ data }) {
  const risk = Number(data.duplicate_risk_score || 0);
  const riskPct = Math.round(risk * 100);
  const tone = risk >= 0.75 ? 'red' : risk >= 0.5 ? 'amber' : 'slate';
  const barColor = tone === 'red' ? 'bg-rose-300' : tone === 'amber' ? 'bg-amber-300' : 'bg-slate-400';

  return (
    <CardShell tone={tone}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-white">Duplicate check</p>
          <p className="mt-0.5 text-xs text-slate-400">
            {data.submitted_claim_id ? `Submitted claim ${data.submitted_claim_id}` : 'Claim risk scan'}
          </p>
        </div>
        <Pill tone={tone}>{riskPct >= 75 ? 'High risk' : riskPct >= 50 ? 'Medium risk' : 'Low risk'}</Pill>
      </div>

      <div className="mt-3">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400">Duplicate risk</span>
          <span className="font-mono text-slate-200">{riskPct}%</span>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-950/70">
          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${riskPct}%` }} />
        </div>
      </div>

      <div className="mt-3 rounded-lg bg-slate-950/35 px-3 py-2 text-xs">
        <span className="text-slate-400">Matched claim reference: </span>
        <span className="font-mono text-slate-100">{data.matched_claim_reference || 'None'}</span>
      </div>
    </CardShell>
  );
}

function ToolResultCard({ call }) {
  if (toolMatches(call.name, ['check_policy_compliance', 'expense_policy_checker'])) {
    return <PolicyCheckCard data={call.result || {}} />;
  }
  if (toolMatches(call.name, ['classify_spend_category', 'spend_category_classifier'])) {
    return <CategoryCard data={call.result || {}} />;
  }
  if (toolMatches(call.name, ['detect_duplicate_claim', 'duplicate_claim_detector'])) {
    return <DuplicateCard data={call.result || {}} />;
  }
  if (toolMatches(call.name, ['parse_receipt', 'receipt_parser'])) {
    return <ReceiptCard data={call.result || {}} />;
  }
  return <RawToolDetails call={call} />;
}

function Bubble({ msg }) {
  const isUser = msg.role === 'user';

  if (msg.receipt) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%]">
          <ReceiptCard data={msg.receipt} />
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className="max-w-[80%]">
        <div
          className={`px-4 py-2.5 text-[14px] leading-relaxed ${
            isUser
              ? 'rounded-2xl rounded-br-md bg-cyan-400 text-slate-950'
              : 'rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.05] text-slate-100 shadow-card'
          }`}
        >
          {msg.text ? (
            isUser ? (
              msg.text.split('\n').map((line, i) => <p key={i}>{line || ' '}</p>)
            ) : (
              <div className={MARKDOWN_CLASS}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
              </div>
            )
          ) : (
            <span className="italic text-slate-400">(no text response)</span>
          )}
        </div>
        {!isUser && <ToolCallLog calls={msg.toolCalls} />}
      </div>
    </div>
  );
}

// Pulsing three-dot typing indicator.
function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.05] px-4 py-3 shadow-card">
        <span className="typing-dot h-2 w-2 rounded-full bg-cyan-300" />
        <span className="typing-dot h-2 w-2 rounded-full bg-cyan-300" style={{ animationDelay: '0.2s' }} />
        <span className="typing-dot h-2 w-2 rounded-full bg-cyan-300" style={{ animationDelay: '0.4s' }} />
      </div>
    </div>
  );
}

export default function ChatWindow({ onToolCalls }) {
  // `history` is the Anthropic-format message log the backend round-trips.
  const [history, setHistory] = useState([]);
  // `display` is what we render (user/assistant bubbles + tool-call logs).
  const [display, setDisplay] = useState([WELCOME]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [display, loading]);

  async function send(text) {
    const content = text.trim();
    if (!content || loading) return;

    setError(null);
    setInput('');
    setDisplay((d) => [...d, { role: 'user', text: content }]);
    const nextHistory = [...history, { role: 'user', content }];
    setLoading(true);

    try {
      const res = await api.chat(nextHistory);
      setHistory(res.messages);
      setDisplay((d) => [
        ...d,
        { role: 'assistant', text: res.reply, toolCalls: res.tool_calls },
      ]);
      onToolCalls?.(res.tool_calls);
    } catch (e) {
      setError(
        'Chat request failed. Make sure the API is running and ANTHROPIC_API_KEY is set ' +
          'in the backend environment.'
      );
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    send(input);
  }

  async function uploadReceipt(e) {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-uploading the same file
    if (!file || loading) return;

    setError(null);
    setDisplay((d) => [...d, { role: 'user', text: `Uploaded receipt: ${file.name}` }]);
    setLoading(true);
    try {
      const receipt = await api.parseReceipt(file);
      setDisplay((d) => [...d, { role: 'assistant', receipt }]);
    } catch (err) {
      setError('Receipt upload failed. Make sure the API is running and the file is a JPG/PNG image.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-200px)] min-h-[480px] flex-col overflow-hidden rounded-card border border-white/10 bg-[#0b1627] shadow-card">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto bg-[#07111f] p-4 sm:p-6">
        {display.map((msg, i) => (
          <Bubble key={i} msg={msg} />
        ))}
        {loading && <TypingIndicator />}
      </div>

      {display.length <= 1 && (
        <div className="flex flex-wrap gap-2 border-t border-white/10 bg-[#0b1627] px-4 pt-3">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300 transition-colors hover:border-cyan-400/50 hover:bg-cyan-400/10 hover:text-cyan-100"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {error && <p className="bg-[#0b1627] px-4 pt-2 text-xs text-rose-300">{error}</p>}

      <form onSubmit={onSubmit} className="flex items-end gap-2 border-t border-white/10 bg-[#0b1627] p-3 sm:p-4">
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg"
          className="hidden"
          onChange={uploadReceipt}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={loading}
          title="Attach a receipt image (JPG/PNG)"
          aria-label="Attach a receipt image"
          className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-lg leading-none text-slate-300 transition-colors hover:border-cyan-400/50 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          +
        </button>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          rows={1}
          placeholder="Ask TripSense anything... (e.g. Plan a 3 day trip to Bangalore for a client meeting)"
          className="max-h-32 flex-1 resize-none rounded-xl border border-white/10 bg-slate-950/40 px-4 py-2.5 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-xl bg-cyan-400 px-4 py-2.5 text-sm font-medium text-slate-950 transition-colors hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
