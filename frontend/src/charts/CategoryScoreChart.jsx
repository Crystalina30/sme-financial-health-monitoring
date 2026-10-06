import ReactECharts from 'echarts-for-react';

import { CATEGORY_LABELS } from '../utils/format.js';
import { axisDefaults, baseGrid, baseTextStyle, SERIES_COLOUR } from './chartTheme.js';

/**
 * Compares the four category scores on a common 0-100 scale.
 *
 * A category with no applicable indicators is shown as a gap rather than as
 * zero, so an absent score is not read as a bad one.
 */
export default function CategoryScoreChart({ categoryScores }) {
  const option = {
    textStyle: baseTextStyle,
    grid: baseGrid,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => (value === null ? 'N/A' : value.toFixed(1)),
    },
    xAxis: {
      type: 'category',
      data: categoryScores.map((item) => CATEGORY_LABELS[item.category]),
      ...axisDefaults(),
      splitLine: { show: false },
    },
    yAxis: { type: 'value', min: 0, max: 100, ...axisDefaults('Score') },
    series: [
      {
        type: 'bar',
        data: categoryScores.map((item) => item.score),
        barMaxWidth: 56,
        itemStyle: { color: SERIES_COLOUR, borderRadius: [3, 3, 0, 0] },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 260 }} notMerge />;
}
