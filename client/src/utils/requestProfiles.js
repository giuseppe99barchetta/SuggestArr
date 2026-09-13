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

// Whether approving must ask first.  Only a server list that has LOADED and is
// empty lets approving stay a single click.  While it is still loading
// (null), or when a lookup failed, the dialog opens anyway: a silent approval
// would send the item with a profile nobody chose, and that cannot be taken
// back.
export function approvalNeedsDialog(servers) {
  if (!servers || servers.failed) return true;
  return hasServers(servers);
}

// What the dialog says when there is nothing (yet) to choose from.
export function approvalProfileNotice(servers) {
  if (!servers) return 'Loading quality profiles…';
  if (servers.failed) return 'Quality profiles could not be loaded. Sending now uses the profile the job or Jellyseerr would pick.';
  return '';
}

// The choice that follows from picking a server: is4k and the language profile
// are read off it rather than asked for (same as the job dialog), and a server
// with a single root folder has nothing to ask about the folder either.
export function choiceForServer(server, serverId = server?.id) {
  const folders = server?.rootFolders || [];
  return {
    serverId: serverId ?? '',
    profileId: '',
    rootFolder: folders.length === 1 ? folders[0].path : '',
    is4k: server?.is4k === true,
    languageProfileId: server?.activeLanguageProfileId ?? '',
  };
}

// With exactly one server for a media type there is nothing to decide, so it is
// filled in and only the quality profile is left to choose.  Two or more, and
// the person picks — a guess there could send a film to the wrong Radarr.
export function defaultChoice(serverList) {
  return (serverList || []).length === 1 ? choiceForServer(serverList[0]) : {};
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

// Radarr and Sonarr servers as Jellyseerr reports them.  Each list is loaded
// on its own: one failing lookup must not hide the other.  `failed` tells a
// lookup that went wrong apart from a server that is simply not configured.
export async function loadSeerServers(http) {
  const [radarr, sonarr] = await Promise.allSettled([http.get('/api/seer/radarr-servers'), http.get('/api/seer/sonarr-servers')]);
  const servers = result => (result.status === 'fulfilled' ? result.value?.data?.servers || [] : []);
  return {
    movie: servers(radarr),
    tv: servers(sonarr),
    failed: radarr.status === 'rejected' || sonarr.status === 'rejected',
  };
}
