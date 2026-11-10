/**
 * Release notes shown once in the dashboard "What's new" popup, newest first.
 *
 * Adding one for a release:
 *  1. Add an entry here with a stable `id` (never the version number: nightly builds carry the
 *     previous release's version, and the Docker workflow only assigns versions on `main`).
 *  2. Give each slide an illustration as data: `art: { type: 'flow' | 'form' | 'features', ... }`
 *     (shapes in components/WhatsNewArt.vue, checked by `artProblems` in utils/whatsNew.js). No image
 *     files are needed: it is drawn with `currentColor`, tinted by the slide `tone`. Only for a visual
 *     none of those can express, use `icon: 'name.svg'` with a file in `src/assets/whats-new/<id>/`.
 *  3. Each slide says what changed (`changes`) and what that means for the reader (`impact`).
 *     `adminOnly` slides are hidden from non-admin users; `cta.tab` opens a dashboard tab.
 */
export const RELEASE_NOTES = [
  {
    id: 'arr-feature-parity',
    title: 'Radarr & Sonarr delivery catches up with Seer',
    slides: [
      {
        art: { type: 'form', fields: [{ label: 'Tag', value: 'suggestarr' }], optional: { label: 'User', value: 'suggestarr-user-anna' } },
        tone: 'brand',
        heading: 'Every title SuggestArr adds is tagged',
        changes: 'With direct delivery, titles added to Radarr or Sonarr carry the suggestarr tag. An option in Connections also tags them with who they were suggested for.',
        impact: 'You can filter SuggestArr\'s additions in Radarr and Sonarr, by person too. Cleanup only ever deletes tagged titles. Titles added before this update are not tagged.',
        cta: { label: 'Open Connections', tab: 'services' },
        adminOnly: true,
      },
      {
        art: { type: 'flow', source: { label: 'Radarr' }, targets: [{ label: 'Requests', sub: 'available', done: true }], arrow: 'file found' },
        tone: 'good',
        heading: 'Know when it is ready',
        changes: 'Requested titles now move from requested to processing, partial and available by reading Radarr and Sonarr, as they do with Seer.',
        impact: 'The Requests page shows the badges, the request.available webhook fires and personal notifications arrive without Seer. There is no play link: Radarr and Sonarr do not know one.',
      },
      {
        art: { type: 'features', locked: false, items: [{ label: 'Replace rejected', sub: 'approval queue' }, { label: 'Cleanup', sub: 'tagged only' }] },
        tone: 'caution',
        heading: 'Replacements and cleanup',
        changes: 'Rejecting a suggestion in the approval queue can bring one alternative from the same job. Cleanup deletes unfavorited titles straight in Radarr or Sonarr, files included.',
        impact: 'Cleanup never touches a title without the suggestarr tag, so what you added yourself is safe. Run a dry run first: it lists exactly what a real run would delete.',
        cta: { label: 'Open Cleanup', tab: 'cleanup' },
        adminOnly: true,
      },
      {
        art: { type: 'form', fields: [{ label: 'Quality profile', value: 'UHD-2160p' }, { label: 'Pause while', value: 'downloads queued' }] },
        tone: 'brand',
        heading: 'Profiles and pause, per job',
        changes: 'A job can use its own Radarr or Sonarr quality profile, root folder and tags, and wait while Radarr or Sonarr still has downloads in the queue.',
        impact: 'Jobs without their own profile keep the one from Connections. A stalled download keeps those jobs waiting until you clear it in Radarr or Sonarr.',
        cta: { label: 'Open Jobs', tab: 'jobs' },
      },
    ],
  },
  {
    id: 'request-backend-arr',
    title: 'Radarr & Sonarr can now take your requests',
    slides: [
      {
        art: { type: 'flow', source: { label: 'SuggestArr' }, via: 'Seer', targets: [{ label: 'Radarr' }, { label: 'Sonarr' }], badge: 'NEW' },
        tone: 'brand',
        heading: 'Choose where requests go',
        changes: 'Connections (and the setup wizard) now ask how requests are delivered: through Seer, straight to Radarr and Sonarr, or both.',
        impact: 'Nothing changes unless you change it: existing setups stay on Seer. Pick Radarr & Sonarr to run without Seer. "Both" keeps Seer for requests and also uses Radarr and Sonarr to know what you already own.',
        adminOnly: true,
        cta: { label: 'Open Connections', tab: 'services' },
      },
      {
        art: { type: 'flow', source: { poster: true }, targets: [{ label: 'Radarr', sub: 'movies', done: true }, { label: 'Sonarr', sub: 'TV shows', done: true }], arrow: 'auto-search' },
        tone: 'good',
        heading: 'Titles added straight to your libraries',
        changes: 'With direct delivery, an approved suggestion is added to Radarr (movies) or Sonarr (TV) and searched for right away.',
        impact: 'If you use approvals, nothing is added until you approve it. A title already in Radarr or Sonarr is never added twice, and suggestions you already own are skipped, monitored or not.',
      },
      {
        art: { type: 'form', fields: [{ label: 'Quality profile', value: 'HD-1080p' }, { label: 'Root folder', value: '/movies' }], optional: { label: 'Anime', value: 'Same as default' } },
        tone: 'brand',
        heading: 'Profiles, folders and anime',
        changes: 'For each instance you pick a quality profile, root folder and tags, with optional ones for anime. Anime falls back to the defaults when left empty.',
        impact: 'Choose them once in Connections after testing the connection. If a profile is later deleted in Radarr or Sonarr, SuggestArr tells you to choose it again.',
        adminOnly: true,
        cta: { label: 'Choose profiles', tab: 'services' },
      },
      {
        art: { type: 'features', items: [{ label: 'Auto-decline', sub: 'Seer only' }] },
        tone: 'caution',
        heading: 'What still needs Seer',
        changes: 'Only auto-decline of old pending requests depends on Seer: it declines requests waiting in Seer, and direct delivery has none.',
        impact: 'Replacing rejected requests, availability notifications, cleanup and the pause for pending downloads work with Radarr & Sonarr too. Requests already queued for Seer are still delivered to Seer, so switching never reroutes anything in flight.',
        adminOnly: true,
      },
    ],
  },
];
