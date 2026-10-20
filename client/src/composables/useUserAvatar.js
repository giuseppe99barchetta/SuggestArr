import axios from 'axios';
import { computed, onScopeDispose, reactive, shallowRef, watch } from 'vue';

// Sidebar, profile and account cards share one request and blob URL per user.
const entries = new Map();

function clearImage(entry) {
  if (entry.state.url) URL.revokeObjectURL(entry.state.url);
  entry.state.url = null;
  entry.state.source = null;
}

async function loadImage(entry) {
  entry.controller?.abort();
  const controller = new AbortController();
  entry.controller = controller;
  clearImage(entry);
  try {
    const response = await axios.get(`/api/users/${encodeURIComponent(entry.userId)}/avatar`, {
      responseType: 'blob', timeout: 20000, signal: controller.signal,
    });
    if (controller.signal.aborted || response.status !== 200 || !response.data?.type?.startsWith('image/')) return;
    entry.state.url = URL.createObjectURL(response.data);
    entry.state.source = response.headers['x-avatar-source'] || null;
  } catch {
    // The local cinema avatar stays visible while loading or on any failure.
  }
}

export function refreshUserAvatar(userId) {
  const entry = entries.get(String(userId));
  if (entry) return loadImage(entry);
}

export function useUserAvatar(user) {
  const currentEntry = shallowRef(null);
  let release = () => {};

  watch(() => user.value?.id, (id) => {
    release();
    currentEntry.value = null;
    if (id === undefined || id === null) return;
    const key = String(id);
    let entry = entries.get(key);
    if (!entry) {
      entry = { userId: key, state: reactive({ url: null, source: null }), users: 0, controller: null };
      entries.set(key, entry);
      loadImage(entry);
    }
    entry.users += 1;
    currentEntry.value = entry;
    release = () => {
      if (--entry.users === 0) {
        entry.controller?.abort();
        clearImage(entry);
        entries.delete(key);
      }
      release = () => {};
    };
  }, { immediate: true });

  onScopeDispose(() => release());
  return {
    avatarUrl: computed(() => currentEntry.value?.state.url || null),
    avatarSource: computed(() => currentEntry.value?.state.source || null),
    imageFailed: () => { if (currentEntry.value) clearImage(currentEntry.value); },
  };
}
