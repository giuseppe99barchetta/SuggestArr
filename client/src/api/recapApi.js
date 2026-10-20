import axios from 'axios';

export async function getYearRecap(year, scope = 'personal', includePlayback = false, signal) {
  const { data } = await axios.get('/api/recap/year', {
    params: { year, scope, include_playback: String(includePlayback) }, signal, timeout: 35000,
  });
  return data.data;
}

export async function getRecap(includePosters = false) {
  const { data } = await axios.get('/api/recap', { params: includePosters ? { include_posters: 'true' } : {} });
  const recap = data.data;
  if (!Number.isFinite(recap?.total) || !Number.isFinite(recap.movies) || !Number.isFinite(recap.tv)
      || !Array.isArray(recap.badges) || !recap.preferences) {
    throw new Error('Incomplete recap response');
  }
  return recap;
}

/** Link recorded requests to plays on the media server; the server throttles repeated scans. */
export async function syncWatchActivity() {
  const { data } = await axios.post('/api/recap/watch-sync', null, { timeout: 50000 });
  return data.data;
}

export async function claimRecapPrompt() {
  const { data } = await axios.post('/api/recap/prompt');
  return data.data.prompt;
}

export async function saveRecapPreference(action) {
  const { data } = await axios.patch('/api/recap/preferences', { action });
  return data.data;
}
