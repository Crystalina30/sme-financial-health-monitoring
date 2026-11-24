import ReactECharts from 'echarts-for-react';

import { baseGrid, useChartTheme } from './chartTheme.js';

/**
 * One indicator's value across reporting periods, with its two thresholds
 * drawn as reference lines so the trajectory can be read against them.
 */
export default function IndicatorTrendChart({ points, threshold, indicatorName }) {
  const { colours, textStyle, tooltip, referenceLine, axis } = useChartTheme();

  const markLines = threshold
    ? [
        { yAxis: threshold.concern_threshold, name: 'Concern' },
        { yAxis: threshold.distress_threshold, name: 'Distress' },
      ]
    : [];

  const option = {
    textStyle,
    grid: baseGrid,
    tooltip: { ...tooltip, trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: points.map((point) => point.label),
      ...axis(),
      splitLine: { show: false },
    },
    yAxis: { type: 'value', ...axis(indicatorName) },
    series: [
      {
        type: 'line',
        data: points.map((point) => point.value),
        symbolSize: 8,
        lineStyle: { width: 2, color: colours.series },
        itemStyle: { color: colours.series, borderColor: colours.markRing, borderWidth: 2 },
        markLine: {
          ...referenceLine,
          data: markLines,
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 260 }} notMerge />;
}
