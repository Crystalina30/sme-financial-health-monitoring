import ReactECharts from 'echarts-for-react';

import { axisDefaults, baseGrid, baseTextStyle, SERIES_COLOUR } from './chartTheme.js';

/**
 * Overall financial health score across reporting periods.
 *
 * The two classification boundaries are drawn as reference lines, so a point's
 * band is readable from the chart without consulting a legend.
 */
export default function HealthScoreTrendChart({ trend }) {
  const option = {
    textStyle: baseTextStyle,
    grid: baseGrid,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => (value === null ? 'N/A' : value.toFixed(1)),
    },
    xAxis: {
      type: 'category',
      data: trend.map((point) => point.period_label),
      ...axisDefaults(),
      splitLine: { show: false },
    },
    yAxis: { type: 'value', min: 0, max: 100, ...axisDefaults('Overall score') },
    series: [
      {
        type: 'line',
        data: trend.map((point) => point.overall_score),
        smooth: false,
        symbolSize: 7,
        lineStyle: { width: 2, color: SERIES_COLOUR },
        itemStyle: { color: SERIES_COLOUR },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { formatter: '{b}', fontSize: 10, color: '#7a8599' },
          lineStyle: { type: 'dashed', color: '#c9d2e0' },
          data: [
            { yAxis: 60, name: 'Sound' },
            { yAxis: 40, name: 'Vulnerable' },
          ],
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 280 }} notMerge />;
}
