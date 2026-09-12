// Choosing a request profile (server, quality profile, root folder) while
// approving a suggestion. Shared by every place that can approve — the
// Requests page and the dashboard — so the rules live once.

const MEDIA_TYPES = ['movie', 'tv'];

// Jellyseerr numbers its first server 0, so "not chosen" must mean empty or
// missing — never merely falsy.
export function isChosen(value) {
  return value !== '' && value !== null && value !== undefined;
}

export function hasServers(servers) {
  return Boolean(servers) && ((servers.movie || []).length > 0 || (servers.tv || []).length > 0);
}

export function mediaTypesOf(items) {
  return [...new Set((items || []).map(item => item?.media_type).filter(Boolean))];
}

// Only the media types actually being approved, and only when Jellyseerr has a
// server for them.
export function profileTypes(mediaTypes, servers) {
  return MEDIA_TYPES.filter(type => (mediaTypes || []).includes(type) && ((servers || {})[type] || []).length > 0);
}

// Only complete triples are sent: serverId, profileId and rootFolder mean
// nothing apart, and the API refuses a partial one with 400. is4k and the
// language profile were read off the server when it was chosen.
export function buildProfilePayload(types, chosen) {
  const profile = {};
  for (const type of types || []) {
    const wahl = (chosen || {})[type] || {};
    if (!isChosen(wahl.serverId) || !isChosen(wahl.profileId) || !wahl.rootFolder) continue;
    profile[type] = {
      serverId: Number(wahl.serverId),
      profileId: Number(wahl.profileId),
      rootFolder: wahl.rootFolder,
      is4k: wahl.is4k === true,
    };
    if (isChosen(wahl.languageProfileId)) profile[type].languageProfileId = Number(wahl.languageProfileId);
  }
  return Object.keys(profile).length ? profile : null;
}

// Radarr and Sonarr servers as Jellyseerr reports them. Without servers there
// is nothing to choose, and approving stays a single click.
export async function loadSeerServers(http) {
  try {
    const [radarr, sonarr] = await Promise.all([http.get('/api/seer/radarr-servers'), http.get('/api/seer/sonarr-servers')]);
    return { movie: radarr.data.servers || [], tv: sonarr.data.servers || [] };
  } catch {
    return { movie: [], tv: [] };
  }
}
