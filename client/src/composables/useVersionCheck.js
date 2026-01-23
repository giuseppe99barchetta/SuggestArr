import { ref, onMounted } from 'vue';
import { useToast } from 'vue-toast-notification';
import axios from 'axios';

export function useVersionCheck() {
  const toast = useToast();
  const currentVersion = ref('Loading...');
  const latestVersion = ref(null);
  const updateAvailable = ref(false);
  const isChecking = ref(false);

  const getCurrentVersion = async () => {
    try {
      const response = await axios.get('/api/config/version');
      if (response.data.status === 'success') {
        currentVersion.value = response.data.version;
      }
    } catch (error) {
      console.error('Error getting current version:', error);
      currentVersion.value = 'v2.0.0'; // Fallback version
    }
  };

  const checkForUpdates = async () => {
    if (isChecking.value) return;
    
    isChecking.value = true;
    
    try {
      // Get current version if not already loaded
      if (currentVersion.value === 'Loading...') {
        await getCurrentVersion();
      }
      
      const response = await axios.get('https://api.github.com/repos/giuseppe99barchetta/SuggestArr/releases/latest');
      const release = response.data;
      
      latestVersion.value = release.tag_name;
      
      // Simple version comparison (remove 'v' prefix and compare)
      const current = currentVersion.value.replace('v', '');
      const latest = latestVersion.value.replace('v', '');
      
      if (current !== latest) {
        updateAvailable.value = true;
        showUpdateNotification();
      } else {
        updateAvailable.value = false;
      }
    } catch (error) {
      console.error('Error checking for updates:', error);
    } finally {
      isChecking.value = false;
    }
  };

  const showUpdateNotification = () => {
    toast.info(`New version available: ${latestVersion.value}`, {
      duration: 8000,
      onClick: () => {
        window.open('https://github.com/giuseppe99barchetta/SuggestArr/releases/latest', '_blank');
      }
    });
  };

  onMounted(() => {
    // Get current version first
    getCurrentVersion();
    
    // Check for updates shortly after
    setTimeout(() => {
      checkForUpdates();
    }, 1000);
    
    // Check for updates every hour
    const interval = setInterval(checkForUpdates, 60 * 60 * 1000);
    
    return () => clearInterval(interval);
  });

  return {
    currentVersion,
    latestVersion,
    updateAvailable,
    isChecking,
    checkForUpdates
  };
}