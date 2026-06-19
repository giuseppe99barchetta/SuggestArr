const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const settingsRequestsPath = path.join(__dirname, 'SettingsRequests.vue');
const requestsPagePath = path.join(__dirname, '..', 'RequestsPage.vue');
const requestDetailsModalPath = path.join(__dirname, '..', 'common', 'RequestDetailsModal.vue');
const requestPosterCardPath = path.join(__dirname, '..', 'common', 'RequestPosterCard.vue');
const settingsRequestsSource = fs.readFileSync(settingsRequestsPath, 'utf8');
const requestsPageSource = fs.readFileSync(requestsPagePath, 'utf8');
const requestDetailsModalSource = fs.readFileSync(requestDetailsModalPath, 'utf8');
const requestPosterCardSource = fs.readFileSync(requestPosterCardPath, 'utf8');

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

test('request details modal uses poster overlays for request metadata', () => {
  assert.match(requestDetailsModalSource, /class="request-details-modal__poster-frame"/);
  assert.match(requestDetailsModalSource, /class="request-details-modal__poster-overlay request-details-modal__poster-overlay--top"/);
  assert.match(requestDetailsModalSource, /class="request-details-modal__poster-pill request-details-modal__poster-pill--media"/);
  assert.match(requestDetailsModalSource, /class="request-details-modal__poster-pill request-details-modal__poster-pill--rating"/);
  assert.match(requestDetailsModalSource, /class="request-details-modal__poster-overlay request-details-modal__poster-overlay--bottom"/);
  assert.match(requestDetailsModalSource, /class="request-details-modal__poster-date"/);
  assert.match(requestDetailsModalSource, /class="request-details-modal__poster-origin"/);
  assert.match(requestDetailsModalSource, /Source content <strong>{{ selectedSource\.source_title }}<\/strong>/);
  assert.match(requestDetailsModalSource, /Origin <strong>Trakt History<\/strong>/);
  assert.match(requestDetailsModalSource, /class="request-details-modal__context"/);
  assert.doesNotMatch(requestDetailsModalSource, /class="request-details-modal__badges"/);
  assert.doesNotMatch(requestDetailsModalSource, /class="request-details-modal__badge/);
});

test('request poster card keeps metadata on the poster artwork', () => {
  assert.match(requestPosterCardSource, /class="poster-overlay poster-overlay--top"/);
  assert.match(requestPosterCardSource, /class="poster-pill poster-pill--media"/);
  assert.match(requestPosterCardSource, /class="poster-pill poster-pill--rating"/);
  assert.match(requestPosterCardSource, /class="poster-overlay poster-overlay--bottom"/);
  assert.match(requestPosterCardSource, /class="poster-date"/);
  assert.match(requestPosterCardSource, /class="poster-origin"/);
  assert.match(requestPosterCardSource, /source_origin === 'trakt_history'/);
  assert.match(requestPosterCardSource, /From: <strong>{{ item\.source_title }}<\/strong>/);
  assert.doesNotMatch(requestPosterCardSource, /class="badge-container"/);
  assert.doesNotMatch(requestPosterCardSource, /class="badge badge-media"/);
});
