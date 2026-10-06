import ReactECharts from 'echarts-for-react';

import { STATUS_COLOURS } from './chartTheme.js';
import { axisDefaults, baseTextStyle } from './chartTheme.js';

/**
 * All ten indicator scores on one axis, coloured by threshold status.
 *
 * Indicators are drawn in attention order, so the ones needing attention sit
 * at the top rather than having to be picked out by colour.
 */
export default function IndicatorStatusChart({ indicators }) {
  const ordered = [...indicators].reverse();

  const option = {
    textStyle: baseTextStyle,
    grid: { left: 150, right: 32, top: 16, bottom: 40, containLabel: false },
    tooltip: {
      trigger: 'item',
      formatter: (params) =>
        `${params.name}<br/>Score: ${
          params.value === null || params.value === undefined
            ? 'N/A'
            : params.value.toFixed(1)
        }`,
    },
    xAxis: { type: 'value', min: 0, max: 100, ...axisDefaults('Score') },
    yAxis: {
      type: 'category',
      data: ordered.map((item) => item.display_name),
      ...axisDefaults(),
      splitLine: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: ordered.map((item) => ({
          value: item.score,
          itemStyle: { color: STATUS_COLOURS[item.status], borderRadius: [0, 3, 3, 0] },
        })),
        barMaxWidth: 18,
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 380 }} notMerge />;
}
