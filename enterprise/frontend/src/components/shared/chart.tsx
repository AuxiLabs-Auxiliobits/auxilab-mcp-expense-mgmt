"use client";

import dynamic from "next/dynamic";
import type { EChartsOption } from "echarts";

// Apache ECharts via echarts-for-react; client-only to avoid SSR window access.
const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

export function Chart({
  option,
  height = 240,
  className,
}: {
  option: EChartsOption;
  height?: number | string;
  className?: string;
}) {
  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      className={className}
      notMerge
      lazyUpdate
      opts={{ renderer: "svg" }}
    />
  );
}
