import { getJobTypeLabel } from './jobTypeVisuals.js';

/**
 * Share of delivered titles that were watched afterwards.
 *
 * @param {{ requested: number, watched: number }|null} stats - A job's `stats` from /api/jobs.
 * @returns {number|null} Whole percent, or null when nothing was delivered or watching is not tracked.
 */
export function hitRate(stats) {
  if (!stats || !stats.requested) return null;
  return Math.round((stats.watched * 100) / stats.requested);
}

/**
 * Where a job's suggestions come from; recommendation jobs split by whether the LLM picks them.
 *
 * @param {object} job
 * @returns {string}
 */
export function jobSourceLabel(job) {
  if (job.job_type === 'recommendation' && job.filters?.use_llm) return 'LLM Recommendation';
  return getJobTypeLabel(job.job_type);
}

/**
 * Hit rate per suggestion source, summed over the jobs of that source.
 *
 * @param {object[]} jobs - Jobs from /api/jobs.
 * @returns {{ label: string, requested: number, watched: number, rate: number }[]} Sources with deliveries, best first.
 */
export function hitRatesBySource(jobs) {
  const totals = new Map();
  for (const job of jobs) {
    if (!job.stats?.requested) continue;
    const label = jobSourceLabel(job);
    const total = totals.get(label) || { label, requested: 0, watched: 0 };
    total.requested += job.stats.requested;
    total.watched += job.stats.watched;
    totals.set(label, total);
  }
  return [...totals.values()]
    .map((total) => ({ ...total, rate: hitRate(total) }))
    .sort((a, b) => b.rate - a.rate || b.requested - a.requested);
}
