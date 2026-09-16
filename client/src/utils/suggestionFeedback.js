/**
 * Rating a pending suggestion, shared by every UI that lists them.
 *
 * This lives outside the components on purpose: the actions have to stay identical
 * wherever pending suggestions appear, and duplicating the list is how they drift apart.
 */

/**
 * The ratings offered on a pending card.
 *
 * All three stop the title being suggested again. They differ in what the recommender
 * learns from them, which is why 'already_seen' exists as a separate option: having
 * watched something is not a verdict on it, and recording it as one would teach a
 * preference the user never expressed.
 */
export const SEEN_OPTIONS = [
  { value: 'liked', label: 'Seen it, liked it', icon: 'fas fa-thumbs-up', feedback: 'seen_liked' },
  { value: 'disliked', label: 'Seen it, did not like it', icon: 'fas fa-thumbs-down', feedback: 'seen_disliked' },
  { value: 'seen', label: 'Seen it', icon: 'fas fa-eye', feedback: 'already_seen' }
]

/**
 * Save a rating for one pending suggestion.
 *
 * The title and year travel with the rating so the next recommendation prompt can name
 * what the user liked or disliked instead of only suppressing an id.
 *
 * @param {object} http Axios instance to send with.
 * @param {number} suggestionId Pending suggestion id.
 * @param {object} option One entry from SEEN_OPTIONS.
 * @param {object} item The suggestion being rated.
 * @returns {Promise} Resolves when the rating is stored.
 */
export function saveSeenFeedback (http, suggestionId, option, item) {
  // Number('') is 0, not NaN, so an absent date has to be excluded before parsing.
  const released = String(item.release_date || '').slice(0, 4)
  const year = released ? Number(released) : NaN
  return http.put(`/api/automation/requests/workflow/${suggestionId}/feedback`, {
    feedback: option.feedback,
    reason_type: 'content',
    reason_text: option.label,
    title: item.title || null,
    year: Number.isFinite(year) ? year : null
  })
}
