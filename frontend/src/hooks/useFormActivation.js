import { useEffect, useRef } from 'react';

/**
 * For a form that stays mounted while another one is on screen. When it
 * becomes the active form, focus moves to its heading (the link the user
 * clicked has just gone inert). When it stops being active, onDeactivate
 * clears whatever should not be waiting there on their return.
 */
export default function useFormActivation(active, onDeactivate) {
  const titleRef = useRef(null);
  const wasActive = useRef(active);

  useEffect(() => {
    if (active && !wasActive.current) titleRef.current?.focus({ preventScroll: true });
    if (!active && wasActive.current) onDeactivate();
    wasActive.current = active;
  }, [active]);

  return titleRef;
}
