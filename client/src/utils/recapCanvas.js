/** One local renderer for the preview and the exported PNG. */
import { drawCinemaPattern } from './cinemaIcons.js';

export const PROJECT_URL = 'https://github.com/giuseppe99barchetta/SuggestArr';

export function recapShareTargets(recap, options = {}) {
  const title = options.title ?? `${recap.total.toLocaleString('en-US')} titles requested with SuggestArr`;
  const caption = options.caption ?? recapCaption(recap);
  const query = values => new URLSearchParams(values).toString();
  return [
    { id: 'reddit', label: 'Reddit', icon: 'fab fa-reddit-alien', url: `https://www.reddit.com/submit?${query({ title, type: 'IMAGE' })}` },
    { id: 'discord', label: 'Discord', icon: 'fab fa-discord', url: 'https://discord.com/channels/@me' },
    { id: 'x', label: 'X', icon: 'fab fa-x-twitter', url: `https://twitter.com/intent/tweet?${query({ text: caption })}` },
    { id: 'bluesky', label: 'Bluesky', icon: 'fab fa-bluesky', url: `https://bsky.app/intent/compose?${query({ text: caption })}` },
  ];
}

export function recapCaption(recap) {
  return `${recap.total.toLocaleString('en-US')} titles requested with SuggestArr — ${recap.movies.toLocaleString('en-US')} movies and ${recap.tv.toLocaleString('en-US')} TV series. Less searching. More watching. ${PROJECT_URL}`;
}

export function posterUrl(path) {
  if (!path || typeof path !== 'string') return null;
  try {
    const url = new URL(path.startsWith('/') ? `https://image.tmdb.org/t/p/w342${path}` : path);
    if (url.protocol !== 'https:' || url.hostname !== 'image.tmdb.org' || !url.pathname.startsWith('/t/p/')) return null;
    return url.href;
  } catch { return null; }
}

export function loadImage(url, timeout = 5000) {
  return new Promise(resolve => {
    const img = new Image();
    let timer;
    const finish = value => {
      clearTimeout(timer);
      img.onload = null;
      img.onerror = null;
      resolve(value);
    };
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      // Test each image in isolation: one tainted image must never poison the recap.
      try {
        const probe = document.createElement('canvas');
        probe.width = probe.height = 1;
        probe.getContext('2d').drawImage(img, 0, 0, 1, 1);
        probe.toDataURL();
        finish(img);
      } catch { finish(null); }
    };
    img.onerror = () => finish(null);
    timer = setTimeout(() => finish(null), timeout);
    img.src = url;
  });
}

function cover(ctx, img, x, y, width, height) {
  const scale = Math.max(width / img.naturalWidth, height / img.naturalHeight);
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(x, y, width, height, 18);
  ctx.clip();
  ctx.drawImage(img, x + (width - img.naturalWidth * scale) / 2, y + (height - img.naturalHeight * scale) / 2,
    img.naturalWidth * scale, img.naturalHeight * scale);
  ctx.restore();
}

export function containRect(imageWidth, imageHeight, x, y, width, height) {
  const scale = Math.min(width / imageWidth, height / imageHeight);
  const drawnWidth = imageWidth * scale;
  const drawnHeight = imageHeight * scale;
  return { x: x + (width - drawnWidth) / 2, y: y + (height - drawnHeight) / 2, width: drawnWidth, height: drawnHeight };
}

export function fanLayout(count) {
  const layouts = {
    1: [{ index: 0, x: 0, y: 0, angle: -4 }],
    2: [{ index: 1, x: 114, y: 20, angle: 10 }, { index: 0, x: -114, y: 0, angle: -10 }],
    3: [{ index: 2, x: -236, y: 46, angle: -17 }, { index: 1, x: 236, y: 46, angle: 17 }, { index: 0, x: 0, y: -8, angle: -3 }],
    4: [{ index: 3, x: -258, y: 44, angle: -17 }, { index: 2, x: 258, y: 44, angle: 17 }, { index: 1, x: 94, y: 2, angle: 6 }, { index: 0, x: -94, y: -10, angle: -6 }],
  };
  return layouts[Math.max(1, Math.min(4, count))];
}

function fitText(ctx, value, maxWidth) {
  if (ctx.measureText(value).width <= maxWidth) return value;
  let shortened = value;
  while (shortened.length && ctx.measureText(`${shortened}…`).width > maxWidth) shortened = shortened.slice(0, -1);
  return `${shortened}…`;
}

export async function renderRecap(canvas, recap, { logoUrl, includePosters = true } = {}) {
  await document.fonts?.ready;
  const featured = includePosters ? recap.posters.slice(0, 4) : [];
  const [logo, ...images] = await Promise.all([
    logoUrl ? loadImage(logoUrl) : null,
    ...featured.map(poster => posterUrl(poster.poster_path)).map(url => url ? loadImage(url) : null),
  ]);
  canvas.width = 1080;
  canvas.height = 1350;
  const ctx = canvas.getContext('2d');
  const styles = getComputedStyle(document.documentElement);
  const color = name => styles.getPropertyValue(`--color-${name}`).trim();
  const font = styles.getPropertyValue('--font-sans').trim();
  const text = (value, x, y, size, weight = 600, ink = 'ink', maxWidth = 936) => {
    ctx.fillStyle = color(ink);
    ctx.font = `${weight} ${size}px ${font}`;
    // Canvas fillText(maxWidth) compresses glyphs horizontally. Fit by font size
    // instead so the artwork and all lettering retain their proportions.
    while (ctx.measureText(value).width > maxWidth && size > 12) {
      size -= 1;
      ctx.font = `${weight} ${size}px ${font}`;
    }
    ctx.fillText(value, x, y);
  };
  ctx.fillStyle = color('canvas');
  ctx.fillRect(0, 0, 1080, 1350);
  const glow = ctx.createRadialGradient(540, 710, 10, 540, 650, 850);
  glow.addColorStop(0, color('brand-soft'));
  glow.addColorStop(1, color('canvas'));
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, 1080, 1350);
  ctx.save();
  ctx.globalAlpha = 0.05;
  ctx.strokeStyle = color('ink');
  drawCinemaPattern(ctx, 7, { x: 70, y: 150, width: 940, height: 1130, count: 12 });
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
  // The logo already names the project: no slogan, URL or repeated "with SuggestArr".
  text(recap.scope === 'installation' ? 'OUR DISCOVERY RECAP' : 'MY DISCOVERY RECAP', 540, 228, 20, 700, 'brand-ink');
  text(recap.total.toLocaleString('en-US'), 540, 384, 150, 800);
  text('titles requested', 540, 436, 30, 500, 'ink-2');
  text(`${recap.movies.toLocaleString('en-US')} movies   ·   ${recap.tv.toLocaleString('en-US')} TV series`, 540, 499, 29, 700);

  // Fixed 2:3 portrait cards; never expand a lone cover into a wide banner.
  const cards = featured.length ? featured : Array.from({ length: 4 }, (_, index) => ({ title: ['DISCOVER', 'YOUR NEXT', 'FAVORITE', 'WITH SUGGESTARR'][index] }));
  fanLayout(cards.length).forEach(slot => {
    const img = images[slot.index];
    const card = cards[slot.index];
    ctx.save();
    ctx.translate(540 + slot.x, 800 + slot.y);
    ctx.rotate(slot.angle * Math.PI / 180);
    ctx.shadowColor = color('canvas');
    ctx.shadowBlur = 42;
    ctx.shadowOffsetY = 22;
    ctx.fillStyle = color('panel-2');
    ctx.beginPath();
    ctx.roundRect(-123, -184.5, 246, 369, 18);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;
    if (img) cover(ctx, img, -123, -184.5, 246, 369);
    else {
      const gradient = ctx.createLinearGradient(-123, -184, 123, 185);
      gradient.addColorStop(0, color('brand-soft'));
      gradient.addColorStop(1, color('panel'));
      ctx.fillStyle = gradient;
      ctx.fill();
      ctx.strokeStyle = color('brand');
      ctx.lineWidth = 2;
      ctx.strokeRect(-64, -95, 128, 168);
      ctx.beginPath();
      ctx.moveTo(-35, -39);
      ctx.lineTo(36, -2);
      ctx.lineTo(-35, 35);
      ctx.closePath();
      ctx.stroke();
    }
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(-123, -184.5, 246, 369, 18);
    ctx.clip();
    const shade = ctx.createLinearGradient(0, 45, 0, 185);
    shade.addColorStop(0, 'transparent');
    shade.addColorStop(0.45, color('canvas'));
    shade.addColorStop(1, color('canvas'));
    ctx.fillStyle = shade;
    ctx.fillRect(-123, 45, 246, 140);
    ctx.fillStyle = color('ink');
    ctx.font = `700 19px ${font}`;
    ctx.fillText(fitText(ctx, card.title || 'Artwork unavailable', 214), 0, 157);
    if (card.rating) {
      ctx.fillStyle = color('caution');
      ctx.font = `700 17px ${font}`;
      ctx.fillText(`★ ${Number(card.rating).toFixed(1)}`, 0, 125);
    }
    ctx.restore();
    ctx.strokeStyle = color(slot.index === 0 ? 'brand-ink' : 'edge-strong');
    ctx.lineWidth = slot.index === 0 ? 2.5 : 1.5;
    ctx.beginPath();
    ctx.roundRect(-123, -184.5, 246, 369, 18);
    ctx.stroke();
    ctx.restore();
  });
  text('Good taste. On autopilot.', 540, 1150, 43, 800);
  const unlocked = recap.badges.filter(badge => badge.unlocked);
  const highest = unlocked.filter(badge => badge.kind === 'titles').at(-1) || unlocked.at(-1);
  if (highest) text(`★  ${highest.label}`, 540, 1215, 26, 700, 'brand-ink');
  return { missingPosters: includePosters && images.some(img => !img) };
}

export function canvasBlob(canvas, timeout = 1500) {
  return new Promise((resolve, reject) => {
    // Some browsers leave concurrent offscreen encodes pending indefinitely.
    // Keep the complete rendered frame exportable with a synchronous fallback.
    let settled = false;
    const finish = blob => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (blob) resolve(blob);
      else reject(new Error('Unable to generate PNG'));
    };
    const timer = setTimeout(() => {
      try {
        const bytes = Uint8Array.from(atob(canvas.toDataURL('image/png').split(',')[1]), c => c.charCodeAt(0));
        finish(new Blob([bytes], { type: 'image/png' }));
      } catch { finish(null); }
    }, timeout);
    try { canvas.toBlob(finish, 'image/png'); }
    catch { finish(null); }
  });
}
