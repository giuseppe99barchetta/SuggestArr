import { ref, onMounted } from 'vue';
import { useToast } from 'vue-toast-notification';
import axios from 'axios';

export function useVersionCheck() {
  const toast = useToast();
  const currentVersion = ref(`${process.env.VUE_APP_VERSION || __APP_VERSION__ || 'unknown'}`);
  const latestVersion = ref(null);
  const updateAvailable = ref(false);
  const isChecking = ref(false);
  const currentImageTag = ref('unknown'); // nightly, latest
  const currentBuildDate = ref(null);

  const versionCache = ref(null);
  let lastCheckTime = 0;
  const CHECK_COOLDOWN = 5 * 60 * 1000; // 5 min
  const CHECK_INTERVAL = 60 * 60 * 1000; // 1h

  const getCurrentVersion = async (useCache = true) => {
    if (useCache && versionCache.value && (Date.now() - lastCheckTime < CHECK_COOLDOWN)) {
      currentVersion.value = versionCache.value.version;
      currentImageTag.value = versionCache.value.imageTag || 'latest';
      currentBuildDate.value = versionCache.value.buildDate;
      return;
    }

    try {
      const [dockerResponse] = await Promise.all([
        axios.get('/api/config/docker-info', { timeout: 5000 })
      ]);

      if (dockerResponse.data.status === 'success') {
        currentImageTag.value = dockerResponse.data.tag || 'latest';
        currentBuildDate.value = dockerResponse.data.build_date;
      } else {
        const version = currentVersion.value?.toLowerCase() || '';
        currentImageTag.value = version.includes('nightly') || version.includes('dev') ? 'nightly' : 'latest';
      }

      versionCache.value = {
        version: currentVersion.value,
        imageTag: currentImageTag.value,
        buildDate: currentBuildDate.value,
        timestamp: Date.now()
      };
      lastCheckTime = Date.now();

    } catch (error) {
      console.error('getCurrentVersion error:', error);
      currentVersion.value = 'v2.0.0';
      currentImageTag.value = 'latest';
    }
  };

  const getLatestVersion = async () => {
    try {
      const response = await axios.get(
        'https://api.github.com/repos/giuseppe99barchetta/SuggestArr/releases/latest',
        { timeout: 8000 }
      );
      return response.data.tag_name;
    } catch (error) {
      console.error('GitHub latest version error:', error);
      return null;
    }
  };

  const checkForUpdates = async (force = false) => {
    if (isChecking.value) return;

    const now = Date.now();
    if (!force && now - lastCheckTime < CHECK_COOLDOWN) return;

    isChecking.value = true;

    try {
      if (currentVersion.value === 'Loading...' || !currentVersion.value) {
        await getCurrentVersion(false);
      }

      const latest = await getLatestVersion();
      if (!latest) return;

      latestVersion.value = latest;
      const cleanLatest = latest.replace(/^v/, '');
      const cleanCurrent = currentVersion.value.replace(/^v/, '');

      const isUpdateAvailable = cleanLatest > cleanCurrent;
      updateAvailable.value = isUpdateAvailable;

      if (isUpdateAvailable) {
        showUpdateNotification();
      }

      lastCheckTime = now;
    } catch (error) {
      console.error('checkForUpdates error:', error);
    } finally {
      isChecking.value = false;
    }
  };

  const showUpdateNotification = () => {
    const isNightly = currentImageTag.value === 'nightly';
    const type = isNightly ? 'nightly' : 'stable';
    const message = `New ${type} available!\nCurrent: ${currentVersion.value} (${currentImageTag.value})\nNew: ${latestVersion.value}`;

    toast.info(message, {
      duration: 10000,
      position: 'top-right',
      onClick: () => {
        if (isNightly) {
          window.open('https://hub.docker.com/r/ciuse99/suggestarr/tags', '_blank');
        } else {
          window.open('https://github.com/giuseppe99barchetta/SuggestArr/releases/latest', '_blank');
        }
      }
    });
  };

  onMounted(() => {
    getCurrentVersion();

    setTimeout(() => checkForUpdates(false), 5000);

    const interval = setInterval(() => checkForUpdates(false), CHECK_INTERVAL);

    return () => clearInterval(interval);
  });

  return {
    currentVersion,
    latestVersion,
    updateAvailable,
    isChecking,
    currentImageTag,
    currentBuildDate,
    checkForUpdates
  };
}
