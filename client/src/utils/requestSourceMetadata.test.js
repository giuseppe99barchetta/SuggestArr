import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  getRequestMethodMetadata,
  getRequestSourceContentMetadata,
} from './requestSourceMetadata.js';

test('getRequestMethodMetadata resolves real automation methods', () => {
  assert.deepEqual(getRequestMethodMetadata({ source_id: 'discover' }), {
    label: 'Discover',
    shortLabel: 'Discover',
    icon: 'fas fa-search',
  });
  assert.deepEqual(getRequestMethodMetadata({ source_id: 'trakt_recommendations' }), {
    label: 'Trakt Recommendations',
    shortLabel: 'Trakt',
    icon: 'icon-trakt',
  });
  assert.deepEqual(getRequestMethodMetadata({ source_id: 'ai_search' }), {
    label: 'AI Search',
    shortLabel: 'AI',
    icon: 'fas fa-magic',
  });
});

test('getRequestMethodMetadata does not call numeric source ids a request method', () => {
  assert.equal(getRequestMethodMetadata({ source_id: '27205' }), null);
  assert.equal(getRequestMethodMetadata({ id: 101 }), null);
});

test('getRequestSourceContentMetadata describes TMDb-backed source content', () => {
  assert.deepEqual(getRequestSourceContentMetadata({
    source_id: '27205',
    source_title: 'Breaking Bad',
  }), {
    label: 'Breaking Bad',
    kind: 'TMDB Source',
    icon: 'fas fa-database',
  });
});

test('getRequestSourceContentMetadata hides synthetic source content rows', () => {
  assert.equal(getRequestSourceContentMetadata({
    source_id: 'trakt_recommendations',
    source_title: 'Trakt Recommendations',
  }), null);
  assert.equal(getRequestSourceContentMetadata({
    source_id: 'discover',
    source_title: 'Discover',
  }), null);
  assert.equal(getRequestSourceContentMetadata({
    source_id: 'ai_search',
    source_title: 'AI Search',
  }), null);
});
