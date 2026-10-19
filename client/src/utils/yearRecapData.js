/** Adapt actual aggregates without filling gaps with fictional viewing activity. */
import { posterUrl, PROJECT_URL } from './recapCanvas.js';
import { YEAR_RECAP_STORIES, yearRecapCaption as demoCaption, storyDescription as demoDescription, storyDetail as demoDetail } from './yearRecapDemo.js';

export function prepareYearRecap(data) {
  return { ...data, titles: data.titles.map(title => ({ ...title, artwork: posterUrl(title.poster_path) })) };
}

/** Stories without data to show are left out rather than rendered as empty placeholders. */
const hasContent = (data, story) => data.isDemo
  || (story.id === 'watched' ? Boolean(data.watched)
    : story.id === 'genres' ? Boolean(data.genres?.length)
      : story.id === 'titles' ? Boolean(data.titles?.length) : true);

export function yearStories(data) {
  return YEAR_RECAP_STORIES.filter(story => hasContent(data, story)).map(story => {
    if (story.id === 'intro') return { ...story, title: `Your ${data.year}, on screen` };
    if (!data.isDemo && story.id === 'time') return { ...story, title: 'A year of discoveries', kicker: 'RECORDED REQUEST ACTIVITY' };
    if (!data.isDemo && story.id === 'genres') return { ...story, kicker: 'GENRES OF YOUR REQUESTS' };
    if (!data.isDemo && story.id === 'titles') return { ...story, title: 'Your recent discoveries', kicker: 'TITLES REQUESTED THIS YEAR' };
    return story;
  });
}

export function yearCaption(data, story) {
  if (data.isDemo) return demoCaption(data, story);
  const viewing = data.watched ? ` ${data.watched.movies} movies · ${data.watched.episodes} episodes in partial ${data.providerLabel} watch data.` : '';
  return `${data.year} Year Recap${data.isYearToDate ? ' · Year to date' : ''}. ${data.requested.total} recorded titles requested with SuggestArr.${viewing} ${PROJECT_URL}`;
}

/** Story text without its title; coverage caveats live once in the dialog's "About these numbers". */
export function yearStoryDetail(data, story) {
  if (data.isDemo) return demoDetail(data, story);
  const descriptions = {
    intro: `${data.scope === 'server' ? 'Server' : 'Personal'} recorded progress${data.isYearToDate ? ' · Year to date' : ''}.`,
    discovery: `${data.requested.total} titles first recorded this year: ${data.requested.movies} movies and ${data.requested.series} TV series.`,
    watched: data.watched ? `${data.watched.movies} movies, ${data.watched.episodes} episodes and ${data.watched.series} TV series. ${data.watchNote}` : data.watchNote,
    time: `${data.requested.total} recorded title requests across twelve months. ${data.peakMonth.label}: ${data.peakMonth.requests} requests. Actual watch time is unavailable.`,
    genres: data.genres.length ? `${data.genres.map(genre => `${genre.label} ${genre.percent}%`).join(', ')}. Share of genre tags among ${data.genreCoverage} requested titles with available metadata.` : 'Genre metadata is not available for these recorded requests.',
    titles: data.titles.length ? `${data.titles.map(title => `${title.title}, ${title.detail}`).join('; ')}. Most recently requested titles with available metadata.` : 'No title metadata is available for this year yet.',
    summary: `${data.requested.total} recorded titles requested: ${data.requested.movies} movies and ${data.requested.series} TV series.${data.watched ? ` Partial ${data.providerLabel} activity: ${data.watched.movies} movies and ${data.watched.episodes} episodes.` : ''}`,
  };
  return descriptions[story.id];
}

export function yearDescription(data, story) {
  if (data.isDemo) return demoDescription(data, story);
  return `${story.title}. ${yearStoryDetail(data, story)}`;
}
