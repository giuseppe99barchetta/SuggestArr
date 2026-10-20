/** Adapt actual aggregates without filling gaps with fictional viewing activity. */
import { posterUrl, PROJECT_URL } from './recapCanvas.js';
import { YEAR_RECAP_STORIES, yearRecapCaption as demoCaption, storyDescription as demoDescription, storyDetail as demoDetail } from './yearRecapDemo.js';

export function prepareYearRecap(data) {
  return { ...data, titles: data.titles.map(title => ({ ...title, artwork: posterUrl(title.poster_path) })) };
}

/** Stories with too little data to be worth sharing are left out rather than shown nearly empty. */
const CONTENT = {
  watched: data => data.watched?.movies + data.watched?.episodes >= 3,
  // A single-digit share reads as a failure, not a celebration.
  hitrate: data => data.hitRate?.watched >= 3 && data.hitRate.percent >= 10,
  // One or two requests make a twelve-month chart look empty.
  time: data => data.watchMinutes != null || data.requested?.total >= 3,
  genres: data => data.genres?.length > 0 && data.genreCoverage >= 3,
  titles: data => Boolean(data.titles?.length),
  badges: data => Boolean(data.badgesUnlocked?.length),
};
const hasContent = (data, story) => data.isDemo || (CONTENT[story.id]?.(data) ?? true);

export function yearStories(data) {
  return YEAR_RECAP_STORIES.filter(story => hasContent(data, story)).map(story => {
    if (story.id === 'intro') return { ...story, title: `Your ${data.year}, on screen` };
    if (!data.isDemo && story.id === 'time') return { ...story, title: 'A year of discoveries', kicker: 'RECORDED REQUEST ACTIVITY' };
    if (!data.isDemo && story.id === 'genres') return { ...story, kicker: 'GENRES OF YOUR REQUESTS' };
    if (!data.isDemo && story.id === 'titles') return { ...story, title: 'Your standout discoveries', kicker: 'TOP-RATED TITLES REQUESTED THIS YEAR' };
    return story;
  });
}

export function yearCaption(data, story) {
  if (data.isDemo) return demoCaption(data, story);
  const viewing = data.watched ? ` ${data.watched.movies} movies · ${data.watched.episodes} episodes in partial ${data.providerLabel} watch data.` : '';
  const landed = data.hitRate?.watched ? ` ${data.hitRate.percent}% of them watched.` : '';
  return `${data.year} Year Recap${data.isYearToDate ? ' · Year to date' : ''}. ${data.requested.total} recorded titles requested with SuggestArr.${landed}${viewing} ${PROJECT_URL}`;
}

/** Story text without its title; coverage caveats live once in the dialog's "About these numbers". */
export function yearStoryDetail(data, story) {
  if (data.isDemo) return demoDetail(data, story);
  const descriptions = {
    intro: `${data.scope === 'server' ? 'Server' : 'Personal'} recorded progress${data.isYearToDate ? ' · Year to date' : ''}.`,
    discovery: `${data.requested.total} titles first recorded this year: ${data.requested.movies} movies and ${data.requested.series} TV series.`,
    watched: data.watched ? `${data.watched.movies} movies, ${data.watched.episodes} episodes and ${data.watched.series} TV series. ${data.watchNote}` : data.watchNote,
    hitrate: data.hitRate ? `${data.hitRate.percent}% of the titles requested this year were watched by their recipient: ${data.hitRate.watched} of ${data.hitRate.total}, ${data.hitRate.movies} movies and ${data.hitRate.series} TV series.` : '',
    time: `${data.requested.total} recorded title requests across twelve months. ${data.peakMonth.label}: ${data.peakMonth.requests} requests.${data.streak?.longest > 1 ? ` Longest watch streak: ${data.streak.longest} months in a row.` : ''} Actual watch time is unavailable.`,
    genres: data.genres.length ? `${data.genres.map(genre => `${genre.label} ${genre.percent}%`).join(', ')}. Share of genre tags among ${data.genreCoverage} requested titles with available metadata.` : 'Genre metadata is not available for these recorded requests.',
    titles: data.titles.length ? `${data.titles.map(title => `${title.title}, ${title.detail}`).join('; ')}. Highest-rated titles requested this year with available metadata.` : 'No title metadata is available for this year yet.',
    badges: (data.badgesUnlocked || []).map(badge => badge.label).join(', ') + (data.badgesUnlocked?.length ? ' unlocked this year.' : ''),
    summary: `${data.requested.total} recorded titles requested: ${data.requested.movies} movies and ${data.requested.series} TV series.${data.watched ? ` Partial ${data.providerLabel} activity: ${data.watched.movies} movies and ${data.watched.episodes} episodes.` : ''}`,
  };
  return descriptions[story.id];
}

export function yearDescription(data, story) {
  if (data.isDemo) return demoDescription(data, story);
  return `${story.title}. ${yearStoryDetail(data, story)}`;
}
