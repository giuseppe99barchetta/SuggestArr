/**
 * Options-API mixin encapsulating the shared Trakt device-code polling logic
 * used by TraktMediaUsers.
 *
 * It owns the device-code/user-code/verification-url state, the poll timer and
 * deadline, and the poll loop itself (deadline expiry -> stop; connected -> stop
 * + success; any thrown error -> stop with message fallback). Pending responses
 * (HTTP 202 with connected:false) simply do not satisfy the connected check, so
 * polling continues until the deadline.
 *
 * Components parameterize the differences (which API functions to call, where to
 * surface errors, what to do on success) via the options object passed to
 * `startTraktPolling`.
 */
export default {
  data() {
    return {
      isPollingTrakt: false,
      traktDeviceCode: null,
      traktUserCode: '',
      traktVerificationUrl: '',
      traktPollTimer: null,
      traktPollDeadline: null,
      // Per-poll-session configuration captured at start time.
      traktPollConfig: null,
    };
  },

  beforeUnmount() {
    this.stopTraktPolling();
  },

  methods: {
    /**
     * Begin a Trakt device-code authorization flow.
     *
     * @param {Object} options
     * @param {Function} options.requestCode - async () => axios response with
     *   { device_code, user_code, verification_url, interval, expires_in }.
     * @param {Function} options.pollToken - async (deviceCode) => axios response
     *   with { connected, ... } (HTTP 202 while pending).
     * @param {Function} options.onConnected - async (data) => void, called once
     *   the account is connected (e.g. refresh status + show success toast).
     * @param {Function} options.setError - (message|null) => void, routes error
     *   messages to the component's own error field.
     * @param {Function} [options.onPopupBlocked] - () => void, called when the
     *   verification popup was blocked by the browser.
     * @param {string} [options.windowName] - name for the verification popup.
     * @returns {Promise<boolean>} true if polling started, false on failure.
     */
    async startTraktPolling({ requestCode, pollToken, onConnected, setError, onPopupBlocked, windowName = 'trakt-oauth' }) {
      setError(null);
      this.stopTraktPolling();
      try {
        const start = await requestCode();
        const {
          device_code: deviceCode,
          user_code: userCode,
          verification_url: verificationUrl,
          interval,
          expires_in: expiresIn,
        } = start.data || {};
        if (!deviceCode || !userCode || !verificationUrl) {
          throw new Error('Invalid Trakt OAuth response');
        }

        this.traktPollConfig = { pollToken, onConnected, setError };
        this.traktDeviceCode = deviceCode;
        this.traktUserCode = userCode;
        this.traktVerificationUrl = verificationUrl;
        this.traktPollDeadline = Date.now() + Math.max(Number(expiresIn || 600), 1) * 1000;
        const popup = window.open(verificationUrl, windowName, 'width=700,height=760');
        if ((!popup || popup.closed) && onPopupBlocked) {
          onPopupBlocked();
        }

        const intervalMs = Math.max(Number(interval || 5), 5) * 1000;
        this.isPollingTrakt = true;
        this.traktPollTimer = setInterval(() => this.pollTraktDeviceToken(), intervalMs);
        return true;
      } catch (err) {
        setError(err.response?.data?.message || err.message || 'Failed to start Trakt connection');
        return false;
      }
    },

    async pollTraktDeviceToken() {
      if (!this.traktDeviceCode || !this.traktPollConfig) return;
      const { pollToken, onConnected, setError } = this.traktPollConfig;
      if (this.traktPollDeadline && Date.now() >= this.traktPollDeadline) {
        this.stopTraktPolling();
        setError('Trakt authorization expired. Please try again.');
        return;
      }
      try {
        const poll = await pollToken(this.traktDeviceCode);
        if (poll.data?.connected) {
          this.stopTraktPolling();
          await onConnected(poll.data);
        }
      } catch (err) {
        const message = err.response?.data?.message || '';
        this.stopTraktPolling();
        setError(message || 'Trakt authorization failed. Please reconnect.');
      }
    },

    stopTraktPolling() {
      if (this.traktPollTimer) {
        clearInterval(this.traktPollTimer);
        this.traktPollTimer = null;
      }
      this.isPollingTrakt = false;
      this.traktDeviceCode = null;
      this.traktUserCode = '';
      this.traktVerificationUrl = '';
      this.traktPollDeadline = null;
      this.traktPollConfig = null;
    },
  },
};
