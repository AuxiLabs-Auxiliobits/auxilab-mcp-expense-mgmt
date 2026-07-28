import { highlightSegments } from "@/lib/command-fuzzy";

/** Renders `text` with the fuzzy-matched subsequence of `query` emphasized. */
export function Highlight({ query, text }: { query: string; text: string }) {
  const segs = highlightSegments(query, text);
  return (
    <>
      {segs.map((s, i) =>
        s.hit ? (
          <mark key={i} className="bg-transparent font-semibold text-primary">
            {s.text}
          </mark>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </>
  );
}
