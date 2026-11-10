/**
 * Release notes shown once in the dashboard "What's new" popup, newest first.
 *
 * Adding one for a release:
 *  1. Add an entry here with a stable `id` (never the version number: nightly builds carry the
 *     previous release's version, and the Docker workflow only assigns versions on `main`).
 *  2. Draw one SVG per slide in `src/assets/whats-new/<id>/` (viewBox 0 0 120 120, `currentColor`
 *     strokes, no fixed colours: the slide `tone` tints it).
 *  3. Each slide says what changed (`changes`) and what that means for the reader (`impact`).
 *     `adminOnly` slides are hidden from non-admin users; `cta.tab` opens a dashboard tab.
 */
export const RELEASE_NOTES = [
  {
    id: 'request-backend-arr',
    title: 'Radarr & Sonarr can now take your requests',
    slides: [
      {
        icon: 'choice.svg',
        tone: 'brand',
        heading: 'Choose where requests go',
        changes: 'Connections (and the setup wizard) now ask how requests are delivered: through Seer, straight to Radarr and Sonarr, or both.',
        impact: 'Nothing changes unless you change it: existing setups stay on Seer. Pick Radarr & Sonarr to run without Seer. "Both" keeps Seer for requests and also uses Radarr and Sonarr to know what you already own.',
        adminOnly: true,
        cta: { label: 'Open Connections', tab: 'services' },
      },
      {
        icon: 'direct.svg',
        tone: 'good',
        heading: 'Titles added straight to your libraries',
        changes: 'With direct delivery, an approved suggestion is added to Radarr (movies) or Sonarr (TV) and searched for right away.',
        impact: 'If you use approvals, nothing is added until you approve it. A title already in Radarr or Sonarr is never added twice, and suggestions you already own are skipped, monitored or not.',
      },
      {
        icon: 'profiles.svg',
        tone: 'brand',
        heading: 'Profiles, folders and anime',
        changes: 'For each instance you pick a quality profile, root folder and tags, with optional ones for anime. Anime falls back to the defaults when left empty.',
        impact: 'Choose them once in Connections after testing the connection. If a profile is later deleted in Radarr or Sonarr, SuggestArr tells you to choose it again.',
        adminOnly: true,
        cta: { label: 'Choose profiles', tab: 'services' },
      },
      {
        icon: 'limits.svg',
        tone: 'caution',
        heading: 'What is not available without Seer',
        changes: 'Auto-decline of old pending requests, replacing rejected requests, availability notifications, cleanup and "pause while Seer has pending requests" depend on Seer.',
        impact: 'In Radarr & Sonarr mode these options are hidden or switched off. Requests already queued for Seer are still delivered to Seer, so switching never reroutes anything in flight.',
        adminOnly: true,
      },
    ],
  },
];
