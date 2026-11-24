import ReactECharts from 'echarts-for-react';

import { STATUS_LABELS } from '../utils/format.js';
import { useChartTheme } from './chartTheme.js';

/**
 * All ten indicator scores on one axis, coloured by threshold status.
 *
 * Indicators are drawn in attention order, so the ones needing attention sit
 * at the top rather than having to be picked out by colour.
 */
export default function IndicatorStatusChart({ indicators }) {
  const { colours, textStyle, tooltip, axis } = useChartTheme();
  const ordered = [...indicators].reverse();

  const option = {
    textStyle,
    grid: { left: 150, right: 32, top: 16, bottom: 52, containLabel: false },
    tooltip: {
      ...tooltip,
      trigger: 'item',
      // The status is named in words, so it is never carried by colour alone.
      formatter: (params) =>
        `${params.name}<br/>Score: ${
          params.value === null || params.value === undefined
            ? 'N/A'
            : params.value.toFixed(1)
        } · ${STATUS_LABELS[ordered[params.dataIndex].status]}`,
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 100,
      ...axis('Score'),
      // Centred under the axis, so the title cannot run off the right edge.
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: colours.text, fontSize: 11 },
    },
    yAxis: {
      type: 'category',
      data: ordered.map((item) => item.display_name),
      ...axis(),
      splitLine: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: ordered.map((item) => ({
          value: item.score,
          itemStyle: { color: colours.status[item.status], borderRadius: [0, 4, 4, 0] },
        })),
        barMaxWidth: 18,
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 380 }} notMerge />;
}
