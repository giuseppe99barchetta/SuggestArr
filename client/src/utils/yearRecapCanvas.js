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

export async function renderYearStory(canvas, data, story, index) {
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
  const text = (value, x, y, size, { weight = 700, ink = 'ink', align = 'left', width = 920 } = {}) => {
    ctx.textAlign = align;
    ctx.fillStyle = color(ink);
    ctx.font = `${weight} ${size}px ${family}`;
    while (ctx.measureText(value).width > width && size > 12) {
      size -= 1;
      ctx.font = `${weight} ${size}px ${family}`;
    }
    ctx.fillText(value, x, y);
  };
  const panel = (x, y, w, h, fill = 'panel-2') => {
    ctx.fillStyle = color(fill);
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 24);
    ctx.fill();
  };
  const image = (img, x, y, w, h) => {
    if (!img) return;
    const rect = containRect(img.naturalWidth, img.naturalHeight, x, y, w, h);
    ctx.drawImage(img, rect.x, rect.y, rect.width, rect.height);
  };
  const poster = (i, x, y, w, angle = 0) => {
    if (!data.titles[i]) return;
    const h = w * 1.5;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle * Math.PI / 180);
    ctx.shadowColor = color('canvas');
    ctx.shadowBlur = 45;
    ctx.shadowOffsetY = 20;
    panel(-w / 2, -h / 2, w, h);
    ctx.shadowBlur = ctx.shadowOffsetY = 0;
    ctx.beginPath();
    ctx.roundRect(-w / 2, -h / 2, w, h, 20);
    ctx.clip();
    if (posters[i]) image(posters[i], -w / 2, -h / 2, w, h);
    else text(data.titles[i].title, 0, 0, 24, { align: 'center', width: w - 20 });
    ctx.restore();
  };
  const fan = (y, w = 270) => fanLayout(data.titles.length).forEach(slot => {
    poster(slot.index, 540 + slot.x * (w / 246), y + slot.y * (w / 246), w, slot.angle);
  });
  const tile = (value, label, x, y, { w = 435, h = 178, size = 100 } = {}) => {
    panel(x, y, w, h);
    text(value, x + 28, y + (h >= 220 ? 150 : 105), size, { weight: 800, width: w - 56 });
    text(label, x + 28, y + h - 25, 26, { ink: 'ink-3', width: w - 56 });
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
      fan(1160, 270);
      text(data.scope === 'server' ? (data.activeUsers == null ? 'Your server, on screen.' : `${data.activeUsers} viewers. One great year.`) : 'Your year, on screen.', 540, 1560, 43, { align: 'center' });
      image(providerLogo, 397, 1610, 65, 60);
      text(data.providerLabel, 478, 1653, 35, { ink: 'ink-2', width: 250 });
      break;
    case 'discovery':
      headline('Discovery, on', 'autopilot.');
      text(number(data.requested.total), 76, 742, 200, { weight: 800 });
      text('titles requested by SuggestArr', 80, 812, 38, { ink: 'ink-2' });
      tile(number(data.requested.movies), 'movies requested', 80, 890);
      tile(number(data.requested.series), 'TV series requested', 565, 890);
      fan(1330, 210);
      text('A new favorite, without the search.', 540, 1630, 34, { align: 'center', ink: 'ink-2' });
      break;
    case 'watched':
      headline('You pressed', 'play.');
      if (!data.watched) {
        text('Watch activity', 80, 800, 76);
        text('not available yet.', 80, 895, 76);
        text('Your discoveries are already here.', 80, 1030, 37, { ink: 'ink-2' });
        text('Load watch activity to check your linked server.', 80, 1095, 30, { ink: 'ink-3' });
        fan(1410, 180);
        break;
      }
      image(providerLogo, 80, 555, 62, 62);
      text(`WATCHED ON ${data.providerLabel.toUpperCase()}`, 160, 598, 25, { ink: 'notice', width: 820 });
      tile(number(data.watched.movies), 'movies watched', 80, 700, { h: 240, size: 140 });
      tile(number(data.watched.episodes), 'episodes watched', 565, 700, { h: 240, size: 140 });
      text(`${number(data.watched.series)} TV series in the mix.`, 80, 1050, 49);
      poster(2, 320, 1340, 250, -12);
      poster(1, 720, 1340, 250, 10);
      text(data.isDemo ? 'The stories you made time for.' : data.provider === 'jellyfin' ? 'Last-played snapshot · Partial coverage' : 'Retained watch history · Partial coverage', 540, 1650, 30, { align: 'center', ink: 'ink-2' });
      break;
    case 'time': {
      const hasTime = data.watchMinutes != null;
      headline(hasTime ? 'Time well' : 'A year of', hasTime ? 'watched.' : 'discoveries.');
      text(hasTime ? `${number(Math.floor(data.watchMinutes / 60))}h` : number(data.requested.total), 76, 740, 177, { weight: 800 });
      text(hasTime ? `and ${data.watchMinutes % 60} minutes of good stories.` : 'recorded title requests this year.', 80, 817, 36, { ink: 'ink-2' });
      panel(60, 940, 960, 610, 'panel');
      text(hasTime ? 'YOUR YEAR IN HOURS' : 'SUGGESTARR REQUESTS BY MONTH', 100, 1015, 23, { ink: 'ink-3' });
      const metric = hasTime ? 'minutes' : 'requests';
      const peak = data.peakMonth[metric];
      data.monthly.forEach((month, i) => {
        const x = 103 + i * 74;
        const height = peak ? month[metric] / peak * 350 : 0;
        if (height) panel(x, 1435 - height, 48, height, month[metric] === peak ? 'caution' : 'brand');
        text(month.month, x + 24, 1484, 18, { align: 'center', ink: 'ink-3', width: 65 });
      });
      text(peak ? `${data.peakMonth.label} · ${number(hasTime ? peak / 60 : peak)} ${hasTime ? 'hours' : 'requests'}.` : 'Your first discoveries are ahead.', 540, 1630, 39, { align: 'center', ink: 'caution' });
      if (!hasTime) text('Actual watch time is not available.', 540, 1685, 27, { align: 'center', ink: 'ink-3' });
      break;
    }
    case 'genres':
      headline('Your kind', 'of stories.');
      if (!data.genres.length) {
        text('More discoveries.', 80, 810, 73);
        text('More of your story.', 80, 905, 73);
        text('Genre metadata is not available yet.', 80, 1030, 36, { ink: 'ink-3' });
        fan(1400, 200);
        break;
      }
      text(data.genres[0].label, 80, 703, 125, { weight: 800, width: 660 });
      text(`${data.genres[0].percent}%`, 1000, 700, 100, { weight: 800, align: 'right', ink: 'anime', width: 300 });
      data.genres.forEach((genre, i) => {
        const y = 850 + i * 125;
        text(genre.label, 80, y, 31);
        text(`${genre.percent}%`, 1000, y, 31, { align: 'right', ink: 'ink-2', width: 150 });
        panel(80, y + 24, 920, 20);
        panel(80, y + 24, 920 * genre.percent / 100, 20, ['anime', 'brand', 'notice', 'caution'][i]);
      });
      data.titles.forEach((_, i) => poster(i, 218 + i * 215, 1470, 166, (i - 1.5) * 4));
      text(data.isDemo ? 'Genres of your sample watch history.' : `Genre tags · ${data.genreCoverage} requested titles with metadata`, 540, 1650, 28, { align: 'center', ink: 'ink-3' });
      break;
    case 'titles':
      headline(data.isDemo ? 'The titles that' : 'Your recent', data.isDemo ? 'defined your year.' : 'discoveries.');
      fan(1000, 280);
      if (!data.titles.length) text('Your next story is waiting.', 540, 1200, 50, { align: 'center', ink: 'ink-2' });
      data.titles.forEach((title, i) => {
        text(title.title, 80, 1435 + i * 66, 35, { width: 540 });
        text(title.detail, 1000, 1435 + i * 66, 23, { align: 'right', ink: 'ink-3', width: 350 });
      });
      break;
    case 'summary':
      headline('Your year,', 'wrapped.');
      tile(number(data.requested.total), 'titles requested', 80, 580);
      tile(number(data.watched?.movies ?? data.requested.movies), data.watched ? 'movies watched' : 'movies requested', 565, 580);
      tile(number(data.watched?.episodes ?? data.requested.series), data.watched ? 'episodes watched' : 'TV series requested', 80, 795);
      tile(data.watchMinutes == null ? '—' : `${number(Math.floor(data.watchMinutes / 60))}h`, data.watchMinutes == null ? 'watch time unavailable' : 'watch time', 565, 795);
      fan(1250, 210);
      text(data.isDemo ? 'YOUR LEADING GENRE' : 'LEADING GENRE OF YOUR REQUESTS', 540, 1540, 21, { align: 'center', ink: 'ink-3' });
      text(data.genres[0]?.label || 'Your story starts here', 540, 1620, 68, { align: 'center', weight: 800, ink: 'brand-ink' });
      break;
  }
  text(data.isDemo ? 'PREVIEW · SAMPLE DATA' : `RECORDED PROGRESS${data.isYearToDate ? ' · YEAR TO DATE' : ''}`, 540, 1748, 26, { align: 'center', ink: 'brand-ink' });
  const watchLabel = !data.isDemo && data.watched ? ' · Partial watch data' : '';
  text(`${data.scope === 'server' ? 'Server recap' : 'Personal recap'} · ${data.providerLabel}${watchLabel}`, 540, 1795, 23, { align: 'center', ink: 'ink-3' });
  text('github.com/giuseppe99barchetta/SuggestArr', 540, 1850, 24, { align: 'center', ink: 'ink-2' });
  text(`${index + 1} / 7`, 995, 1890, 15, { align: 'right', ink: 'ink-4', width: 90 });
  return { missingPosters: posters.filter((poster, i) => data.titles[i].artwork && !poster).length };
}
