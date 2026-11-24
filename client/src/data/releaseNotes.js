/** Every past release note, on GitHub. */
export const RELEASES_URL = 'https://github.com/giuseppe99barchetta/SuggestArr/releases';

/**
 * Release note shown once in the dashboard "What's new" popup.
 *
 * Only the upcoming release lives here: what goes from `nightly` to `main`. While it is unreleased,
 * keep adding slides to this object. Once it has shipped on `main` (CI warns when you touch a note that
 * `main` already has), the next new feature or substantial change replaces it: empty `slides` and change
 * `id`, so everyone sees the popup once more. Older notes stay on the GitHub releases page.
 *
 *  1. `id` is stable, never the version number: nightly builds carry the previous release's version,
 *     and the Docker workflow only assigns versions on `main`.
 *  2. One slide per change, 4 or 5 at most: a FontAwesome `icon` (e.g. 'fa-route'), a `tone`
 *     ('brand' | 'good' | 'caution'), a short `heading`, one or two sentences of `text` on what changed,
 *     and up to 3 short `points` on what it means for the reader. `adminOnly` slides are hidden from
 *     non-admin users.
 */
export const WHATS_NEW = {
  id: 'season-followup',
  title: 'Next seasons, requested for you',
  slides: [
    {
      icon: 'fa-forward',
      tone: 'brand',
      heading: 'Next-season follow-up',
      text: 'An optional job requests the next season when people on your media server get close to the end of the current one, and picks up newly announced seasons once they are caught up.',
      points: [
        'Off by default; turn it on in Settings, Advanced.',
        'Runs every 6 hours on the watch history of all media server accounts.',
        'Requests go out as the configured Seer user, or straight to Sonarr.',
      ],
      adminOnly: true,
    },
  ],
};
