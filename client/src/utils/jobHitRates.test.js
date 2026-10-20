import assert from 'node:assert/strict';
import { test } from 'node:test';
import { hitRate, hitRatesBySource, jobSourceLabel } from './jobHitRates.js';

test('hit rate is a whole percent, and unknown without deliveries or tracking', () => {
  assert.equal(hitRate({ requested: 3, watched: 1 }), 33);
  assert.equal(hitRate({ requested: 0, watched: 0 }), null);
  assert.equal(hitRate(null), null);
});

test('recommendation jobs are split by whether the LLM picks them', () => {
  assert.equal(jobSourceLabel({ job_type: 'recommendation', filters: { use_llm: true } }), 'LLM Recommendation');
  assert.equal(jobSourceLabel({ job_type: 'recommendation', filters: {} }), 'Recommendation');
});

test('sources sum their jobs, skip those without deliveries and come best first', () => {
  const jobs = [
    { job_type: 'discover', stats: { requested: 10, watched: 1 } },
    { job_type: 'discover', stats: { requested: 10, watched: 3 } },
    { job_type: 'recommendation', filters: { use_llm: true }, stats: { requested: 4, watched: 2 } },
    { job_type: 'list_import', stats: { requested: 0, watched: 0 } },
    { job_type: 'recommendation', stats: null },
  ];
  assert.deepEqual(hitRatesBySource(jobs), [
    { label: 'LLM Recommendation', requested: 4, watched: 2, rate: 50 },
    { label: 'Discover', requested: 20, watched: 4, rate: 20 },
  ]);
});
