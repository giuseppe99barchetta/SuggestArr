/**
 * Options-API mixin encapsulating the Simkl PIN polling logic used by
 * SimklMediaUsers.
 *
 * It is the Simkl counterpart of traktDevicePolling, and differs in three ways
 * that are not cosmetic:
 *
 *  - The poll identifier is the `user_code`, not Trakt's `device_code`. The
 *    server holds the code against the requesting identity, so the browser
 *    keeps it only to know a flow is in flight.
 *  - Simkl signals an expired or already-consumed code by *restarting* the
 *    flow: the response carries a `device_code` key. The backend raises on
 *    that, so an expired code arrives here as a thrown error, but the deadline
 *    below is the local safeguard for a poll loop that would otherwise run
 *    forever if the tab is left open.
 *  - The PIN window is up to fifteen minutes, against Trakt's much shorter
 *    one, which is long enough that stranding the user without an exit is a
 *    real cost. Hence `cancelSimklPolling`, which also clears the pending code
 *    server-side so it cannot be completed later.
 */
export default {
  data() {
    return {
      isPollingSimkl: false,
      simklUserCode: '',
      simklVerificationUri: '',
      simklPollTimer: null,
      simklPollDeadline: null,
      // Per-poll-session configuration captured at start time.
      simklPollConfig: null,
    };
  },

  beforeUnmount() {
    this.stopSimklPolling();
  },

  methods: {
    /**
     * Begin a Simkl PIN authorization flow.
     *
     * @param {Object} options
     * @param {Function} options.requestCode - async () => axios response with
     *   { user_code, verification_uri, interval, expires_in }.
     * @param {Function} options.pollToken - async () => axios response with
     *   { connected, ... } (HTTP 202 while pending). Takes no argument: the
     *   server reads the pending code from its own state.
     * @param {Function} options.onConnected - async (data) => void, called once
     *   the account is connected.
     * @param {Function} options.setError - (message|null, error?) => void,
     *   routes error messages to the component's own error field. The original
     *   error is passed alongside so a caller can branch on a response code
     *   rather than on message text.
     * @param {Function} [options.cancelCode] - async () => void, clears the
     *   pending code server-side when the user cancels.
     * @returns {Promise<boolean>} true if polling started, false on failure.
     */
    async startSimklPolling({ requestCode, pollToken, onConnected, setError, cancelCode }) {
      setError(null);
      this.stopSimklPolling();
      try {
        const start = await requestCode();
        const {
          user_code: userCode,
          verification_uri: verificationUri,
          interval,
          expires_in: expiresIn,
        } = start.data || {};
        if (!userCode) {
          throw new Error('Invalid Simkl PIN response');
        }

        this.simklPollConfig = { pollToken, onConnected, setError, cancelCode };
        this.simklUserCode = userCode;
        // Simkl documents simkl.com/pin as the destination, but the response
        // is the authority in case that ever moves.
        this.simklVerificationUri = verificationUri || 'https://simkl.com/pin';
        this.simklPollDeadline = Date.now() + Math.max(Number(expiresIn || 900), 1) * 1000;

        // Poll at the cadence Simkl asks for. Going faster is how an app gets
        // its client ID suspended.
        const intervalMs = Math.max(Number(interval || 5), 5) * 1000;
        this.isPollingSimkl = true;
        this.simklPollTimer = setInterval(() => this.pollSimklPinToken(), intervalMs);
        return true;
      } catch (err) {
        setError(err.response?.data?.message || err.message || 'Failed to start Simkl connection', err);
        return false;
      }
    },

    async pollSimklPinToken() {
      if (!this.simklUserCode || !this.simklPollConfig) return;
      const { pollToken, onConnected, setError } = this.simklPollConfig;
      if (this.simklPollDeadline && Date.now() >= this.simklPollDeadline) {
        this.stopSimklPolling();
        setError('Simkl PIN expired. Please try again.');
        return;
      }
      try {
        const poll = await pollToken();
        if (poll.data?.connected) {
          this.stopSimklPolling();
          await onConnected(poll.data);
        }
      } catch (err) {
        const message = err.response?.data?.message || '';
        this.stopSimklPolling();
        setError(message || 'Simkl authorization failed. Please try again.', err);
      }
    },

    /**
     * Abandon an in-flight PIN at the user's request.
     *
     * The server call is best-effort: the local state is cleared either way,
     * since leaving the card stuck in a waiting state because a cleanup call
     * failed would be worse than the orphaned code it is trying to prevent.
     */
    async cancelSimklPolling() {
      const cancelCode = this.simklPollConfig?.cancelCode;
      this.stopSimklPolling();
      if (!cancelCode) return;
      try {
        await cancelCode();
      } catch {
        // Intentionally ignored; the code expires on its own.
      }
    },

    stopSimklPolling() {
      if (this.simklPollTimer) {
        clearInterval(this.simklPollTimer);
        this.simklPollTimer = null;
      }
      this.isPollingSimkl = false;
      this.simklUserCode = '';
      this.simklVerificationUri = '';
      this.simklPollDeadline = null;
      this.simklPollConfig = null;
    },
  },
};
