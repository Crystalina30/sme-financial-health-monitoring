import ReactECharts from 'echarts-for-react';

import { baseGrid, useChartTheme } from './chartTheme.js';

const STATUS_LABELS = {
  validated: 'Validated',
  provisional: 'Provisional',
  insufficient_data: 'Insufficient data',
};

/**
 * Overall financial health score across reporting periods.
 *
 * The two classification boundaries are drawn as reference lines, so a point's
 * band is readable from the chart without consulting a legend.
 */
export default function HealthScoreTrendChart({ trend }) {
  const { colours, textStyle, tooltip, referenceLine, axis } = useChartTheme();

  const option = {
    textStyle,
    grid: baseGrid,
    tooltip: {
      ...tooltip,
      trigger: 'axis',
      formatter: (params) => {
        const point = trend[params[0].dataIndex];
        const score = point.overall_score === null ? 'N/A' : point.overall_score.toFixed(1);
        return `${point.period_label}<br/>Score ${score} · ${STATUS_LABELS[point.assessment_status] || ''}`;
      },
    },
    xAxis: {
      type: 'category',
      data: trend.map((point) => point.period_label),
      ...axis(),
      splitLine: { show: false },
    },
    yAxis: { type: 'value', min: 0, max: 100, ...axis('Overall score') },
    series: [
      {
        type: 'line',
        // A provisional score is not a validated observation: drawn hollow.
        data: trend.map((point) =>
          point.assessment_status === 'validated'
            ? point.overall_score
            : {
                value: point.overall_score,
                symbol: 'emptyCircle',
                symbolSize: 11,
                itemStyle: { color: colours.status.concern, borderColor: colours.status.concern },
              },
        ),
        smooth: false,
        symbolSize: 8,
        lineStyle: { width: 2, color: colours.series },
        itemStyle: { color: colours.series, borderColor: colours.markRing, borderWidth: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: colours.seriesFill },
              { offset: 1, color: 'rgba(15, 157, 138, 0)' },
            ],
          },
        },
        markLine: {
          ...referenceLine,
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
