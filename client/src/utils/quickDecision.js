/** Keyboard and swipe shortcuts for the approval queue. Each maps to the card's existing button flow. */

const KEYS = { a: 'approve', r: 'reject', s: 'seen' };

// A horizontal drag this long (px) counts as a swipe; mostly-vertical drags are scrolling.
export const SWIPE_DISTANCE = 80;

/**
 * @param {KeyboardEvent} event - keydown from inside a card.
 * @returns {'approve'|'reject'|'seen'|null} The decision, or null when the key is not a shortcut here.
 */
export function keyDecision(event) {
  if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return null;
  if (event.target?.closest?.('input, textarea, select, [contenteditable="true"]')) return null;
  return KEYS[String(event.key).toLowerCase()] || null;
}

/**
 * @param {TouchEvent} event
 * @returns {{ x: number, y: number }} Where the touch started or ended.
 */
export function touchPoint(event) {
  const touch = event.changedTouches[0];
  return { x: touch.clientX, y: touch.clientY };
}

/**
 * @param {{ x: number, y: number }|null} start
 * @param {{ x: number, y: number }} end
 * @returns {'approve'|'reject'|null} Right approves, left asks to reject.
 */
export function swipeDecision(start, end) {
  if (!start) return null;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (Math.abs(dx) < SWIPE_DISTANCE || Math.abs(dy) > Math.abs(dx) / 2) return null;
  return dx > 0 ? 'approve' : 'reject';
}
