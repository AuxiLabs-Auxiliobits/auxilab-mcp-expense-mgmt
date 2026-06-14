"use client";

// REFERENCE SCAFFOLD ONLY — see README.md.
// Tremor KPI tiles (SCOPING §10). Stub — the real version imports { Card, Metric,
// Text } from "@tremor/react" and binds to the Report Summariser output
// (total_by_category, violation_count, total_at_risk, compliance_rate_pct — §4).

// import { Card, Metric, Text } from "@tremor/react";

interface Kpi {
  label: string;
  value: string;
}

const PLACEHOLDER_KPIS: Kpi[] = [
  { label: "Compliance rate", value: "—%" },
  { label: "Total at risk", value: "$—" },
  { label: "Violations", value: "—" },
  { label: "Routed to human", value: "—" },
];

export function KpiTiles() {
  // TODO(reference): GET /reports/summary → bind to <Card><Metric/></Card> tiles.
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {PLACEHOLDER_KPIS.map((kpi) => (
        <div key={kpi.label} className="rounded-md border p-4">
          <div className="text-xs text-muted-foreground">{kpi.label}</div>
          <div className="mt-1 text-2xl font-semibold">{kpi.value}</div>
        </div>
      ))}
      <p className="col-span-full text-xs text-muted-foreground">
        STUB: Tremor KPI tiles bound to the Report Summariser output.
      </p>
    </div>
  );
}
