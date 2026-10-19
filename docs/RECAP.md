# Your SuggestArr journey

Home shows your recorded title requests, milestone badges and progress toward the next badge. Choose **Create your recap** to preview and download a 1080 × 1350 PNG, copy a caption, or share the image when your browser supports sharing files.

Administrators see installation-wide progress. Regular users see only titles associated with their linked Plex, Jellyfin or Emby profiles, even when the request list is configured to show everyone's requests. Administrators using `REQUEST_VISIBILITY=own_all` also receive a personal recap. Link your media account in **My profile** to start a personal recap.

## What is counted

Each distinct `(media type, TMDb ID)` successfully requested by SuggestArr counts once per installation. The recorded recipient determines which personal recap includes it. Failed attempts, retries, duplicate requests and requests imported from Seer do not count. A TV series counts as one title, irrespective of its seasons.

Progress uses a minimal, persistent database ledger, so automated cleanup of request history does not remove your achievements. Upgrading seeds this ledger from the SuggestArr requests still present in your database. Previously deleted history cannot be reconstructed. The date shown is the first recorded request, rather than the installation date. Include the database in your regular backups.

Badges unlock at 10, 100, 500, 1,000, 5,000 and 10,000 titles, plus 365 days after the first recorded request. Personal progress follows the media profiles currently linked to your account; changing or unlinking those profiles changes your personal recap.

## Sharing and privacy

The preview and PNG are rendered locally in your browser. By default, the image contains aggregate statistics, a badge, the project logo and its GitHub address. Usernames, server names and installation URLs are excluded. No telemetry or automatic publishing is added.

Cover artwork is shown by default: up to four requested titles with the highest available metadata ratings appear as overlapping, rotated portrait cards. The same scoped titles are previewed beside the image. Turn off **Show top-title covers** to hide your picks. Review the preview before sharing: covers can reveal viewing interests. Images are loaded directly from TMDb's image host; missing or non-exportable images use illustrated cards. Without artwork the image keeps its fan layout. The logo and 2:3 cover cards preserve their proportions, and the PNG preview maintains its 4:5 aspect ratio.

**Reddit** is the first quick-share shortcut, followed by **Discord**, **X** and **Bluesky**. The social shortcuts open the post composer and save the PNG for you to attach manually; the caption is copied when the browser permits it. Discord copies the PNG to your clipboard where supported, or saves it as a file to attach in your chosen conversation. **Copy image**, **Copy caption**, **Download PNG** and native file sharing are also available as supported by the browser. These actions prepare your post; publishing is always your choice.

## Supporting the project

Administrators receive dismissible support cards in Home starting at 100 recorded titles and 14 days after the first recorded request. Further milestones are 500, 1,000, 5,000 and 10,000 titles, with at least 90 days between new milestone invitations. An upgrade that crosses several milestones displays only the highest one. A reminder can also appear after 180 days without an invitation.

Closing a card archives that invitation. **Remind me in 30 days** explicitly postpones the same invitation for 30 days, overriding the usual 90-day gap. **I already supported** and **Don't show these reminders** stop invitations for your administrator account, across browsers. These choices do not affect other administrators. Change them under **My profile → Support reminders**; no payment verification is required. Progress and recap sharing remain available.

The footer's **Support SuggestArr** link opens Ko-fi, Buy Me a Coffee and GitHub support options at any time.
