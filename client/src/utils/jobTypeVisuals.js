/** Shared icons, labels, and colors for automation job types and system request sources. */

export const JOB_TYPE_CONFIG = {
  list_import: {
    icon: 'fas fa-list',
    label: 'Import list',
    color: 'var(--color-notice)',
    gradient: 'linear-gradient(135deg, var(--color-brand), var(--color-notice))',
  },
  discover: {
    icon: 'fas fa-search',
    label: 'Discover',
    color: '#b3a9ff',
    gradient: 'linear-gradient(135deg, #4a95d8 0%, #5aa9f0 50%, #b3a9ff 100%)',
  },
  recommendation: {
    icon: 'fas fa-users',
    label: 'Recommendation',
    color: '#f6cd7d',
    gradient: 'linear-gradient(135deg, #4a3fb0 0%, #6a5ae0 50%, #f6cd7d 100%)',
  },
  trakt_recommendations: {
    icon: 'icon-trakt',
    label: 'Trakt Recommendations',
    color: '#f59a93',
    gradient: 'linear-gradient(135deg, #d95d55 0%, #f07067 50%, #f59a93 100%)',
  },
  llm_recommendation: {
    icon: 'fas fa-robot',
    label: 'LLM Recommendation',
    color: '#f6cd7d',
    gradient: 'linear-gradient(135deg, #4a3fb0 0%, #6a5ae0 50%, #f6cd7d 100%)',
  },
};

/**
 * @param {string} jobType
 * @returns {typeof JOB_TYPE_CONFIG.discover}
 */
export function getJobTypeConfig(jobType) {
  return JOB_TYPE_CONFIG[jobType] || JOB_TYPE_CONFIG.discover;
}

/**
 * @param {string} jobType
 * @returns {string}
 */
export function getJobTypeIcon(jobType) {
  return getJobTypeConfig(jobType).icon;
}

/**
 * @param {string} jobType
 * @returns {string}
 */
export function getJobTypeLabel(jobType) {
  const config = getJobTypeConfig(jobType);
  if (jobType === 'trakt_recommendations') {
    return 'Trakt';
  }
  return config.label;
}

/**
 * Visual config for grouped request sources that are not TMDb titles.
 *
 * @param {{ id?: string|number, title?: string }|null|undefined} source
 * @returns {(typeof JOB_TYPE_CONFIG.discover & { key: string })|null}
 */
export function getRequestSourceVisual(source) {
  if (!source) {
    return null;
  }

  const id = String(source.id ?? '');
  if (id === 'list_import') {
    return { ...JOB_TYPE_CONFIG.list_import, key: 'list_import' };
  }
  if (id === 'discover') {
    return { ...JOB_TYPE_CONFIG.discover, key: 'discover' };
  }
  if (id === 'trakt_recommendations') {
    return { ...JOB_TYPE_CONFIG.trakt_recommendations, key: 'trakt_recommendations' };
  }
  if (id === '0') {
    return { ...JOB_TYPE_CONFIG.llm_recommendation, key: 'llm_recommendation' };
  }

  return null;
}

/**
 * @param {{ id?: string|number, title?: string }|null|undefined} source
 * @returns {boolean}
 */
export function isSystemRequestSource(source) {
  return getRequestSourceVisual(source) !== null;
}

const SCHEDULE_PRESETS = {
  daily: 'Daily at midnight',
  weekly: 'Weekly on Monday',
  every_12h: 'Every 12 hours',
  every_6h: 'Every 6 hours',
  every_hour: 'Every hour',
};

/**
 * Human-readable schedule of a job.
 * @param {{ schedule_type?: string, schedule_value?: string }} job
 * @returns {string}
 */
export function formatJobSchedule(job) {
  if (job.schedule_type === 'preset') return SCHEDULE_PRESETS[job.schedule_value] || job.schedule_value;
  return `Cron: ${job.schedule_value}`;
}
