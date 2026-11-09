import test from 'node:test';
import assert from 'node:assert/strict';
import { discordEndpointUrl } from './discordEndpoint.js';

test('root deployments get the plain API path', () => {
  assert.equal(discordEndpointUrl('https://example.com', '/'), 'https://example.com/api/discord/interactions');
  assert.equal(discordEndpointUrl('https://example.com', ''), 'https://example.com/api/discord/interactions');
  assert.equal(discordEndpointUrl('https://example.com', undefined), 'https://example.com/api/discord/interactions');
});

test('a sub-path is kept, with or without trailing slashes', () => {
  assert.equal(discordEndpointUrl('https://example.com', '/suggestarr'), 'https://example.com/suggestarr/api/discord/interactions');
  assert.equal(discordEndpointUrl('https://example.com', '/suggestarr/'), 'https://example.com/suggestarr/api/discord/interactions');
  assert.equal(discordEndpointUrl('https://example.com', '/a/b'), 'https://example.com/a/b/api/discord/interactions');
});

test('an absolute development base is used as given', () => {
  assert.equal(discordEndpointUrl('http://localhost:8080', 'http://localhost:5000/x'), 'http://localhost:5000/x/api/discord/interactions');
});
