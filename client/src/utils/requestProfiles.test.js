import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  approvalNeedsDialog, approvalProfileNotice, buildProfilePayload, choiceForServer, defaultChoice, hasServers, isChosen, loadSeerServers, mediaTypesOf, profileTypes,
} from './requestProfiles.js';

const servers = {
  movie: [{ id: 0, name: 'Radarr', is4k: false, profiles: [{ id: 7, name: 'HD' }], rootFolders: [{ path: '/movies' }] }],
  tv: [],
};

test('server id 0 counts as chosen — Jellyseerr numbers its first server 0', () => {
  assert.equal(isChosen(0), true);
  assert.equal(isChosen('0'), true);
  assert.equal(isChosen(''), false);
  assert.equal(isChosen(null), false);
  assert.equal(isChosen(undefined), false);
});

test('only media types that are being approved AND have a server are offered', () => {
  assert.deepEqual(profileTypes(['movie', 'tv'], servers), ['movie']);
  assert.deepEqual(profileTypes(['tv'], servers), []);
  assert.deepEqual(profileTypes([], servers), []);
});

test('mediaTypesOf collects each type once', () => {
  assert.deepEqual(mediaTypesOf([{ media_type: 'movie' }, { media_type: 'movie' }, { media_type: 'tv' }]), ['movie', 'tv']);
  assert.deepEqual(mediaTypesOf([null, undefined]), []);
});

test('hasServers is false only when neither Radarr nor Sonarr is configured', () => {
  assert.equal(hasServers(servers), true);
  assert.equal(hasServers({ movie: [], tv: [] }), false);
  assert.equal(hasServers(undefined), false);
});

test('a complete triple on server 0 is sent with numbers and is4k from the server', () => {
  const chosen = { movie: { serverId: 0, profileId: '7', rootFolder: '/movies', is4k: false, languageProfileId: '' }, tv: {} };
  assert.deepEqual(buildProfilePayload(['movie'], chosen), {
    movie: { serverId: 0, profileId: 7, rootFolder: '/movies', is4k: false },
  });
});

test('a partial or empty choice sends no profile at all', () => {
  assert.equal(buildProfilePayload(['movie'], { movie: {}, tv: {} }), null);
  assert.equal(buildProfilePayload(['movie'], { movie: { serverId: 0, profileId: '', rootFolder: '' } }), null);
  assert.equal(buildProfilePayload(['movie'], { movie: { serverId: 0, profileId: 7, rootFolder: '' } }), null);
});

test('a language profile is only sent when the server has one', () => {
  const chosen = { tv: { serverId: 1, profileId: 4, rootFolder: '/tv', is4k: true, languageProfileId: 2 } };
  assert.deepEqual(buildProfilePayload(['tv'], chosen), {
    tv: { serverId: 1, profileId: 4, rootFolder: '/tv', is4k: true, languageProfileId: 2 },
  });
});

test('approving asks first unless the server list has loaded and is empty', () => {
  assert.equal(approvalNeedsDialog(servers), true);
  assert.equal(approvalNeedsDialog({ movie: [], tv: [] }), false);
  // Still loading: a click right after opening the page must not approve silently.
  assert.equal(approvalNeedsDialog(null), true);
  assert.equal(approvalNeedsDialog(undefined), true);
  // A failed lookup is not "no servers".
  assert.equal(approvalNeedsDialog({ movie: [], tv: [], failed: true }), true);
});

test('the dialog says why there is nothing to choose', () => {
  assert.match(approvalProfileNotice(null), /Loading/);
  assert.match(approvalProfileNotice({ movie: [], tv: [], failed: true }), /could not be loaded/);
  assert.equal(approvalProfileNotice(servers), '');
});

test('one failing server lookup does not hide the other', async () => {
  const http = {
    get: async url => {
      if (url.includes('sonarr')) throw new Error('503');
      return { data: { servers: servers.movie } };
    },
  };
  assert.deepEqual(await loadSeerServers(http), { movie: servers.movie, tv: [], failed: true });
});

test('two answering lookups are not marked as failed', async () => {
  const http = { get: async url => ({ data: { servers: url.includes('radarr') ? servers.movie : [] } }) };
  assert.deepEqual(await loadSeerServers(http), { movie: servers.movie, tv: [], failed: false });
});

test('a single server with a single folder is filled in, only the profile stays open', () => {
  assert.deepEqual(defaultChoice(servers.movie), {
    serverId: 0, profileId: '', rootFolder: '/movies', is4k: false, languageProfileId: '',
  });
  // Server 0 counts as chosen, so the dialog shows the profile list right away.
  assert.equal(isChosen(defaultChoice(servers.movie).serverId), true);
});

test('with two servers nothing is guessed', () => {
  const zwei = [servers.movie[0], { ...servers.movie[0], id: 1, name: 'Radarr 4K', is4k: true }];
  assert.deepEqual(defaultChoice(zwei), {});
  assert.deepEqual(defaultChoice([]), {});
  assert.deepEqual(defaultChoice(undefined), {});
});

test('a server with two folders leaves the folder to choose', () => {
  const server = { ...servers.movie[0], rootFolders: [{ path: '/a' }, { path: '/b' }] };
  assert.equal(choiceForServer(server).rootFolder, '');
  assert.equal(choiceForServer(server).serverId, 0);
});

test('choosing only the profile is enough to send a complete profile', () => {
  const chosen = { movie: { ...defaultChoice(servers.movie), profileId: 7 }, tv: {} };
  assert.deepEqual(buildProfilePayload(['movie'], chosen), {
    movie: { serverId: 0, profileId: 7, rootFolder: '/movies', is4k: false },
  });
});
