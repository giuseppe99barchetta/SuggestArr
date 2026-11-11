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
  id: 'arr-direct-delivery',
  title: 'Radarr & Sonarr can now take your requests',
  slides: [
    {
      icon: 'fa-route',
      tone: 'brand',
      heading: 'Choose where requests go',
      text: 'Connections and the setup wizard now ask how requests are delivered: through Seer, straight to Radarr and Sonarr, or both.',
      points: [
        'Existing setups stay on Seer until you change it.',
        'With Both, Seer takes requests and Radarr and Sonarr report what you own.',
        'Only auto-decline of old pending requests still needs Seer.',
      ],
      adminOnly: true,
    },
    {
      icon: 'fa-tag',
      tone: 'good',
      heading: 'Titles added straight to your libraries',
      text: 'With direct delivery, an approved suggestion is added to Radarr (movies) or Sonarr (TV) and searched for right away.',
      points: [
        'Tagged suggestarr, and optionally with who it was suggested for.',
        'A title already in Radarr or Sonarr is never added twice.',
        'Titles added before this update are not tagged.',
      ],
    },
    {
      icon: 'fa-bell',
      tone: 'good',
      heading: 'Know when it is ready',
      text: 'Requested titles move from requested to processing, partial and available by reading Radarr and Sonarr, as they do with Seer.',
      points: [
        'Badges on the Requests page, the request.available webhook and personal notifications work without Seer.',
        'There is no play link: Radarr and Sonarr do not know one.',
      ],
    },
    {
      icon: 'fa-broom',
      tone: 'caution',
      heading: 'Replacements and cleanup',
      text: 'Rejecting a suggestion in the approval queue can bring one alternative from the same job. Cleanup deletes unfavorited titles straight in Radarr or Sonarr, files included.',
      points: [
        'Cleanup only ever deletes titles tagged suggestarr.',
        'A dry run lists exactly what a real run would delete.',
      ],
      adminOnly: true,
    },
    {
      icon: 'fa-sliders',
      tone: 'brand',
      heading: 'Profiles and pause, per job',
      text: 'Choose a quality profile, root folder and tags per instance in Connections, with optional ones for anime, and override them per job.',
      points: [
        'Jobs can wait while Radarr or Sonarr still has downloads in the queue.',
        'A stalled download keeps them waiting until you clear it.',
      ],
      adminOnly: true,
    },
  ],
};
