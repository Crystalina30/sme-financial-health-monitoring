/**
 * Shared chart styling.
 *
 * One palette and one set of axis defaults, so every chart on the dashboard
 * reads as part of the same system. Status colour is carried by both hue and
 * position, never by hue alone.
 */

export const STATUS_COLOURS = {
  sound: '#2e8b57',
  concern: '#d99a2b',
  distress: '#c0392b',
  not_applicable: '#9aa8bf',
};

export const CLASSIFICATION_COLOURS = {
  sound: '#2e8b57',
  vulnerable: '#d99a2b',
  distressed: '#c0392b',
};

export const SERIES_COLOUR = '#1f6aa8';
export const GRID_COLOUR = '#e3e8f0';
export const TEXT_COLOUR = '#44506b';

export const baseGrid = { left: 48, right: 24, top: 32, bottom: 40, containLabel: true };

export const baseTextStyle = {
  fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
  color: TEXT_COLOUR,
  fontSize: 12,
};

export function axisDefaults(name) {
  return {
    name,
    nameTextStyle: { color: TEXT_COLOUR, fontSize: 11 },
    axisLine: { lineStyle: { color: GRID_COLOUR } },
    axisTick: { show: false },
    axisLabel: { color: TEXT_COLOUR, fontSize: 11 },
    splitLine: { lineStyle: { color: GRID_COLOUR, type: 'dashed' } },
  };
}
