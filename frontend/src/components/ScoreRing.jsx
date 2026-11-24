import { useEffect, useState } from 'react';

import { formatScore } from '../utils/format.js';

const COUNT_UP_MS = 1200;

/**
 * Counts from zero up to the score as the ring draws, unless the device asks
 * for reduced motion, in which case the final value is shown at once.
 */
function prefersReducedMotion() {
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
}

function useCountUp(target) {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0));

  useEffect(() => {
    if (target === null || target === undefined) return undefined;
    if (prefersReducedMotion()) {
      setValue(target);
      return undefined;
    }
    let frame;
    const start = performance.now();
    // Timed with performance.now() rather than the frame timestamp, so the
    // two clocks can never disagree and give a negative progress.
    const step = () => {
      const progress = Math.min(Math.max((performance.now() - start) / COUNT_UP_MS, 0), 1);
      const eased = 1 - (1 - progress) ** 3;
      setValue(target * eased);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target]);

  return value;
}

/**
 * A 0-100 score drawn as a ring; `colour` may be a CSS variable. A score that
 * could not be calculated shows an empty ring and "N/A", never a zero.
 */
export default function ScoreRing({ score, colour, size = 72, stroke = 7, large = false }) {
  const shown = useCountUp(score);
  const radius = (size - stroke) / 2;
  const length = 2 * Math.PI * radius;
  const hasScore = score !== null && score !== undefined;
  const offset = hasScore ? length * (1 - Math.max(0, Math.min(score, 100)) / 100) : length;

  return (
    <div
      className={`score-ring${large ? ' score-ring-large' : ''}`}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} aria-hidden="true" focusable="false">
        <circle className="score-ring-track" cx={size / 2} cy={size / 2} r={radius} strokeWidth={stroke} />
        {hasScore && (
          <circle
            className="score-ring-value"
            cx={size / 2}
            cy={size / 2}
            r={radius}
            strokeWidth={stroke}
            strokeDasharray={length}
            strokeDashoffset={offset}
            // Set as a style, not an attribute, so a CSS colour variable works
            // and the ring follows the theme.
            style={{ stroke: colour, '--ring-length': length }}
          />
        )}
      </svg>
      <div className="score-ring-label">
        <span className="score-ring-number">{hasScore ? formatScore(shown) : 'N/A'}</span>
        {large && <span className="score-ring-outof">out of 100</span>}
      </div>
    </div>
  );
}
