/** A 1080×1350 PNG celebrating one badge, rendered locally like the recap image. */
import { containRect, loadImage, PROJECT_URL } from './recapCanvas.js';
import { drawCinemaPattern } from './cinemaIcons.js';
import { badgeMedallion, formatBadgeDate } from './recapBadges.js';

const KIND_LABELS = { titles: 'TITLE MILESTONE', watched: 'WATCHED SUGGESTIONS', variety: 'VARIETY BADGE',
  streak: 'WATCH STREAK', days: 'ANNIVERSARY' };
// Font Awesome glyphs are not available on canvas; variety badges use a star instead.
const STAR = '★';

export function badgeCaption(badge) {
  return `Badge unlocked on SuggestArr: ${badge.label} — ${badge.description}. ${PROJECT_URL}`;
}

/**
 * @param {HTMLCanvasElement} canvas
 * @param {Object} badge - Unlocked badge from the recap API.
 * @param {Object} [options]
 * @param {string} [options.logoUrl] - Project logo drawn in the header.
 */
export async function renderBadgeCard(canvas, badge, { logoUrl } = {}) {
  await document.fonts?.ready;
  const logo = logoUrl ? await loadImage(logoUrl) : null;
  canvas.width = 1080;
  canvas.height = 1350;
  const ctx = canvas.getContext('2d');
  const styles = getComputedStyle(document.documentElement);
  const color = name => styles.getPropertyValue(`--color-${name}`).trim();
  const family = styles.getPropertyValue('--font-sans').trim();
  const text = (value, x, y, size, weight = 700, ink = 'ink', maxWidth = 920) => {
    ctx.fillStyle = color(ink);
    ctx.font = `${weight} ${size}px ${family}`;
    while (ctx.measureText(value).width > maxWidth && size > 12) ctx.font = `${weight} ${--size}px ${family}`;
    ctx.fillText(value, x, y);
  };
  ctx.fillStyle = color('canvas');
  ctx.fillRect(0, 0, 1080, 1350);
  const glow = ctx.createRadialGradient(540, 560, 10, 540, 560, 760);
  glow.addColorStop(0, color('brand-soft'));
  glow.addColorStop(1, color('canvas'));
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, 1080, 1350);
  ctx.save();
  ctx.globalAlpha = 0.05;
  ctx.strokeStyle = color('ink');
  drawCinemaPattern(ctx, badge.id.length * 13, { x: 70, y: 150, width: 940, height: 1130, count: 12 });
  ctx.restore();
  ctx.strokeStyle = color('edge-strong');
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(28, 28, 1024, 1294, 36);
  ctx.stroke();
  if (logo) {
    const rect = containRect(logo.naturalWidth, logo.naturalHeight, 72, 70, 106, 60);
    ctx.drawImage(logo, rect.x, rect.y, rect.width, rect.height);
  }
  text('SuggestArr', logo ? 194 : 72, 114, 38, 800);

  ctx.textAlign = 'center';
  text('BADGE UNLOCKED', 540, 260, 28, 700, 'brand-ink');
  // Medallion with rays.
  ctx.save();
  ctx.translate(540, 560);
  ctx.strokeStyle = color('brand');
  ctx.globalAlpha = 0.35;
  ctx.lineWidth = 6;
  for (let i = 0; i < 24; i += 1) {
    const angle = i * Math.PI / 12;
    ctx.beginPath();
    ctx.moveTo(Math.cos(angle) * 220, Math.sin(angle) * 220);
    ctx.lineTo(Math.cos(angle) * (i % 2 ? 250 : 275), Math.sin(angle) * (i % 2 ? 250 : 275));
    ctx.stroke();
  }
  ctx.restore();
  ctx.fillStyle = color('brand-soft');
  ctx.beginPath();
  ctx.arc(540, 560, 190, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = color('brand-ink');
  ctx.lineWidth = 8;
  ctx.stroke();
  ctx.lineWidth = 2;
  ctx.globalAlpha = 0.5;
  ctx.beginPath();
  ctx.arc(540, 560, 160, 0, Math.PI * 2);
  ctx.stroke();
  ctx.globalAlpha = 1;
  const medallion = badgeMedallion(badge);
  if (medallion.icon) text(STAR, 540, 615, 150, 800, 'brand-ink', 300);
  else {
    text(medallion.text, 540, 600, 130, 800, 'brand-ink', 300);
    text(medallion.unit.toUpperCase(), 540, 660, 30, 700, 'brand-ink', 260);
  }
  text(badge.label, 540, 900, 76, 800);
  text(badge.description, 540, 975, 36, 600, 'ink-2');
  text(KIND_LABELS[badge.kind] || 'BADGE', 540, 1090, 24, 700, 'ink-3');
  if (badge.unlocked_at) text(`Unlocked ${formatBadgeDate(badge.unlocked_at)}`, 540, 1140, 30, 600, 'ink-3');
  text('Good taste. On autopilot.', 540, 1250, 34, 800, 'brand-ink');
  ctx.textAlign = 'left';
}
