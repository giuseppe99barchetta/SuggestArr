/**
 * Formatting helpers for the Simkl recent-items preview.
 *
 * Kept out of the component for the same reason as trackerState: the rules
 * turn on values the UI cannot show you (a missing watch date arrives as a
 * number, not as null), so they are easier to get right against tests.
 */

/**
 * Render a cached Simkl watch timestamp, or nothing when there isn't one.
 *
 * Simkl entries with no watch date are cached as epoch 0, which formats as a
 * perfectly valid 1 January 1970 rather than as the missing value it is.
 *
 * @param {number|string|null|undefined} ts Epoch seconds.
 * @returns {string} A locale date, or '' when there is no usable timestamp.
 */
export function formatWatchedDate(ts) {
  const seconds = Number(ts);
  if (!seconds || Number.isNaN(seconds)) return '';
  const date = new Date(seconds * 1000);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString();
}

/**
 * Preview loading state machine, spread into SimklMediaUsers' methods.
 *
 * Every load and reset bumps `previewGeneration`, so a response that lands
 * after the target changed (or after a reset) is dropped instead of showing
 * another user's items. The host provides `previewTargetUser`, `rowKey()` and
 * `fetchPreview(user)`.
 */
export const previewLoaderMethods = {
  resetPreview() {
    this.previewGeneration += 1;
    this.previewTargetKey = '';
    // The in-flight request's finally skips this once the generation moved on.
    this.previewLoading = false;
    this.clearPreviewItems();
  },
  clearPreviewItems() {
    this.previewItems = [];
    this.previewError = null;
    this.previewFetched = false;
  },
  async loadPreviewItems() {
    const user = this.previewTargetUser;
    if (!user) return;
    const generation = ++this.previewGeneration;
    const targetKey = this.rowKey(user);
    const isStale = () => generation !== this.previewGeneration || targetKey !== this.previewTargetKey;
    this.previewLoading = true;
    this.previewError = null;
    this.previewFetched = false;
    try {
      const res = await this.fetchPreview(user);
      if (isStale()) return;
      this.previewItems = res.data?.items || [];
      this.previewFetched = true;
    } catch (err) {
      if (isStale()) return;
      this.previewItems = [];
      this.previewFetched = true;
      if (err.response?.data?.code === 'client_id_failed') {
        this.clientIdError = true;
      } else {
        this.previewError = err.response?.data?.message || 'Failed to fetch recent Simkl items';
      }
    } finally {
      if (generation === this.previewGeneration) this.previewLoading = false;
    }
  },
};
