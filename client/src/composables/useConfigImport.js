import { ref } from 'vue';
import axios from 'axios';

export function useConfigImport(fetchConfig) {
  const isImporting = ref(false);
  const fileInput = ref(null);

  function importConfig() {
    fileInput.value.click();
  }

  async function handleFileImport(event) {
    const file = event.target.files[0];
    if (!file) return;

    isImporting.value = true;
    
    try {
      const text = await file.text();
      const configData = JSON.parse(text);

      await axios.post('/api/config/save', configData);
      await fetchConfig();

      return { success: true };
    } catch (error) {
      console.error('Error importing config:', error);
      return { success: false, error };
    } finally {
      isImporting.value = false;
      event.target.value = '';
    }
  }

  return {
    isImporting,
    fileInput,
    importConfig,
    handleFileImport,
  };
}
