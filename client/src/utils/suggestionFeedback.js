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
 * The verdict a 1-10 star rating stands for.
 *
 * Used when "Seen it" is also written to Trakt: the user picks an exact rating for
 * Trakt, and SuggestArr keeps its own coarser verdict so the recommender learns the
 * same way it does from the three icons. No rating means plain "seen".
 *
 * @param {number|null} rating Stars from 1 to 10, or null.
 * @returns {object} The SEEN_OPTIONS-shaped option to save.
 */
export function ratedSeenOption (rating) {
  if (!rating) return SEEN_OPTIONS.find(option => option.value === 'seen')
  let feedback = 'already_seen'
  if (rating >= 7) feedback = 'seen_liked'
  else if (rating <= 4) feedback = 'seen_disliked'
  return { value: 'rated', label: `Seen it, rated ${rating}/10`, icon: 'fas fa-star', feedback }
}

/**
 * Whether "Seen it" should ask for a star rating for the current user.
 *
 * True only when the admin enabled the Trakt write-back and this user's Trakt account
 * is linked, so the rating has somewhere to go. Any error falls back to the icons.
 *
 * @param {object} http Axios instance to send with.
 * @returns {Promise<boolean>}
 */
export async function loadSeenRatingMode (http) {
  try {
    const response = await http.get('/api/trakt/me')
    return response?.data?.sync_seen_feedback === true
  } catch {
    return false
  }
}

/**
 * Save a rating for one pending suggestion.
 *
 * The title and year travel with the rating so the next recommendation prompt can name
 * what the user liked or disliked instead of only suppressing an id.
 *
 * @param {object} http Axios instance to send with.
 * @param {number} suggestionId Pending suggestion id.
 * @param {object} option One entry from SEEN_OPTIONS, or from ratedSeenOption().
 * @param {object} item The suggestion being rated.
 * @param {object} [trakt] Optional Trakt details: { rating, markWatched }.
 * @returns {Promise} Resolves when the rating is stored.
 */
export function saveSeenFeedback (http, suggestionId, option, item, trakt = null) {
  // Number('') is 0, not NaN, so an absent date has to be excluded before parsing.
  const released = String(item.release_date || '').slice(0, 4)
  const year = released ? Number(released) : NaN
  const body = {
    feedback: option.feedback,
    reason_type: 'content',
    reason_text: option.label,
    title: item.title || null,
    year: Number.isFinite(year) ? year : null
  }
  if (trakt) {
    body.rating = trakt.rating || null
    body.mark_watched = trakt.markWatched !== false
  }
  return http.put(`/api/automation/requests/workflow/${suggestionId}/feedback`, body)
}
