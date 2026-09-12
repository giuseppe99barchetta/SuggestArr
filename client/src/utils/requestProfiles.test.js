import assert from 'node:assert/strict';
import { test } from 'node:test';

import { buildProfilePayload, hasServers, isChosen, mediaTypesOf, profileTypes } from './requestProfiles.js';

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
