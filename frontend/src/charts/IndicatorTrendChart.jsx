import ReactECharts from 'echarts-for-react';

import { axisDefaults, baseGrid, baseTextStyle, SERIES_COLOUR } from './chartTheme.js';

/**
 * One indicator's value across reporting periods, with its two thresholds
 * drawn as reference lines so the trajectory can be read against them.
 */
export default function IndicatorTrendChart({ points, threshold, indicatorName }) {
  const markLines = threshold
    ? [
        { yAxis: threshold.concern_threshold, name: 'Concern' },
        { yAxis: threshold.distress_threshold, name: 'Distress' },
      ]
    : [];

  const option = {
    textStyle: baseTextStyle,
    grid: baseGrid,
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: points.map((point) => point.label),
      ...axisDefaults(),
      splitLine: { show: false },
    },
    yAxis: { type: 'value', ...axisDefaults(indicatorName) },
    series: [
      {
        type: 'line',
        data: points.map((point) => point.value),
        symbolSize: 7,
        lineStyle: { width: 2, color: SERIES_COLOUR },
        itemStyle: { color: SERIES_COLOUR },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { formatter: '{b}', fontSize: 10, color: '#7a8599' },
          lineStyle: { type: 'dashed', color: '#c9d2e0' },
          data: markLines,
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 260 }} notMerge />;
}
