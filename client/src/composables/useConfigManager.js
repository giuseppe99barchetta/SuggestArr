import { ref } from 'vue';
import axios from 'axios';

export function useConfigManager() {
  const config = ref(getInitialConfig());
  const hasExistingConfig = ref(false);

  function getInitialConfig() {
    return {
      TMDB_API_KEY: '',
      JELLYFIN_API_URL: '',
      JELLYFIN_TOKEN: '',
      JELLYFIN_LIBRARIES: [],
      PLEX_API_URL: '',
      PLEX_TOKEN: '',
      PLEX_LIBRARIES: [],
      SEER_API_URL: '',
      SEER_TOKEN: '',
      SEER_USER_NAME: '',
      SEER_USER_PSW: '',
      SEER_SESSION_TOKEN: '',
      SELECTED_SERVICE: '',
      MAX_SIMILAR_MOVIE: 5,
      MAX_SIMILAR_TV: 2,
      MAX_CONTENT_CHECKS: 10,
      SEARCH_SIZE: 20,
      CRON_TIMES: '0 0 * * *',
      SUBPATH: '',
      DB_TYPE: 'sqlite',
      EXCLUDE_DOWNLOADED: true,
      EXCLUDE_REQUESTED: true,
    };
  }

  async function fetchConfig() {
    try {
      const { data } = await axios.get('/api/config/fetch');
      if (data) {
        config.value = { ...getInitialConfig(), ...data };
        hasExistingConfig.value = !!(data.TMDB_API_KEY && data.SELECTED_SERVICE);
      }
    } catch (error) {
      console.error('Error fetching configuration:', error);
    }
  }

  async function saveConfig(setupMode, quickDefaults) {
    try {
      let configToSave = { ...config.value };
      
      // Applica i defaults per quick setup
      if (setupMode === 'quick') {
        configToSave = { ...quickDefaults, ...configToSave };
      }

      console.log('Saving config:', configToSave); // Debug

      await axios.post('/api/config/save', configToSave);
      await axios.post('/api/config/complete-setup');
      return { success: true };
    } catch (error) {
      console.error('Error saving configuration:', error);
      return { success: false, error };
    }
  }

  function updateConfig(key, value) {
    config.value[key] = value;
  }

  return {
    config,
    hasExistingConfig,
    fetchConfig,
    saveConfig,
    updateConfig,
    getInitialConfig,
  };
}
