/** Shared icons, labels, and colors for automation job types and system request sources. */

export const JOB_TYPE_CONFIG = {
  discover: {
    icon: 'fas fa-search',
    label: 'Discover',
    color: 'var(--color-primary-light)',
    gradient: 'linear-gradient(135deg, var(--color-info-hover) 0%, var(--color-info) 50%, var(--color-primary-light) 100%)',
  },
  recommendation: {
    icon: 'fas fa-users',
    label: 'Recommendation',
    color: 'var(--color-warning-light)',
    gradient: 'linear-gradient(135deg, var(--color-primary-dark) 0%, var(--color-primary) 50%, var(--color-warning-light) 100%)',
  },
  trakt_recommendations: {
    icon: 'fab fa-trakt',
    label: 'Trakt Recommendations',
    color: 'var(--color-error-light)',
    gradient: 'linear-gradient(135deg, var(--color-error-hover) 0%, var(--color-error) 50%, var(--color-error-light) 100%)',
  },
  llm_recommendation: {
    icon: 'fas fa-robot',
    label: 'LLM Recommendation',
    color: 'var(--color-warning-light)',
    gradient: 'linear-gradient(135deg, var(--color-primary-dark) 0%, var(--color-primary) 50%, var(--color-warning-light) 100%)',
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
