/** Lightweight canvas confetti; nothing runs when the viewer prefers reduced motion. */

const COLORS = ['brand', 'brand-ink', 'caution', 'good', 'notice', 'anime'];

export function prefersReducedMotion() {
  try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
}

/**
 * Celebrate over a canvas sized to its CSS box: two side cannons, a rain from the top and a second burst.
 * @param {HTMLCanvasElement} canvas - Overlay canvas; it should not capture pointer events.
 * @param {Object} [options]
 * @param {number} [options.count=420] - Number of pieces across all waves.
 * @param {number} [options.duration=6500] - Milliseconds before the last pieces fade out.
 * @returns {Function} Stops the animation and clears the canvas.
 */
export function launchConfetti(canvas, { count = 420, duration = 6500 } = {}) {
  if (!canvas || prefersReducedMotion()) return () => {};
  const ratio = window.devicePixelRatio || 1;
  const { width, height } = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(width * ratio));
  canvas.height = Math.max(1, Math.round(height * ratio));
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const styles = getComputedStyle(document.documentElement);
  const palette = COLORS.map(name => styles.getPropertyValue(`--color-${name}`).trim()).filter(Boolean);
  const piece = (x, y, angle, speed, delay) => ({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, delay,
    size: 7 + Math.random() * 8, spin: (Math.random() - 0.5) * 0.3, rotation: Math.random() * Math.PI,
    wobble: Math.random() * Math.PI * 2, color: palette[Math.floor(Math.random() * palette.length)] || '#f5c518',
    round: Math.random() < 0.25 });
  const cannon = (delay, n) => Array.from({ length: n }, (_, i) => {
    const left = i % 2 === 0;
    // Aimed up and towards the centre from the middle of each side.
    const angle = (left ? -55 : -125) * Math.PI / 180 + (Math.random() - 0.5) * 0.8;
    return piece(left ? 0 : width, height * 0.6, angle, 10 + Math.random() * 12, delay + Math.random() * 150);
  });
  const rain = Array.from({ length: Math.round(count * 0.4) }, () =>
    piece(Math.random() * width, -20, Math.PI / 2, 1 + Math.random() * 2, Math.random() * 2500));
  const pieces = [...cannon(0, Math.round(count * 0.35)), ...rain, ...cannon(1200, Math.round(count * 0.25))];
  const start = performance.now();
  let frame = 0;
  let last = start;
  const draw = now => {
    const elapsed = now - start;
    const step = Math.min(2, (now - last) / 16.7);  // Frame-rate independent motion.
    last = now;
    ctx.clearRect(0, 0, width, height);
    ctx.globalAlpha = Math.max(0, Math.min(1, (duration - elapsed) / 1000));
    for (const p of pieces) {
      if (elapsed < p.delay) continue;
      p.vy = Math.min(p.vy + 0.16 * step, 4.5);
      p.vx *= 0.985 ** step;
      p.wobble += 0.08 * step;
      p.x += (p.vx + Math.sin(p.wobble) * 0.8) * step;
      p.y += p.vy * step;
      p.rotation += p.spin * step;
      if (p.y > height + 20) continue;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);
      ctx.scale(1, Math.abs(Math.cos(p.wobble)) * 0.7 + 0.3);  // Flutter as the piece turns.
      ctx.fillStyle = p.color;
      if (p.round) { ctx.beginPath(); ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2); ctx.fill(); }
      else ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
      ctx.restore();
    }
    if (elapsed < duration) frame = requestAnimationFrame(draw);
    else ctx.clearRect(0, 0, width, height);
  };
  frame = requestAnimationFrame(draw);
  return () => { cancelAnimationFrame(frame); ctx.clearRect(0, 0, width, height); };
}
