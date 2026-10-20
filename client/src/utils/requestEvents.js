/**
 * App-wide signal that the pending-request queue changed.
 *
 * The sidebar badge lives in the dashboard shell while the approve / reject / seen
 * actions live in the pages it hosts, which are swapped in by a dynamic component.
 * A window event keeps them decoupled: pages announce a change, the shell recounts.
 */

export const REQUESTS_CHANGED = 'suggestarr:requests-changed'

/**
 * Announce that suggestions were approved, rejected or otherwise moved, so anything
 * showing a pending count can refresh it.
 */
export function notifyRequestsChanged () {
  window.dispatchEvent(new CustomEvent(REQUESTS_CHANGED))
}
