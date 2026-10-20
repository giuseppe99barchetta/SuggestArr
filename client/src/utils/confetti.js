/** Lightweight canvas confetti; nothing runs when the viewer prefers reduced motion. */

const COLORS = ['brand', 'brand-ink', 'caution', 'good', 'notice', 'anime'];

export function prefersReducedMotion() {
  try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
}

/**
 * Burst confetti over a canvas sized to its CSS box.
 * @param {HTMLCanvasElement} canvas - Overlay canvas; it should not capture pointer events.
 * @param {Object} [options]
 * @param {number} [options.count=160] - Number of pieces.
 * @param {number} [options.duration=3200] - Milliseconds before the burst fades out.
 * @returns {Function} Stops the animation and clears the canvas.
 */
export function launchConfetti(canvas, { count = 160, duration = 3200 } = {}) {
  if (!canvas || prefersReducedMotion()) return () => {};
  const ratio = window.devicePixelRatio || 1;
  const { width, height } = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(width * ratio));
  canvas.height = Math.max(1, Math.round(height * ratio));
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const styles = getComputedStyle(document.documentElement);
  const palette = COLORS.map(name => styles.getPropertyValue(`--color-${name}`).trim()).filter(Boolean);
  const pieces = Array.from({ length: count }, (_, i) => {
    // Two cannons from the lower corners, aimed up and towards the centre.
    const left = i % 2 === 0;
    const angle = (left ? -60 : -120) * Math.PI / 180 + (Math.random() - 0.5) * 0.9;
    const speed = 7 + Math.random() * 9;
    return { x: left ? width * 0.1 : width * 0.9, y: height * 0.95, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      size: 5 + Math.random() * 6, spin: (Math.random() - 0.5) * 0.4, rotation: Math.random() * Math.PI,
      color: palette[i % palette.length] || '#f5c518', round: Math.random() < 0.3 };
  });
  const start = performance.now();
  let frame = 0;
  const draw = now => {
    const elapsed = now - start;
    ctx.clearRect(0, 0, width, height);
    ctx.globalAlpha = Math.max(0, Math.min(1, (duration - elapsed) / 600));
    for (const piece of pieces) {
      piece.vy += 0.25;
      piece.vx *= 0.99;
      piece.x += piece.vx;
      piece.y += piece.vy;
      piece.rotation += piece.spin;
      ctx.save();
      ctx.translate(piece.x, piece.y);
      ctx.rotate(piece.rotation);
      ctx.fillStyle = piece.color;
      if (piece.round) { ctx.beginPath(); ctx.arc(0, 0, piece.size / 2, 0, Math.PI * 2); ctx.fill(); }
      else ctx.fillRect(-piece.size / 2, -piece.size / 4, piece.size, piece.size / 2);
      ctx.restore();
    }
    if (elapsed < duration) frame = requestAnimationFrame(draw);
    else ctx.clearRect(0, 0, width, height);
  };
  frame = requestAnimationFrame(draw);
  return () => { cancelAnimationFrame(frame); ctx.clearRect(0, 0, width, height); };
}
