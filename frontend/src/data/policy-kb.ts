/**
 * Mock policy knowledge base for the Policy Assistant (document Q&A, SCOPING.md
 * §7 RAG). `retrieve()` does a tiny keyword "hybrid" match (agency-trimmed);
 * `composeAnswer()` produces a grounded, cited markdown answer. Swap both for a
 * real Azure AI Search + LLM call behind src/data/api.ts when the backend lands.
 */

export interface PolicyClause {
  id: string;
  /** Agency id this clause belongs to, or "ALL" for the baseline ruleset. */
  agencyId: string;
  title: string;
  keywords: string[];
  text: string;
  source: string;
}

export const policyClauses: PolicyClause[] = [
  {
    id: "WIFI-01",
    agencyId: "AGY-CRISPIN",
    title: "Wi-Fi / internet reimbursement",
    keywords: ["wifi", "wi-fi", "internet", "broadband", "fios", "home office", "connectivity"],
    text: "Wi-Fi / internet reimbursement is capped at **$100** per month. Any amount above is rejected. The cap is inclusive — $100 is allowed, $100.01 is not.",
    source: "Crispin Finance Rules v2.1",
  },
  {
    id: "MEAL-04",
    agencyId: "ALL",
    title: "Per-meal limit",
    keywords: ["meal", "meals", "food", "dinner", "lunch", "breakfast", "per diem", "restaurant"],
    text: "Individual meals are capped at **$75** inclusive of tax and tip. Amounts above the cap fail the deterministic intake check.",
    source: "Baseline ruleset",
  },
  {
    id: "HOTEL-01",
    agencyId: "ALL",
    title: "Hotel per-night limit",
    keywords: ["hotel", "lodging", "accommodation", "room", "night", "stay"],
    text: "Hotel lodging is capped at **$250 per night**. Multi-night stays are evaluated per night.",
    source: "Baseline ruleset",
  },
  {
    id: "CLIENT-01",
    agencyId: "ALL",
    title: "Client entertainment",
    keywords: ["client", "entertainment", "attendee", "attendees", "guests", "hospitality"],
    text: "Client entertainment requires an **itemised receipt** and an **attendee list**. Group client entertainment exceeding **$500** total requires documented pre-approval from the agency Managing Director.",
    source: "Crispin Finance Rules v2.1",
  },
  {
    id: "AIR-01",
    agencyId: "ALL",
    title: "Air travel class",
    keywords: ["air", "flight", "flights", "airfare", "plane", "travel", "economy", "business class"],
    text: "Air travel must be **economy class for flights under 6 hours**. Business class on shorter flights is rejected unless pre-approved.",
    source: "Baseline ruleset",
  },
  {
    id: "RECEIPT-01",
    agencyId: "ALL",
    title: "Receipt requirement",
    keywords: ["receipt", "receipts", "proof", "missing receipt", "threshold"],
    text: "A receipt is **required for any expense over $25**. Line items above the threshold without an attachment are returned at intake.",
    source: "Baseline ruleset",
  },
  {
    id: "CUTOFF-01",
    agencyId: "ALL",
    title: "Submission cutoff",
    keywords: ["cutoff", "deadline", "submit", "submission", "late", "month end", "month-end", "when"],
    text: "Expenses must be submitted **before the end of the calendar month in which they were incurred** (month-end cutoff, configurable).",
    source: "Baseline ruleset",
  },
  {
    id: "PROHIBITED-01",
    agencyId: "ALL",
    title: "Prohibited categories",
    keywords: ["prohibited", "banned", "not allowed", "other", "category", "disallowed"],
    text: 'The **"Other"** category is prohibited and rejected at intake. Use one of the eight standard categories instead.',
    source: "Baseline ruleset",
  },
  {
    id: "DUP-01",
    agencyId: "ALL",
    title: "Duplicate detection",
    keywords: ["duplicate", "duplicates", "same", "twice", "double", "repeat"],
    text: "Duplicates are detected by the unique key **(employee, receipt date-time, final total)**. Exact matches are blocked; near matches within ±3 days are flagged. Cross-employee matches route to a human.",
    source: "Baseline ruleset",
  },
  {
    id: "CAP-01",
    agencyId: "ALL",
    title: "Cap boundary",
    keywords: ["cap", "boundary", "inclusive", "exclusive", "limit", "exactly", "equal"],
    text: "All caps are **inclusive** — an amount exactly equal to the cap is allowed; only amounts strictly above it fail.",
    source: "Baseline ruleset",
  },
];

const STOP = new Set(["the", "a", "an", "is", "are", "for", "of", "to", "what", "how", "can", "i", "do", "does", "my", "on", "in", "and", "or", "be", "with", "much"]);

export function retrieve(query: string, agencyId: string, k = 3): PolicyClause[] {
  const terms = query
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter((t) => t && !STOP.has(t));

  const scored = policyClauses
    .filter((c) => c.agencyId === agencyId || c.agencyId === "ALL")
    .map((c) => {
      let score = 0;
      for (const term of terms) {
        if (c.keywords.some((kw) => kw.includes(term) || term.includes(kw))) score += 2;
        if (c.title.toLowerCase().includes(term)) score += 1;
      }
      // prefer agency-specific clauses on ties
      if (c.agencyId !== "ALL") score += 0.5;
      return { c, score };
    })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map((s) => s.c);

  return scored;
}

const THRESHOLD_QUERY = /limit|threshold|cap|baseline|config|rule|how much|amount/i;

export function composeAnswer(
  query: string,
  clauses: PolicyClause[],
  agencyName: string,
): string {
  if (clauses.length === 0) {
    return [
      `I couldn't find a specific clause in **${agencyName}**'s policy for that.`,
      "",
      "Per the governing principle, when the policy is **missing or ambiguous** the AI Finance Approver does not guess — it **routes the sheet to a human** for review. I'd suggest:",
      "",
      "- Rephrasing with the expense category (e.g. *meals*, *hotel*, *air travel*, *Wi-Fi*).",
      "- Checking the **baseline ruleset** for intake thresholds.",
      "- Contacting Finance to add or clarify the clause.",
    ].join("\n");
  }

  const parts: string[] = [];
  parts.push(`Here's what **${agencyName}**'s policy says:`);
  parts.push("");
  for (const c of clauses) {
    parts.push(`- ${c.text} \`[${c.id}]\``);
  }
  parts.push("");

  if (THRESHOLD_QUERY.test(query)) {
    parts.push("The deterministic intake thresholds applied before the AI gate:");
    parts.push("");
    parts.push("```json");
    parts.push("{");
    parts.push('  "per_meal_limit": 75,');
    parts.push('  "per_hotel_night_limit": 250,');
    parts.push('  "receipt_required_threshold": 25,');
    parts.push('  "cap_boundary": "inclusive",');
    parts.push('  "prohibited_categories": ["Other"]');
    parts.push("}");
    parts.push("```");
    parts.push("");
  }

  parts.push(
    "> Every approver decision cites the governing clause and runs alongside deterministic numeric checks; low-confidence or conflicting cases are routed to a human.",
  );
  return parts.join("\n");
}
