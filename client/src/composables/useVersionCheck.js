import { ref, onMounted } from 'vue';
import { useToast } from 'vue-toast-notification';
import axios from 'axios';

export function useVersionCheck() {
  const toast = useToast();
  const currentVersion = ref('Loading...');
  const latestVersion = ref(null);
  const updateAvailable = ref(false);
  const isChecking = ref(false);

  // Cache e debounce per evitare chiamate multiple
  const versionCache = ref(null);
  let lastCheckTime = 0;
  const CHECK_COOLDOWN = 5 * 60 * 1000; // 5 minuti

  const getCurrentVersion = async (useCache = true) => {
    if (useCache && versionCache.value && (Date.now() - lastCheckTime < CHECK_COOLDOWN)) {
      currentVersion.value = versionCache.value.version;
      return;
    }

    try {
      const response = await axios.get('/api/config/version', {
        timeout: 5000 // 5 second timeout
      });
      if (response.data.status === 'success') {
        currentVersion.value = response.data.version;
        versionCache.value = {
          version: response.data.version,
          timestamp: Date.now()
        };
        lastCheckTime = Date.now();
      }
    } catch (error) {
      console.error('Error getting current version:', error);
      currentVersion.value = 'v2.0.0'; // Fallback version
    }
  };

  const checkForUpdates = async (force = false) => {
    if (isChecking.value) return;
    
    // Skip if not enough time passed (unless forced)
    if (!force && (Date.now() - lastCheckTime < CHECK_COOLDOWN)) {
      return;
    }
    
    isChecking.value = true;
    
    try {
      // Get current version if not already loaded
      if (currentVersion.value === 'Loading...' || !currentVersion.value) {
        await getCurrentVersion(false); // Skip cache for first load
      }
      
      const response = await axios.get('https://api.github.com/repos/giuseppe99barchetta/SuggestArr/releases/latest', {
        timeout: 8000 // 8 second timeout
      });
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
      
      lastCheckTime = Date.now();
    } catch (error) {
      console.error('Error checking for updates:', error);
      // Non bloccante - l'errore non ferma l'applicazione
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
    // Get current version first (non-blocking)
    getCurrentVersion();
    
    // Check for updates shortly after (non-blocking)
    setTimeout(() => {
      checkForUpdates();
    }, 2000); // Aumentato a 2 secondi per dare priorità al caricamento principale
    
    // Check for updates every hour
    const interval = setInterval(() => checkForUpdates(false), 60 * 60 * 1000);
    
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