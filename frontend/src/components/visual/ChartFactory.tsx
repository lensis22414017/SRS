import React from 'react';
import ReactECharts from 'echarts-for-react';
import { optionPollutionDonut, optionHorizontalTopN, optionBarrierStack, optionMissingnessHeatmap, optionSafetyEconomyScatter } from '../../visualization/chartPresets';

type ChartKind = 'pollutionDonut' | 'horizontalTopN' | 'barrierStack' | 'missingnessHeatmap' | 'safetyEconomyScatter';

export default function ChartFactory({ kind, data, title, height = 320, testId }: { kind: ChartKind; data: any; title?: string; height?: number | string; testId?: string }) {
  const options: Record<ChartKind, any> = {
    pollutionDonut: optionPollutionDonut(data ?? []),
    horizontalTopN: optionHorizontalTopN(title || 'Top-N', data ?? []),
    barrierStack: optionBarrierStack(data ?? []),
    missingnessHeatmap: optionMissingnessHeatmap(data ?? { xLabels: [], yLabels: [], values: [] }),
    safetyEconomyScatter: optionSafetyEconomyScatter(data ?? []),
  };
  return <div data-testid={testId || `chart-${kind}`} style={{ width: '100%', height }}>
    <ReactECharts option={options[kind]} style={{ width: '100%', height: '100%' }} opts={{ renderer: 'svg' }} notMerge />
  </div>;
}
