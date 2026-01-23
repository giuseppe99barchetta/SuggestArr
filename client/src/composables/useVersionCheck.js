import { ref, onMounted } from 'vue';
import { useToast } from 'vue-toast-notification';
import axios from 'axios';

export function useVersionCheck() {
  const toast = useToast();
  const currentVersion = ref('Loading...');
  const latestVersion = ref(null);
  const updateAvailable = ref(false);
  const isChecking = ref(false);
  const currentImageTag = ref('latest'); // Will detect if we're on nightly or stable

  // Cache and debounce to avoid multiple calls
  const versionCache = ref(null);
  let lastCheckTime = 0;
  const CHECK_COOLDOWN = 5 * 60 * 1000; // 5 minutes

  const getCurrentVersion = async (useCache = true) => {
    if (useCache && versionCache.value && (Date.now() - lastCheckTime < CHECK_COOLDOWN)) {
      currentVersion.value = versionCache.value.version;
      currentImageTag.value = versionCache.value.imageTag || 'latest';
      return;
    }

    try {
      // Get both version and Docker info in parallel
      const [versionResponse, dockerResponse] = await Promise.all([
        axios.get('/api/config/version', { timeout: 5000 }),
        axios.get('/api/config/docker-info', { timeout: 5000 })
      ]);

      if (versionResponse.data.status === 'success') {
        currentVersion.value = versionResponse.data.version;
      }

      // Get the actual Docker tag from container metadata
      if (dockerResponse.data.status === 'success') {
        currentImageTag.value = dockerResponse.data.tag || 'latest';
        console.log(`Docker tag detected: ${currentImageTag.value} (source: ${dockerResponse.data.source})`);
      } else {
        // Fallback: detect from version string
        const version = versionResponse.data.version?.toLowerCase() || '';
        if (version.includes('nightly') || version.includes('dev')) {
          currentImageTag.value = 'nightly';
        } else {
          currentImageTag.value = 'latest';
        }
      }
      
      versionCache.value = {
        version: currentVersion.value,
        imageTag: currentImageTag.value,
        timestamp: Date.now()
      };
      lastCheckTime = Date.now();
      
    } catch (error) {
      console.error('Error getting current version:', error);
      currentVersion.value = 'v2.0.0'; // Fallback version
      currentImageTag.value = 'latest';
    }
  };

  const getDockerDigest = async (tag) => {
    try {
      // Use backend proxy to avoid CORS issues
      const response = await axios.get(`/api/config/docker-digest/${tag}`, {
        timeout: 8000
      });
      
      if (response.data.status === 'success') {
        return response.data.digest;
      } else {
        console.error(`Backend error for ${tag}:`, response.data.message);
        return null;
      }
    } catch (error) {
      console.error(`Error fetching Docker digest for ${tag}:`, error);
      return null;
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
      
      // Determine which tags to check based on current image
      const tagsToCheck = [];
      if (currentImageTag.value === 'nightly') {
        tagsToCheck.push('nightly');
      } else {
        tagsToCheck.push('latest');
      }
      
      let updateFound = false;
      
      for (const tag of tagsToCheck) {
        const currentDigest = await getDockerDigest(tag);
        
        if (currentDigest && versionCache.value?.digests?.[tag] !== currentDigest) {
          // New digest found - update available
          updateFound = true;
          
          // Update cache with new digest
          if (!versionCache.value) versionCache.value = {};
          if (!versionCache.value.digests) versionCache.value.digests = {};
          versionCache.value.digests[tag] = currentDigest;
          
          latestVersion.value = `${tag} (${currentDigest.substring(0, 12)})`;
          break;
        }
      }
      
      if (updateFound) {
        updateAvailable.value = true;
        showUpdateNotification();
      } else {
        updateAvailable.value = false;
      }
      
      lastCheckTime = Date.now();
    } catch (error) {
      console.error('Error checking for updates:', error);
      // Non-blocking - the error doesn't stop the application
    } finally {
      isChecking.value = false;
    }
  };

  const showUpdateNotification = () => {
    const updateType = currentImageTag.value === 'nightly' ? 'nightly' : 'stable';
    const message = currentImageTag.value === 'nightly' 
      ? `New ${updateType} build available: ${latestVersion.value}`
      : `New version available: ${latestVersion.value}`;
    toast.info(message, {
      duration: 8000,
      position: 'top-right',
      onClick: () => {
        if (currentImageTag.value === 'nightly') {
          window.open('https://hub.docker.com/r/ciuse99/suggestarr/tags', '_blank');
        } else {
          window.open('https://github.com/giuseppe99barchetta/SuggestArr/releases/latest', '_blank');
        }
      }
    });
  };

  onMounted(() => {
    getCurrentVersion();
    
    setTimeout(() => {
      checkForUpdates(false);
    }, 5000);
    
    const interval = setInterval(() => checkForUpdates(false), 60 * 60 * 1000);
    
    return () => clearInterval(interval);
  });

  return {
    currentVersion,
    latestVersion,
    updateAvailable,
    isChecking,
    currentImageTag,
    checkForUpdates
  };
}