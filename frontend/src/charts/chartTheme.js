/**
 * Shared chart styling.
 *
 * One palette and one set of axis defaults per theme, so every chart on the
 * dashboard reads as part of the same system. ECharts draws on a canvas, which
 * cannot read CSS variables, so the colours live here and follow the theme the
 * user picked. Each set was checked for colour-blind separation and 3:1
 * contrast against its own card surface. Status colour is carried by both hue
 * and position, never by hue alone.
 */
import { useTheme } from '../context/ThemeContext.jsx';

const FONT = 'Poppins, system-ui, -apple-system, Segoe UI, Roboto, sans-serif';

const PALETTES = {
  light: {
    status: { sound: '#12814b', concern: '#c58f00', distress: '#c8333f', not_applicable: '#6b7890' },
    series: '#0f9d8a',
    seriesFill: 'rgba(15, 157, 138, 0.18)',
    grid: 'rgba(20, 45, 78, 0.08)',
    axis: 'rgba(20, 45, 78, 0.18)',
    text: 'rgba(20, 45, 78, 0.68)',
    reference: 'rgba(20, 45, 78, 0.35)',
    markRing: '#ffffff',
    tooltip: {
      backgroundColor: 'rgba(255, 255, 255, 0.97)',
      borderColor: 'rgba(20, 45, 78, 0.12)',
      textColor: '#142d4e',
      shadow: '0 12px 30px rgba(20, 45, 78, 0.15)',
    },
  },
  dark: {
    status: { sound: '#3ccf8e', concern: '#f5bd3c', distress: '#ff7a70', not_applicable: '#8a9ab3' },
    series: '#14a08d',
    seriesFill: 'rgba(20, 160, 141, 0.28)',
    grid: 'rgba(255, 255, 255, 0.08)',
    axis: 'rgba(255, 255, 255, 0.16)',
    text: 'rgba(245, 247, 250, 0.64)',
    reference: 'rgba(245, 247, 250, 0.35)',
    markRing: '#0b1729',
    tooltip: {
      backgroundColor: 'rgba(11, 23, 41, 0.94)',
      borderColor: 'rgba(255, 255, 255, 0.14)',
      textColor: '#f5f7fa',
      shadow: '0 12px 30px rgba(0, 0, 0, 0.4)',
    },
  },
};

// The wide right margin leaves room for the labels at the end of the dashed
// reference lines ("Concern", "Vulnerable"), which the plot area does not
// reserve space for on its own.
export const baseGrid = { left: 24, right: 84, top: 40, bottom: 24, containLabel: true };

/** Everything a chart needs to draw itself in the given theme. */
export function chartTheme(theme) {
  const colours = PALETTES[theme] || PALETTES.light;
  return {
    colours,
    textStyle: { fontFamily: FONT, color: colours.text, fontSize: 12 },
    // A small card matching the app's cards.
    tooltip: {
      backgroundColor: colours.tooltip.backgroundColor,
      borderColor: colours.tooltip.borderColor,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: colours.tooltip.textColor, fontFamily: FONT, fontSize: 12 },
      extraCssText: `border-radius: 10px; box-shadow: ${colours.tooltip.shadow};`,
    },
    // Dashed reference lines for thresholds and classification boundaries.
    referenceLine: {
      silent: true,
      symbol: 'none',
      label: { formatter: '{b}', fontSize: 10, color: colours.text, fontFamily: FONT },
      lineStyle: { type: 'dashed', color: colours.reference },
    },
    axis(name) {
      return {
        name,
        // Axis titles start at the axis rather than centring on it, so a
        // long one such as an indicator name is not cut off at the edge.
        nameTextStyle: { color: colours.text, fontSize: 11, align: 'left' },
        axisLine: { lineStyle: { color: colours.axis } },
        axisTick: { show: false },
        axisLabel: { color: colours.text, fontSize: 11 },
        splitLine: { lineStyle: { color: colours.grid, type: 'dashed' } },
      };
    },
  };
}

/** The chart styling for the theme currently in use. */
export function useChartTheme() {
  const { theme } = useTheme();
  return chartTheme(theme);
}
