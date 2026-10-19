/** Fictional, internally consistent data. No server activity is read here. */
export const YEAR_RECAP_STORIES = [
  { id: 'intro', title: 'Your 2026, on screen', kicker: 'THE YEAR IN STORIES', accent: 'brand' },
  { id: 'discovery', title: 'Discovery, on autopilot', kicker: 'SUGGESTARR DISCOVERIES', accent: 'brand' },
  { id: 'watched', title: 'You pressed play', kicker: 'YOUR WATCH HISTORY', accent: 'notice' },
  { id: 'time', title: 'Time well watched', kicker: 'MAKE TIME FOR GOOD STORIES', accent: 'caution' },
  { id: 'genres', title: 'Your kind of stories', kicker: 'YOUR VIEWING DNA', accent: 'anime' },
  { id: 'titles', title: 'The titles that defined your year', kicker: 'THE LEADING TITLES', accent: 'good' },
  { id: 'summary', title: 'Your year, wrapped', kicker: 'A YEAR WORTH SHARING', accent: 'brand' },
];

export const DEMO_TITLES = [
  { title: 'Orbit', detail: 'Movie · Sci-fi', artwork: new URL('../assets/recap-demo/orbit.svg', import.meta.url).href },
  { title: 'Afterlight', detail: 'Movie · Drama', artwork: new URL('../assets/recap-demo/afterlight.svg', import.meta.url).href },
  { title: 'Night Signal', detail: 'TV series · Thriller', artwork: new URL('../assets/recap-demo/night-signal.svg', import.meta.url).href },
  { title: 'The Last Horizon', detail: 'Movie · Adventure', artwork: new URL('../assets/recap-demo/horizon.svg', import.meta.url).href },
];

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MINUTES = [1200, 1260, 1380, 1440, 1500, 1560, 1500, 1620, 1800, 3060, 1800, 740];
const REQUESTS = [12, 14, 17, 16, 20, 22, 21, 23, 27, 31, 24, 21];

export function createYearRecapDemo(scope = 'personal', provider = 'jellyfin') {
  const factor = scope === 'server' ? 5 : 1;
  const monthly = MONTHS.map((month, i) => ({ month,
    label: new Date(Date.UTC(2026, i, 1)).toLocaleString('en-US', { month: 'long', timeZone: 'UTC' }),
    minutes: MINUTES[i] * factor, requests: REQUESTS[i] * factor }));
  return {
    year: 2026, isDemo: true, scope: scope === 'server' ? 'server' : 'personal',
    provider: provider === 'plex' ? 'plex' : 'jellyfin',
    providerLabel: provider === 'plex' ? 'Plex' : 'Jellyfin',
    activeUsers: scope === 'server' ? 12 : 1,
    requested: { total: 248 * factor, movies: 176 * factor, series: 72 * factor },
    watched: { movies: 82 * factor, episodes: 410 * factor, series: 34 * factor },
    watchMinutes: monthly.reduce((sum, month) => sum + month.minutes, 0),
    monthly, peakMonth: monthly.reduce((peak, month) => month.minutes > peak.minutes ? month : peak),
    genres: [{ label: 'Sci-fi', percent: 38 }, { label: 'Drama', percent: 27 }, { label: 'Thriller', percent: 21 }, { label: 'Animation', percent: 14 }],
    titles: DEMO_TITLES.map(title => ({ ...title })),
  };
}

export function yearRecapCaption(data, story) {
  const hours = Math.floor(data.watchMinutes / 60);
  return `${data.year} Year Recap · Preview / Sample data. ${story.title}. ${data.requested.total.toLocaleString('en-US')} requested · ${data.watched.movies.toLocaleString('en-US')} movies · ${data.watched.episodes.toLocaleString('en-US')} episodes · ${hours.toLocaleString('en-US')}h on ${data.providerLabel}. https://github.com/giuseppe99barchetta/SuggestArr`;
}

/** Story text without its title, for the side panel next to the rendered image. */
export function storyDetail(data, story) {
  const descriptions = {
    intro: `${data.scope === 'server' ? `Server recap for ${data.activeUsers} active viewers` : 'Your personal recap'} on ${data.providerLabel}.`,
    discovery: `${data.requested.total} titles requested: ${data.requested.movies} movies and ${data.requested.series} TV series.`,
    watched: `${data.watched.movies} movies, ${data.watched.episodes} episodes and ${data.watched.series} TV series watched on ${data.providerLabel}.`,
    time: `${Math.floor(data.watchMinutes / 60)} hours and ${data.watchMinutes % 60} minutes watched. ${data.peakMonth.label} was the busiest month with ${data.peakMonth.minutes / 60} hours.`,
    genres: data.genres.map(genre => `${genre.label} ${genre.percent}%`).join(', '),
    titles: data.titles.map(title => `${title.title}, ${title.detail}`).join('; '),
    summary: `${data.requested.total} titles requested, ${data.watched.movies} movies and ${data.watched.episodes} episodes watched. Leading genre: ${data.genres[0].label}.`,
  };
  return descriptions[story.id];
}

export function storyDescription(data, story) {
  return `${story.title}. ${storyDetail(data, story)} Preview. Fictional sample data for ${data.year}.`;
}
