import axios from 'axios';

/**
 * API client for discover jobs management.
 */
export const jobsApi = {
  /**
   * Get all discover jobs.
   * @returns {Promise<Object>} Response with jobs array.
   */
  async getJobs() {
    const response = await axios.get('/api/jobs');
    return response.data;
  },

  /**
   * Get a single job by ID.
   * @param {number} jobId - Job ID.
   * @returns {Promise<Object>} Response with job object.
   */
  async getJob(jobId) {
    const response = await axios.get(`/api/jobs/${jobId}`);
    return response.data;
  },

  /**
   * Create a new discover job.
   * @param {Object} jobData - Job configuration.
   * @returns {Promise<Object>} Response with created job ID.
   */
  async createJob(jobData) {
    const response = await axios.post('/api/jobs', jobData);
    return response.data;
  },

  /**
   * Update an existing job.
   * @param {number} jobId - Job ID.
   * @param {Object} jobData - Updated job configuration.
   * @returns {Promise<Object>} Response with status.
   */
  async updateJob(jobId, jobData) {
    const response = await axios.put(`/api/jobs/${jobId}`, jobData);
    return response.data;
  },

  /**
   * Delete a job.
   * @param {number} jobId - Job ID.
   * @returns {Promise<Object>} Response with status.
   */
  async deleteJob(jobId) {
    const response = await axios.delete(`/api/jobs/${jobId}`);
    return response.data;
  },

  /**
   * Toggle job enabled status.
   * @param {number} jobId - Job ID.
   * @returns {Promise<Object>} Response with new enabled status.
   */
  async toggleJob(jobId) {
    const response = await axios.post(`/api/jobs/${jobId}/toggle`);
    return response.data;
  },

  /**
   * Run a job immediately.
   * @param {number} jobId - Job ID.
   * @returns {Promise<Object>} Response with execution result.
   */
  async runJobNow(jobId) {
    const response = await axios.post(`/api/jobs/${jobId}/run`);
    return response.data;
  },

  /**
   * Get execution history for a job.
   * @param {number} jobId - Job ID.
   * @param {number} limit - Maximum records to return.
   * @returns {Promise<Object>} Response with history array.
   */
  async getJobHistory(jobId, limit = 50) {
    const response = await axios.get(`/api/jobs/${jobId}/history`, {
      params: { limit }
    });
    return response.data;
  },

  /**
   * Get recent execution history across all jobs.
   * @param {number} limit - Maximum records to return.
   * @returns {Promise<Object>} Response with history array.
   */
  async getAllHistory(limit = 100) {
    const response = await axios.get('/api/jobs/history', {
      params: { limit }
    });
    return response.data;
  },

  /**
   * Get available genres for a media type.
   * @param {string} mediaType - 'movie' or 'tv'.
   * @returns {Promise<Object>} Response with genres array.
   */
  async getGenres(mediaType) {
    const response = await axios.get(`/api/jobs/genres/${mediaType}`);
    return response.data;
  },

  /**
   * Get available languages.
   * @returns {Promise<Object>} Response with languages array.
   */
  async getLanguages() {
    const response = await axios.get('/api/jobs/languages');
    return response.data;
  },

  /**
   * Sync system job from YAML configuration.
   * @returns {Promise<Object>} Response with sync status.
   */
  async syncSystemJob() {
    const response = await axios.post('/api/jobs/sync-config');
    return response.data;
  },

  /**
   * Get available watch provider regions from TMDb.
   * @returns {Promise<Object>} Response with regions array.
   */
  async getWatchRegions() {
    const response = await axios.get('/api/jobs/watch-regions');
    return response.data;
  },

  /**
   * Get available streaming providers for a region from TMDb.
   * @param {string} region - ISO 3166-1 region code (e.g. 'IT').
   * @returns {Promise<Object>} Response with providers array.
   */
  async getWatchProviders(region) {
    const response = await axios.get('/api/jobs/watch-providers', { params: { region } });
    return response.data;
  },

  /**
   * Get default filter values for new jobs (derived from global config).
   * @returns {Promise<Object>} Response with defaults object.
   */
  async getDefaultFilters() {
    const response = await axios.get('/api/jobs/defaults');
    return response.data;
  },

  /**
   * Check if LLM is configured for AI-enhanced recommendations.
   * @returns {Promise<Object>} Response with configured boolean.
   */
  async getLlmStatus() {
    const response = await axios.get('/api/jobs/llm-status');
    return response.data;
  },

  /**
   * Get the current Seer delivery queue status.
   * @returns {Promise<Object>} Response with queued/submitting/submitted/failed counts.
   */
  async getQueueStatus() {
    const response = await axios.get('/api/jobs/queue-status');
    return response.data;
  },

  /**
   * Simulate job execution without making actual requests.
   * Returns the list of media items that would have been queued.
   * @param {number} jobId - Job ID.
   * @returns {Promise<Object>} Response with items_count and items array.
   */
  async dryRunJob(jobId) {
    const response = await axios.post(`/api/jobs/${jobId}/dry-run`);
    return response.data;
  }
};

export default jobsApi;
