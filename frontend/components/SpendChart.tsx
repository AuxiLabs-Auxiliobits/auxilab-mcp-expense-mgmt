"use client";

// REFERENCE SCAFFOLD ONLY — see README.md.
// Apache ECharts spend-by-category chart (SCOPING §10). Stub — the real version
// imports ReactECharts from "echarts-for-react" and feeds an EChartsOption built
// from the Report Summariser's total_by_category aggregation (§4).

// import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

// Example option shape (not rendered in the stub).
const exampleOption: EChartsOption = {
  tooltip: {},
  xAxis: { type: "category", data: [] },
  yAxis: { type: "value" },
  series: [{ type: "bar", data: [] }],
};

export function SpendChart() {
  // TODO(reference): GET /reports/summary → build option → <ReactECharts option={option} />
  void exampleOption;

  return (
    <div className="rounded-md border border-dashed p-8 text-sm text-muted-foreground">
      STUB: Apache ECharts — spend by category / over time, bound to the Report
      Summariser aggregation.
    </div>
  );
}
