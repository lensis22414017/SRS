export type Track = 'production' | 'ecology';

export const SRS_COLORS = {
  primary: '#1677ff',
  success: '#20b26b',
  warning: '#faad14',
  danger: '#ff4d4f',
  purple: '#7c5cff',
  cyan: '#13c2c2'
};

export function baseGrid() {
  return { left: 56, right: 24, top: 48, bottom: 42, containLabel: true };
}

export function optionPollutionDonut(items: Array<{ name: string; value: number }>) {
  const total = items.reduce((s, x) => s + Number(x.value || 0), 0);
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, left: 'center' },
    title: { text: String(total), subtext: '场地总数', left: 'center', top: '38%' },
    series: [{ name: '污染类型', type: 'pie', radius: ['52%', '72%'], center: ['50%', '42%'], data: items }]
  };
}

export function optionHorizontalTopN(title: string, rows: Array<{ name: string; value: number; extra?: string }>) {
  const sorted = [...rows].sort((a, b) => a.value - b.value);
  return {
    title: { text: title, left: 8, top: 4, textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: baseGrid(),
    xAxis: { type: 'value', name: '得分' },
    yAxis: { type: 'category', data: sorted.map(x => x.name) },
    series: [{ type: 'bar', data: sorted.map(x => x.value), barWidth: 14, label: { show: true, position: 'right' } }]
  };
}

export function optionBarrierStack(rows: Array<any>) {
  const keys = [
    ['规则严重度', 'ruleSeverity'],
    ['用途权重', 'useWeight'],
    ['模型贡献度', 'modelContribution'],
    ['稳定性', 'stability'],
    ['证据等级', 'evidence']
  ] as const;
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0 },
    grid: { left: 90, right: 24, top: 48, bottom: 32 },
    xAxis: { type: 'value', max: 1 },
    yAxis: { type: 'category', data: rows.map(x => x.factor) },
    series: keys.map(([name, key]) => ({
      name, type: 'bar', stack: 'total',
      data: rows.map(x => Number(x[key] || 0))
    }))
  };
}

export function optionMissingnessHeatmap(matrix: { xLabels: string[]; yLabels: string[]; values: Array<[number, number, number]> }) {
  return {
    tooltip: { position: 'top' },
    grid: { top: 48, left: 120, right: 24, bottom: 80 },
    xAxis: { type: 'category', data: matrix.xLabels, axisLabel: { rotate: 45 } },
    yAxis: { type: 'category', data: matrix.yLabels },
    visualMap: { min: 0, max: 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 0 },
    series: [{ type: 'heatmap', data: matrix.values }]
  };
}

export function optionSafetyEconomyScatter(rows: Array<any>) {
  return {
    tooltip: { trigger: 'item' },
    grid: baseGrid(),
    xAxis: { name: '安全性', min: 0, max: 1 },
    yAxis: { name: '经济性', min: 0, max: 1 },
    series: [{
      type: 'scatter',
      symbolSize: (v: any) => 12 + Number(v[2] || 0) * 28,
      data: rows.map(x => [x.safety, x.economy, x.ssui]),
      markLine: { silent: true, data: [{ xAxis: 0.6 }, { yAxis: 0.6 }] }
    }]
  };
}
