import assert from 'node:assert/strict';
import { test } from 'node:test';

import { getRequestSourceVisual } from './jobTypeVisuals.js';

test('getRequestSourceVisual resolves synthetic source ids', () => {
  assert.equal(getRequestSourceVisual({ id: 'discover' })?.key, 'discover');
  assert.equal(getRequestSourceVisual({ id: 'trakt_recommendations' })?.key, 'trakt_recommendations');
  assert.equal(getRequestSourceVisual({ id: '0' })?.key, 'llm_recommendation');
});

test('getRequestSourceVisual ignores title-only matches', () => {
  assert.equal(getRequestSourceVisual({ title: 'Trakt Recommendations' }), null);
  assert.equal(getRequestSourceVisual({ title: 'LLM Recommendation' }), null);
  assert.equal(getRequestSourceVisual({ title: 'Discover' }), null);
});
