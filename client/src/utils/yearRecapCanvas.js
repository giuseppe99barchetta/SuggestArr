/** One final-frame renderer for annual story previews and 1080×1920 PNGs. */
import { containRect, fanLayout, loadImage } from './recapCanvas.js';

const logoUrl = new URL('../assets/logo.png', import.meta.url).href;
const providerLogos = {
  jellyfin: new URL('../assets/logos/jellyfin-logo.svg', import.meta.url).href,
  plex: new URL('../assets/logos/plex-logo.svg', import.meta.url).href,
};
const images = new Map();
const asset = url => {
  if (!url) return Promise.resolve(null);
  if (!images.has(url)) images.set(url, loadImage(url));
  return images.get(url);
};
const number = value => value == null ? '—' : value.toLocaleString('en-US');
const percent = (part, total) => total ? Math.round(part / total * 100) : 0;
// Title cards stand in for covers that could not be loaded; each gets its own tint.
const CARD_TINTS = ['brand', 'anime', 'notice', 'good'];

export async function renderYearStory(canvas, data, story) {
  await document.fonts?.ready;
  const [logo, providerLogo, ...posters] = await Promise.all([
    asset(logoUrl), asset(providerLogos[data.provider]), ...data.titles.map(title => asset(title.artwork)),
  ]);
  canvas.width = 1080;
  canvas.height = 1920;
  const ctx = canvas.getContext('2d');
  const styles = getComputedStyle(document.documentElement);
  const color = name => styles.getPropertyValue(`--color-${name}`).trim();
  const family = styles.getPropertyValue('--font-sans').trim();
  const font = (size, weight) => { ctx.font = `${weight} ${size}px ${family}`; };
  const text = (value, x, y, size, { weight = 700, ink = 'ink', align = 'left', width = 920 } = {}) => {
    ctx.textAlign = align;
    ctx.fillStyle = color(ink);
    font(size, weight);
    while (ctx.measureText(value).width > width && size > 12) font(--size, weight);
    ctx.fillText(value, x, y);
  };
  /** Word-wrapped text from baseline `y`; returns the baseline of the last line drawn. */
  const paragraph = (value, x, y, size, { weight = 700, width = 920, max = 2, leading = 1.18, ...options } = {}) => {
    font(size, weight);
    const lines = [];
    for (const word of String(value).split(/\s+/)) {
      const next = lines.length ? `${lines.at(-1)} ${word}` : word;
      if (lines.length && ctx.measureText(next).width <= width) lines[lines.length - 1] = next;
      else lines.push(word);
    }
    if (lines.length > max) {
      lines.length = max;
      let last = lines[max - 1];
      while (last.length > 1 && ctx.measureText(`${last}…`).width > width) last = last.slice(0, -1).trimEnd();
      lines[max - 1] = `${last}…`;
    }
    lines.forEach((line, i) => text(line, x, y + i * size * leading, size, { weight, width, ...options }));
    return y + (lines.length - 1) * size * leading;
  };
  const panel = (x, y, w, h, fill = 'panel-2', radius = 24) => {
    ctx.fillStyle = color(fill);
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, radius);
    ctx.fill();
  };
  const image = (img, x, y, w, h) => {
    if (!img) return;
    const rect = containRect(img.naturalWidth, img.naturalHeight, x, y, w, h);
    ctx.drawImage(img, rect.x, rect.y, rect.width, rect.height);
  };
  const titleCard = (i, w, h, label) => {
    const tint = ctx.createLinearGradient(0, -h / 2, 0, h / 2);
    tint.addColorStop(0, color(CARD_TINTS[i % CARD_TINTS.length]));
    tint.addColorStop(1, color('panel-2'));
    ctx.save();
    ctx.globalAlpha = 0.55;
    ctx.fillStyle = tint;
    ctx.fillRect(-w / 2, -h / 2, w, h);
    ctx.restore();
    if (!label) return;
    const size = Math.round(w * 0.12);
    const pad = w * 0.1;
    // Bottom-aligned like a real poster title; long names wrap instead of being cut.
    const lines = Math.min(3, Math.ceil(data.titles[i].title.length / 12));
    paragraph(data.titles[i].title, -w / 2 + pad, h / 2 - pad - (lines - 1) * size * 1.12, size,
      { weight: 800, width: w - pad * 2, max: 3, leading: 1.12 });
  };
  /** `label` writes the title on a stand-in card; off where the title is printed next to it. */
  const poster = (i, x, y, w, angle = 0, label = true) => {
    if (!data.titles[i]) return;
    const h = w * 1.5;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle * Math.PI / 180);
    ctx.shadowColor = color('canvas');
    ctx.shadowBlur = 45;
    ctx.shadowOffsetY = 20;
    panel(-w / 2, -h / 2, w, h, 'panel-2', 20);
    ctx.shadowBlur = ctx.shadowOffsetY = 0;
    ctx.beginPath();
    ctx.roundRect(-w / 2, -h / 2, w, h, 20);
    ctx.clip();
    if (posters[i]) image(posters[i], -w / 2, -h / 2, w, h);
    else titleCard(i, w, h, label);
    ctx.restore();
  };
  const fan = (y, w = 270) => fanLayout(data.titles.length).forEach(slot => {
    poster(slot.index, 540 + slot.x * (w / 246), y + slot.y * (w / 246), w, slot.angle);
  });
  /** Straight, evenly spaced covers centred on `y`; returns each cover's centre x. */
  const posterRow = (y, w, gap = 30, label = true) => {
    const count = Math.min(4, data.titles.length);
    const start = 540 - (count * w + (count - 1) * gap) / 2 + w / 2;
    const centres = Array.from({ length: count }, (_, i) => start + i * (w + gap));
    centres.forEach((x, i) => poster(i, x, y, w, 0, label));
    return centres;
  };
  const tile = (value, label, x, y, { w = 435, h = 178, size = 100 } = {}) => {
    panel(x, y, w, h);
    text(value, x + 28, y + (h >= 220 ? 150 : 105), size, { weight: 800, width: w - 56 });
    text(label, x + 28, y + h - 25, 26, { ink: 'ink-3', width: w - 56 });
  };
  /** Full-width stat row: big number on the left, label on the right. */
  const statRow = (value, label, y) => {
    panel(80, y, 920, 215);
    text(value, 120, y + 150, 124, { weight: 800, width: 480 });
    text(label, 960, y + 128, 38, { ink: 'ink-2', align: 'right', width: 380 });
  };
  const headline = (first, second) => {
    text(first, 80, 395, 83, { weight: 800 });
    if (second) text(second, 80, 491, 83, { weight: 800 });
  };

  ctx.fillStyle = color('canvas');
  ctx.fillRect(0, 0, 1080, 1920);
  const glow = ctx.createRadialGradient(860, 950, 0, 540, 900, 1200);
  glow.addColorStop(0, color(story.accent));
  glow.addColorStop(1, color('canvas'));
  ctx.save();
  ctx.globalAlpha = 0.32;
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, 1080, 1920);
  ctx.restore();
  ctx.strokeStyle = color('edge-strong');
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(26, 26, 1028, 1868, 40);
  ctx.stroke();
  image(logo, 76, 80, 114, 64);
  text('SuggestArr', logo ? 210 : 76, 128, 43, { weight: 800 });
  text(String(data.year), 1000, 125, 30, { ink: 'ink-3', align: 'right', width: 120 });
  text(story.kicker, 80, 274, 23, { ink: story.accent });

  switch (story.id) {
    case 'intro':
      text(String(data.year), 70, 570, 250, { weight: 800 });
      text('Good stories.', 80, 680, 67, { weight: 800 });
      text('Even better discoveries.', 80, 766, 62, { weight: 800 });
      fan(1210, 270);
      text(data.scope === 'server' ? (data.activeUsers == null ? 'Your server, on screen.' : `${data.activeUsers} viewers. One great year.`) : 'Your year, on screen.', 540, 1620, 46, { align: 'center' });
      break;
    case 'discovery': {
      const { total, movies, series } = data.requested;
      headline('Discovery, on', 'autopilot.');
      text(number(total), 76, 742, 200, { weight: 800 });
      text('titles requested by SuggestArr', 80, 812, 38, { ink: 'ink-2' });
      tile(number(movies), 'movies', 80, 900, { h: 240, size: 140 });
      tile(number(series), 'TV series', 565, 900, { h: 240, size: 140 });
      if (total) {
        // Movies vs TV split, so the two counts read as one picture.
        const split = 920 * movies / total;
        panel(80, 1250, 920, 28, 'panel-2', 14);
        if (movies) panel(80, 1250, split, 28, 'brand', 14);
        text(`${percent(movies, total)}% movies`, 80, 1330, 30, { ink: 'ink-2', width: 440 });
        text(`${percent(series, total)}% TV series`, 1000, 1330, 30, { ink: 'ink-2', align: 'right', width: 440 });
      }
      text('A new favorite, without the search.', 540, 1560, 40, { align: 'center', ink: 'ink-2' });
      break;
    }
    case 'watched':
      headline('You pressed', 'play.');
      image(providerLogo, 80, 555, 62, 62);
      text(`WATCHED ON ${String(data.providerLabel).toUpperCase()}`, 160, 598, 25, { ink: 'notice', width: 820 });
      statRow(number(data.watched?.movies), 'movies', 700);
      statRow(number(data.watched?.episodes), 'episodes', 945);
      statRow(number(data.watched?.series), 'TV series', 1190);
      text(data.isDemo ? 'The stories you made time for.' : data.provider === 'jellyfin' ? 'Last-played snapshot · Partial coverage' : 'Retained watch history · Partial coverage', 540, 1580, 34, { align: 'center', ink: 'ink-2' });
      break;
    case 'time': {
      const hasTime = data.watchMinutes != null;
      const metric = hasTime ? 'minutes' : 'requests';
      const peak = data.peakMonth[metric];
      headline(hasTime ? 'Time well' : 'A year of', hasTime ? 'watched.' : 'discoveries.');
      if (hasTime) {
        text(`${number(Math.floor(data.watchMinutes / 60))}h`, 76, 740, 177, { weight: 800 });
        text(`and ${data.watchMinutes % 60} minutes of good stories.`, 80, 817, 36, { ink: 'ink-2' });
      } else {
        // The request total is already on the discovery story; lead with the busiest month instead.
        text(peak ? data.peakMonth.label : 'Just started.', 76, 720, 150, { weight: 800 });
        text(peak ? `your busiest month · ${number(peak)} requests` : 'Your first discoveries are ahead.', 80, 817, 36, { ink: 'ink-2' });
      }
      panel(60, 940, 960, 610, 'panel');
      text(hasTime ? 'YOUR YEAR IN HOURS' : 'REQUESTS BY MONTH', 100, 1015, 23, { ink: 'ink-3' });
      data.monthly.forEach((month, i) => {
        const x = 103 + i * 74;
        const height = peak ? month[metric] / peak * 350 : 0;
        if (height) panel(x, 1435 - height, 48, height, month[metric] === peak ? 'caution' : 'brand');
        text(month.month, x + 24, 1484, 18, { align: 'center', ink: 'ink-3', width: 65 });
      });
      if (hasTime && peak) text(`${data.peakMonth.label} · ${number(Math.round(peak / 60))} hours.`, 540, 1640, 42, { align: 'center', ink: 'caution' });
      break;
    }
    case 'genres': {
      const [top, ...rest] = data.genres;
      headline('Your kind', 'of stories.');
      text(top.label, 76, 740, 150, { weight: 800 });
      text(`${top.percent}% of your ${data.isDemo ? 'history' : 'requests'}`, 80, 815, 38, { ink: 'anime' });
      if (rest.length) text('ALSO IN THE MIX', 80, 960, 23, { ink: 'ink-3' });
      rest.slice(0, 3).forEach((genre, i) => {
        const y = 1050 + i * 140;
        text(genre.label, 80, y, 38);
        text(`${genre.percent}%`, 1000, y, 38, { align: 'right', ink: 'ink-2', width: 150 });
        panel(80, y + 30, 920, 22, 'panel-2', 11);
        panel(80, y + 30, Math.max(22, 920 * genre.percent / 100), 22, ['brand', 'notice', 'caution'][i], 11);
      });
      text(data.isDemo ? 'Based on your sample watch history.' : `Based on ${number(data.genreCoverage)} requested titles.`, 540, 1600, 30, { align: 'center', ink: 'ink-3' });
      break;
    }
    case 'titles':
      headline(data.isDemo ? 'The titles that' : 'Your recent', data.isDemo ? 'defined your year.' : 'discoveries.');
      if (data.titles.length <= 2) {
        // One or two titles get large covers instead of a mostly empty list.
        const w = data.titles.length === 1 ? 400 : 360;
        posterRow(1030, w, 60, false).forEach((x, i) => {
          const last = paragraph(data.titles[i].title, x, 1400, 46, { weight: 800, width: w + 20, max: 2, leading: 1.12, align: 'center' });
          text(data.titles[i].detail, x, last + 50, 30, { ink: 'ink-3', align: 'center', width: w + 20 });
        });
        break;
      }
      // A ranked list with covers: every title stays whole and readable.
      data.titles.slice(0, 4).forEach((title, i) => {
        const y = 590 + i * 260;
        poster(i, 155, y + 112, 150, 0, false);
        text(String(i + 1).padStart(2, '0'), 270, y + 62, 30, { weight: 800, ink: 'good' });
        const last = paragraph(title.title, 270, y + 122, 48, { weight: 800, width: 730, max: 2, leading: 1.12 });
        text(title.detail, 270, last + 50, 30, { ink: 'ink-3', width: 730 });
      });
      break;
    case 'summary': {
      headline('Your year,', 'wrapped.');
      const stats = [
        [number(data.requested.total), 'titles requested'],
        data.watched ? [number(data.watched.movies), 'movies watched'] : [number(data.requested.movies), 'movies requested'],
        data.watched ? [number(data.watched.episodes), 'episodes watched'] : [number(data.requested.series), 'TV series requested'],
        data.watchMinutes != null ? [`${number(Math.floor(data.watchMinutes / 60))}h`, 'watch time'] : null,
        data.genres[0] ? [data.genres[0].label, 'leading genre'] : null,
      ].filter(Boolean).slice(0, 4);
      stats.forEach(([value, label], i) => {
        const wide = i === stats.length - 1 && stats.length % 2;
        tile(value, label, i % 2 ? 565 : 80, 580 + Math.floor(i / 2) * 215, wide ? { w: 920 } : undefined);
      });
      posterRow(1250, 190);
      text('Here’s to more good stories.', 540, 1590, 44, { align: 'center', ink: 'brand-ink' });
      break;
    }
  }
  const meta = [data.isDemo ? 'Sample data' : null, data.scope === 'server' ? 'Server recap' : 'Personal recap',
    data.providerLabel, !data.isDemo && data.isYearToDate ? 'Year to date' : null].filter(Boolean).join(' · ');
  text(meta, 540, 1790, 25, { align: 'center', ink: data.isDemo ? 'brand-ink' : 'ink-3' });
  text('github.com/giuseppe99barchetta/SuggestArr', 540, 1845, 24, { align: 'center', ink: 'ink-2' });
  return { missingPosters: posters.filter((poster, i) => data.titles[i].artwork && !poster).length };
}
