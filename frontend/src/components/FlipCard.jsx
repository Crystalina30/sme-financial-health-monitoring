import { useEffect, useRef, useState } from 'react';

import Icon from './Icon.jsx';

/**
 * A card that turns over to show its calculation on the back.
 *
 * A click anywhere on the card turns it. Keyboard and screen-reader users use
 * the small button on each face, and focus moves to the face being shown, so
 * it is never left on the hidden one. Both faces share one grid cell, so the
 * card is as tall as its taller face and does not jump in size when turned.
 */
export default function FlipCard({ label, front, back, className = '' }) {
  const [flipped, setFlipped] = useState(false);
  const frontButton = useRef(null);
  const backButton = useRef(null);
  const hasTurned = useRef(false);

  useEffect(() => {
    // Only after the user has turned the card, never on first render.
    if (!hasTurned.current) return;
    (flipped ? backButton : frontButton).current?.focus({ preventScroll: true });
  }, [flipped]);

  function turn() {
    hasTurned.current = true;
    setFlipped((value) => !value);
  }

  function handleCardClick(event) {
    // Leave links, form controls and text selection alone.
    if (event.target.closest('a, button, select, input')) return;
    if (window.getSelection?.().toString()) return;
    turn();
  }

  return (
    <div className={`flip-card${flipped ? ' is-flipped' : ''} ${className}`} onClick={handleCardClick}>
      <div className="flip-inner">
        <div className="flip-face flip-front" aria-hidden={flipped} inert={flipped ? '' : undefined}>
          {front}
          <button
            ref={frontButton}
            type="button"
            className="flip-toggle"
            onClick={turn}
            aria-label={`Show how ${label} is calculated`}
          >
            <Icon name="info" />
          </button>
        </div>
        <div className="flip-face flip-back" aria-hidden={!flipped} inert={flipped ? undefined : ''}>
          {back}
          <button
            ref={backButton}
            type="button"
            className="flip-toggle"
            onClick={turn}
            aria-label={`Back to ${label}`}
          >
            <Icon name="flipBack" />
          </button>
        </div>
      </div>
    </div>
  );
}
