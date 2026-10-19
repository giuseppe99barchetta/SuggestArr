/**
 * Line-art cinema and TV icons drawn straight onto a canvas, so story PNGs
 * need no icon font or external artwork. Each icon fits a 100×100 box centred on (x, y).
 */
const circle = (ctx, x, y, r) => { ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, Math.PI * 2); };

const ICONS = {
  clapper(ctx) {
    ctx.roundRect(-40, -8, 80, 48, 6);
    for (const x of [-22, 2, 26]) { ctx.moveTo(x, -8); ctx.lineTo(x - 12, 6); }
    ctx.save();
    ctx.translate(-40, -14);
    ctx.rotate(-0.22);
    ctx.roundRect(0, -14, 80, 14, 4);
    for (const x of [16, 40, 64]) { ctx.moveTo(x, -14); ctx.lineTo(x - 10, 0); }
    ctx.restore();
  },
  ticket(ctx) {
    ctx.moveTo(-44, -26);
    ctx.lineTo(44, -26);
    ctx.lineTo(44, -10);
    ctx.arc(44, 0, 10, -Math.PI / 2, Math.PI / 2, true);
    ctx.lineTo(44, 26);
    ctx.lineTo(-44, 26);
    ctx.lineTo(-44, 10);
    ctx.arc(-44, 0, 10, Math.PI / 2, -Math.PI / 2, true);
    ctx.closePath();
    for (let y = -20; y <= 14; y += 12) { ctx.moveTo(18, y); ctx.lineTo(18, y + 6); }
    ctx.moveTo(-30, -6); ctx.lineTo(4, -6);
    ctx.moveTo(-30, 8); ctx.lineTo(-6, 8);
  },
  tv(ctx) {
    ctx.roundRect(-44, -24, 88, 58, 8);
    ctx.moveTo(-18, -42); ctx.lineTo(0, -24); ctx.lineTo(18, -42);
    ctx.moveTo(-16, 44); ctx.lineTo(16, 44);
    ctx.moveTo(-8, -6); ctx.lineTo(14, 5); ctx.lineTo(-8, 16); ctx.closePath();
  },
  popcorn(ctx) {
    ctx.moveTo(-30, -2); ctx.lineTo(30, -2); ctx.lineTo(22, 44); ctx.lineTo(-22, 44); ctx.closePath();
    ctx.moveTo(-10, -2); ctx.lineTo(-7, 44);
    ctx.moveTo(10, -2); ctx.lineTo(7, 44);
    circle(ctx, -20, -12, 11);
    circle(ctx, 0, -18, 13);
    circle(ctx, 20, -12, 11);
    circle(ctx, -9, -34, 10);
    circle(ctx, 12, -34, 10);
  },
  masks(ctx) {
    // Comedy and tragedy, tilted apart.
    for (const [x, y, angle, smile] of [[-15, -6, -0.28, true], [17, 8, 0.28, false]]) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle);
      ctx.moveTo(-21, -26);
      ctx.lineTo(21, -26);
      ctx.quadraticCurveTo(24, 14, 0, 30);
      ctx.quadraticCurveTo(-24, 14, -21, -26);
      ctx.moveTo(-14, -9); ctx.quadraticCurveTo(-9, -15, -4, -9);
      ctx.moveTo(4, -9); ctx.quadraticCurveTo(9, -15, 14, -9);
      if (smile) { ctx.moveTo(-9, 6); ctx.quadraticCurveTo(0, 16, 9, 6); } else { ctx.moveTo(-9, 14); ctx.quadraticCurveTo(0, 4, 9, 14); }
      ctx.restore();
    }
  },
  reel(ctx) {
    circle(ctx, 0, 0, 42);
    circle(ctx, 0, 0, 6);
    for (let i = 0; i < 5; i += 1) {
      const angle = -Math.PI / 2 + i * Math.PI * 2 / 5;
      circle(ctx, Math.cos(angle) * 24, Math.sin(angle) * 24, 9);
    }
  },
  star(ctx) {
    for (let i = 0; i < 10; i += 1) {
      const angle = -Math.PI / 2 + i * Math.PI / 5;
      const r = i % 2 ? 19 : 44;
      ctx[i ? 'lineTo' : 'moveTo'](Math.cos(angle) * r, Math.sin(angle) * r + 4);
    }
    ctx.closePath();
  },
  film(ctx) {
    ctx.roundRect(-26, -46, 52, 92, 6);
    ctx.moveTo(-14, -46); ctx.lineTo(-14, 46);
    ctx.moveTo(14, -46); ctx.lineTo(14, 46);
    for (let y = -36; y <= 30; y += 16) { ctx.rect(-22, y, 4, 6); ctx.rect(18, y, 4, 6); }
  },
  play(ctx) {
    circle(ctx, 0, 0, 42);
    ctx.moveTo(-12, -20); ctx.lineTo(22, 0); ctx.lineTo(-12, 20); ctx.closePath();
  },
};

export const CINEMA_ICONS = Object.keys(ICONS);

/**
 * Stroke one icon.
 * @param {CanvasRenderingContext2D} ctx - Target context; strokeStyle and globalAlpha are the caller's.
 * @param {string} name - One of CINEMA_ICONS.
 * @param {number} x - Centre x.
 * @param {number} y - Centre y.
 * @param {number} size - Rendered width and height of the 100×100 icon box.
 * @param {number} angle - Rotation in degrees.
 */
export function drawCinemaIcon(ctx, name, x, y, size, angle = 0) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle * Math.PI / 180);
  ctx.scale(size / 100, size / 100);
  ctx.lineWidth = 6;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  ICONS[name](ctx);
  ctx.stroke();
  ctx.restore();
}

/**
 * Scatter faint icons over the background, laid out from a fixed seed so every
 * render of the same story, preview and PNG alike, is identical.
 * @param {CanvasRenderingContext2D} ctx - Target context; strokeStyle is the caller's.
 * @param {number} seed - Varies the pattern between stories.
 * @param {{x?: number, y?: number, width: number, height: number, count?: number}} area - Box the icons stay inside, and how many.
 */
export function drawCinemaPattern(ctx, seed, { x: left = 0, y: top = 0, width, height, count = 16 }) {
  let state = seed * 9301 + 49297;
  const random = () => { state = (state * 9301 + 49297) % 233280; return state / 233280; };
  const columns = 4;
  const rows = Math.ceil(count / columns);
  for (let i = 0; i < count; i += 1) {
    // One icon per grid cell, jittered inside it, so the pattern never clumps.
    const x = left + (i % columns + 0.2 + random() * 0.6) * width / columns;
    const y = top + (Math.floor(i / columns) + 0.2 + random() * 0.6) * height / rows;
    const name = CINEMA_ICONS[Math.floor(random() * CINEMA_ICONS.length)];
    drawCinemaIcon(ctx, name, x, y, 70 + random() * 40, (random() - 0.5) * 50);
  }
}
