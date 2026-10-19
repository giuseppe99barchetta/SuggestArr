import axios from 'axios';

export async function getRecap(includePosters = false) {
  const { data } = await axios.get('/api/recap', { params: includePosters ? { include_posters: 'true' } : {} });
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
