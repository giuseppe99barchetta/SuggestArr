const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const settingsRequestsPath = path.join(__dirname, 'SettingsRequests.vue');
const requestsPagePath = path.join(__dirname, '..', 'RequestsPage.vue');
const requestDetailsModalPath = path.join(__dirname, '..', 'common', 'RequestDetailsModal.vue');
const settingsRequestsSource = fs.readFileSync(settingsRequestsPath, 'utf8');
const requestsPageSource = fs.readFileSync(requestsPagePath, 'utf8');
const requestDetailsModalSource = fs.readFileSync(requestDetailsModalPath, 'utf8');

test('recent requests and requests page reuse RequestPosterCard', () => {
  assert.match(settingsRequestsSource, /<RequestPosterCard/);
  assert.match(settingsRequestsSource, /<RequestDetailsModal/);
  assert.match(settingsRequestsSource, /import RequestPosterCard from '@\/components\/common\/RequestPosterCard.vue';/);
  assert.match(settingsRequestsSource, /import RequestDetailsModal from '@\/components\/common\/RequestDetailsModal.vue';/);
  assert.match(settingsRequestsSource, /@select="openRequestModal"/);
  assert.match(settingsRequestsSource, /goToRequestsPage\(\) \{/);
  assert.doesNotMatch(settingsRequestsSource, /class="request-card request-card-compact"/);

  assert.match(requestsPageSource, /<RequestPosterCard/);
  assert.match(requestsPageSource, /<RequestDetailsModal/);
  assert.match(requestsPageSource, /import RequestPosterCard from '@\/components\/common\/RequestPosterCard.vue';/);
  assert.match(requestsPageSource, /import RequestDetailsModal from '@\/components\/common\/RequestDetailsModal.vue';/);
});

test('request details modal avoids generic dashboard modal classes', () => {
  assert.match(requestDetailsModalSource, /<Teleport to="body">/);
  assert.doesNotMatch(requestDetailsModalSource, /class="modal-overlay"/);
  assert.doesNotMatch(requestDetailsModalSource, /class="modal-content"/);
  assert.doesNotMatch(requestDetailsModalSource, /\.modal-overlay/);
  assert.doesNotMatch(requestDetailsModalSource, /\.modal-content/);
});
