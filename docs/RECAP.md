# Your SuggestArr journey

## Year recap

**Year recap** appears in Home only from **December 15 through January 31**, following your browser's local calendar, for both users and administrators. In December it opens the current year; in January it opens the year just completed. The entry disappears from February 1 through December 14, including its sample-data preview. It never opens automatically. The regular title recap and milestones remain available year-round.

When using the Vite development server (`cd client` then `npm run serve`), **Year recap** is available year-round for development and testing. Production builds keep the seasonal window above.

Choose **Year recap → My activity** to open recorded annual progress, with a year selector, monthly requests, movie/series breakdown, genre tags and up to four recent discoveries with available metadata. Requests are attributed to the year of their first recorded successful request; retries and subsequent requests for the same title do not count again in later years. History deleted before the durable ledger was introduced cannot be recovered. The current year is labelled **Year to date**. Empty years and missing metadata stay empty rather than using demo values.

Everyone sees their linked profiles. Administrators can additionally select **Server recap**, except with `REQUEST_VISIBILITY=own_all`. The backend enforces these scopes and accepts no owner override. Personal recap without linked profiles invites you to link an account in My profile. Genres describe **requested titles**, not watched titles: percentages are the share of available genre tags, rounded to total 100%; the number of titles with genre metadata is shown. Covers come from existing metadata and the TMDb image host; no new metadata lookup is made. Usernames, profile IDs, server names and credentials are excluded from responses and images.

**Load Plex/Jellyfin watch activity** explicitly reads the configured server. Personal activity is limited to accounts linked to the current user. Plex uses paginated retained history, counting distinct movies and episodes per account without counting replays again. Jellyfin uses each played item's last-played timestamp within the selected year, including items marked as played. This snapshot cannot reconstruct earlier plays overwritten by a later play or items removed from the library; lifetime play counts are never attributed to one year. Both sources are labelled **Partial watch data**, including in exported viewing stories and summaries. The scan is bounded to 25 seconds, 50 profiles and 5,000 records per profile; hitting a record/profile cap is reported. Connection failures leave viewing counts unavailable, while request data remains usable. Counts are not collected or persisted in a new session store.

**Actual watch time is unavailable in this first integration.** Item runtime and lifetime play counts are not substitutes for session duration. The real recap therefore shows monthly **SuggestArr requests** instead of invented hours; the summary labels watch time unavailable. A full playback-history integration will be needed for reliable hours. See Jellyfin's [discussion of native playback-history limitations](https://github.com/jellyfin/jellyfin-meta/discussions/136).

Switch **Data source → Preview · Sample data** to explore the original seven-story 2026 demo, including fictional watch hours. Its four bundled SVG covers need no credentials or external artwork. Choose Jellyfin or Plex branding; administrators can select fivefold fictional server activity with 12 viewers. Demo images and captions retain **Preview · Sample data**. Switching modes never silently substitutes sample statistics for unavailable real activity. There is no automatic year-end announcement yet.

The player fills the available window with the complete 9:16 story and navigation controls always visible; longer details scroll independently. Stories advance every eight seconds. Use the progress segments, previous/next controls, arrow keys or horizontal swipes to navigate. Space toggles playback when the story area is focused; Escape closes the player. It pauses when the window loses focus, the tab is hidden or you export, and holds on the final story. Reduced-motion preferences disable animated transitions and start playback paused.

Download each completed composition as a **1080 × 1920 PNG**; the final story also offers **Download summary** and Reddit, Discord, X and Bluesky shortcuts. Copy-image, caption and native sharing options follow browser support. Images preserve the year, recorded-progress/partial-watch-data or demo labels, and exports pause playback. No publishing happens automatically.

The authenticated, read-only `GET /api/recap/year` endpoint accepts `year`, `scope=personal|server` and `include_playback=true|false` (default false). It uses the existing durable ledger and cached metadata, with portable SQL for SQLite, PostgreSQL and MySQL/MariaDB, without schema changes. Watch fetches use existing configured credentials, are rate limited, and never accept provider URLs or account IDs from the browser. Existing lifetime recap/statistics endpoints are unchanged; subpath routing continues through the configured axios base URL.

## Milestones and title recap

Home shows your recorded title requests, milestone badges and progress toward the next badge. Choose **Create your recap** to preview and download a 1080 × 1350 PNG, copy a caption, or share the image when your browser supports sharing files.

The journey panel groups your latest badge and progress toward the next milestone, without repeating the dashboard's all-time total. Its medallion shows the unlocked title threshold, rather than the current request count; the remaining titles and next badge appear together below the progress bar. The recap dialog is centered, up to 768 px wide and 80% of the viewport height on desktop, with at least 32 px of horizontal space around it. On mobile it leaves a 16 px margin. It has three views: **Preview** for the image and cover toggle, **Share** for the PNG thumbnail, social shortcuts and caption, and **Badges** for a milestone collection with unlocked, next and locked states, plus a separate anniversary badge. **Download PNG** and, where supported, **Copy image** remain available in the bottom bar in every view. Share and Badges shrink to their content when space permits, with a short height transition disabled by reduced-motion preferences. Width stays fixed between views. The preview keeps its original proportions while fitting the available window height; longer views scroll internally.

Administrators see installation-wide progress. Regular users see only titles associated with their linked Plex, Jellyfin or Emby profiles, even when the request list is configured to show everyone's requests. Administrators using `REQUEST_VISIBILITY=own_all` also receive a personal recap. Link your media account in **My profile** to start a personal recap.

## What is counted

Each distinct `(media type, TMDb ID)` successfully requested by SuggestArr counts once per installation. The recorded recipient determines which personal recap includes it. Failed attempts, retries, duplicate requests and requests imported from Seer do not count. A TV series counts as one title, irrespective of its seasons.

Progress uses a minimal, persistent database ledger, so automated cleanup of request history does not remove your achievements. Upgrading seeds this ledger from the SuggestArr requests still present in your database. Previously deleted history cannot be reconstructed. The date shown is the first recorded request, rather than the installation date. Include the database in your regular backups.

Badges unlock at 10, 100, 500, 1,000, 5,000 and 10,000 titles, plus 365 days after the first recorded request. Personal progress follows the media profiles currently linked to your account; changing or unlinking those profiles changes your personal recap.

## Sharing and privacy

The preview and PNG are rendered locally in your browser. By default, the image contains aggregate statistics, a badge, the project logo and its GitHub address. Usernames, server names and installation URLs are excluded. No telemetry or automatic publishing is added.

Cover artwork is shown by default: up to four requested titles with the highest available metadata ratings appear as overlapping, rotated portrait cards in the preview. Turn off **Show top-title covers** to hide your picks. Review the preview before sharing: covers can reveal viewing interests. Images are loaded directly from TMDb's image host; missing or non-exportable images use illustrated cards. Without artwork the image keeps its fan layout. The logo and 2:3 cover cards preserve their proportions, and the PNG preview maintains its 4:5 aspect ratio.

**Reddit** is the first quick-share shortcut, followed by **Discord**, **X** and **Bluesky**. Every shortcut tries to copy the PNG for pasting into the destination; if image clipboard access is unavailable or denied, it downloads the PNG for manual attachment. Reddit also saves the image for its upload composer. X and Bluesky links include the caption without replacing the copied image with clipboard text. Shortcut feedback disappears after five seconds.

**Share**, where supported, uses [native file sharing](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share) with the actual PNG and caption. It lets you choose a compatible app on your device; web composer links cannot automatically attach a local file. If native sharing fails, the image is downloaded; cancelling leaves the dialog unchanged. **Copy image** and **Copy caption** confirm with **Copied!** on the pressed button for 2.5 seconds, without moving the preview. **Download PNG** is always available. These behaviors apply to both the title recap and annual stories. These actions prepare your post; publishing is always your choice.

## Supporting the project

Administrators receive dismissible support cards in Home starting at 100 recorded titles and 14 days after the first recorded request. Further milestones are 500, 1,000, 5,000 and 10,000 titles, with at least 90 days between new milestone invitations. An upgrade that crosses several milestones displays only the highest one. A reminder can also appear after 180 days without an invitation.

Closing a card archives that invitation. Expand **Reminder options** on the card to postpone or stop invitations. **Remind me in 30 days** explicitly postpones the same invitation for 30 days, overriding the usual 90-day gap. **I already supported** and **Don't show these reminders** stop invitations for your administrator account, across browsers; these two choices are also available under **Reminder options** in the support dialog. These choices do not affect other administrators. Change them under **My profile → Support reminders**; no payment verification is required. Progress and recap sharing remain available.

The footer's **Support SuggestArr** button opens Ko-fi, Buy Me a Coffee, GitHub and Discord options at any time, for every user. Only admins also see the reminder options there.
