# SuggestArr Installation Guide

Images are published to Docker Hub (`ciuse99/suggestarr`) and GitHub Container Registry (`ghcr.io/giuseppe99barchetta/suggestarr`).

SuggestArr is a self-hosted web app that reads watch activity from Plex, Jellyfin, or Emby, finds recommendations through TMDb, and sends requests to Seer. The recommended installation method is Docker Compose because it keeps the Python backend, built Vue frontend, dependencies, scheduler, and persistent data in one predictable container.

## Requirements

Before installing, prepare:

- Docker and Docker Compose, or Python 3.13 and Node.js 22 for a source install.
- A TMDb API key from <https://www.themoviedb.org/settings/api>.
- One media server: Plex, Jellyfin, or Emby.
- A running Seer instance, such as Jellyseerr or Overseerr-compatible Seer.
- Network access from SuggestArr to TMDb, your media server, and Seer.
- Optional: OMDb API key for IMDb-based filters.
- Optional: MDBList API key (`MDBLIST_API_KEY`, from <https://mdblist.com/preferences/>) to import public MDBList lists. See [Public list import](FEATURES.md#public-list-import).
- Optional: OpenAI-compatible LLM provider for AI recommendations and AI Search.
- Optional: a Trakt app Client ID for per-user Trakt watch-history integration. Client Secret is optional; older apps may still have one.
- Optional: Simkl app Client ID for per-user Simkl watch-history integration.

## Recommended Install: Docker Compose

Create a folder for SuggestArr:

```bash
mkdir suggestarr
cd suggestarr
mkdir config_files
```

Create `docker-compose.yml`:

```yaml
services:
  suggestarr:
    image: ciuse99/suggestarr:latest
    container_name: suggestarr
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./config_files:/app/config/config_files
    environment:
      - SUGGESTARR_PORT=5000
      - LOG_LEVEL=INFO
      - TZ=Europe/Rome
```

Start SuggestArr:

```bash
docker compose up -d
```

Open:

```text
http://localhost:5000
```

On another machine, replace `localhost` with the host IP:

```text
http://192.168.1.10:5000
```

### Persistent Files

Keep `config_files` backed up. It contains:

- `config.yaml`: app settings and integration values.
- `requests.db`: SQLite database when using default SQLite mode.
- `secret.key`: JWT signing key. Losing it signs users out.
- `app.log`: rotating application log.

## First-Run Setup

When opening SuggestArr for the first time:

1. Create the first admin account.
2. Follow the setup wizard.
3. Add your TMDb API key.
4. Select Plex, Jellyfin, or Emby.
5. Enter media server URL and token.
6. Enter Seer URL and API key.
7. Select users and libraries.
8. Optional: add the Trakt Client ID in Services > Trakt. If your app has a Client Secret, you may keep it configured.
9. Optional: add a Simkl Client ID in Services > Simkl.
10. Save configuration.
11. Have each user link their media-server account from Profile.
12. Optional: have each user link their Trakt account from Profile > Trakt Account, their Simkl account from Profile > Simkl Account, or both.
13. Create or adjust jobs from the Jobs page.

Use internal network URLs when running everything in Docker. Example:

```text
http://jellyfin:8096
http://jellyseerr:5055
```

If media server or Seer runs directly on the Docker host, use host IP instead of `localhost`, because `localhost` inside the container means the SuggestArr container itself.

Example:

```text
http://192.168.1.10:8096
http://192.168.1.10:5055
```

## Configuration Screenshots

The screenshots below show the main configuration areas. Values shown in the images are examples or masked placeholders.

### Services

Use this page to configure TMDb, optional OMDb, optional MDBList, your media server, Trakt and Simkl app credentials, and Seer.

For Trakt and Simkl, Services stores only the shared app-level credentials. Individual accounts are linked by each user from their Profile page. Simkl needs only a Client ID, because its device flow has no client secret.

![SuggestArr services configuration](docs/assets/suggestarr-config-services.png)

### Users and Profile

Use this page to manage local accounts, assign media-server accounts, and link personal Trakt and Simkl accounts.

- Admins use Users to create accounts, control permissions, and assign media accounts.
- Users shows account totals, enabled sign-ins, administrators, and accounts linked to the selected media server. Search by account or linked media username and filter by role. Each account card shows page access, membership dates, its assigned media account, and the Seer identity used for requests. Enabled means the account can sign in, not that the person is currently online.
- Each user uses Profile to link their own Plex, Jellyfin, or Emby account.
- After the media account is linked, the user can link their own Trakt account from Profile > Trakt Account and their Simkl account from Profile > Simkl Account. Both can be linked at the same time.
- Opening Recent Trakt Preview automatically fetches recent Trakt items and shows a loading icon while it loads. Recent Simkl Preview behaves the same way, reading from the locally cached history.

Jellyfin account linking uses the modern `Authorization: MediaBrowser ...` header, so Jellyfin 12 does not require enabling legacy authorization. The legacy header is also sent for compatibility with Emby and older servers.

### Jobs

Use this page to create, preview, run, enable, or disable automated recommendation and discovery jobs.

Jobs can also pause automatically while Seer has pending requests awaiting approval or denial.

![SuggestArr jobs configuration](docs/assets/suggestarr-config-jobs.png)

### Database

SQLite is the recommended default. PostgreSQL, MySQL, and MariaDB are available for larger or more advanced deployments.

![SuggestArr database configuration](docs/assets/suggestarr-config-database.png)

### Advanced

Use this page for AI provider setup, logging, caching, API timeouts, reverse-proxy subpath, registration, authentication, and Cleanup Automation.

![SuggestArr advanced configuration](docs/assets/suggestarr-config-advanced.png)

## Best Configuration

### General

Recommended defaults:

- `LOG_LEVEL=INFO` for normal use.
- Keep authentication enabled.
- Keep SQLite for small and normal home installs.
- Use PostgreSQL only if you expect many users, many jobs, or want central database backups.
- Keep `EXCLUDE_DOWNLOADED=true`.
- Keep `EXCLUDE_REQUESTED=true`.
- Start with daily or every-12-hours jobs. Increase frequency only after requests look good.
- Use dry-run before enabling aggressive automated jobs.
- Enable job pausing when you want each automation batch reviewed in Seer before the next run starts.
- Keep Cleanup Automation in dry-run mode until its audit log matches what you expect.

### Content Filters

Good starting values:

- `MAX_SIMILAR_MOVIE`: `5`
- `MAX_SIMILAR_TV`: `2`
- `SEARCH_SIZE`: `20`
- `MAX_CONTENT_CHECKS`: `10`
- `FILTER_TMDB_THRESHOLD`: `6.5` or higher
- `FILTER_TMDB_MIN_VOTES`: `100` or higher
- `FILTER_INCLUDE_NO_RATING`: disabled if you want safer quality control
- `REQUEST_FIRST_SEASON_ONLY`: enabled if you want TV requests to stay controlled

For streaming availability filters:

- Set `FILTER_REGION_PROVIDER` to your country code, such as `US`, `IT`, or `GB`.
- Select streaming services you already have.
- Keep `FILTER_INCLUDE_TVOD=false` unless you also want rent/buy availability excluded.

### Jobs

Best practice:

- Create one focused movie job and one focused TV job instead of one broad job.
- Use filters per job: genre, TMDb keyword, language, rating, runtime, provider exclusions. TMDb keywords apply to Discover and recommendation jobs, letting you exclude a theme such as `Bollywood` without excluding all content in its language.
- Run a dry run first.
- Check results in Seer before enabling full automation.
- Enable Pause while Seer requests are pending if Seer approvals are part of your flow.
- Use lower result counts for frequent jobs.
- Optionally set **Automatic requests per user**. It limits new automated queue entries for each linked media user in a rolling time window; `0` keeps the previous unlimited behavior. Manual requests are not affected.
- In Requests, use **My feedback** to mark a proposal as interesting, not interesting, already seen, too similar, or save it for later. This is personal to your SuggestArr account and linked media profile; it does not blacklist the item for everyone.
- Content details fade in their background artwork once it has loaded. The fade is disabled when your system prefers reduced motion.
- Positive feedback moves matching candidates earlier; negative feedback excludes them from future automated recommendation jobs for that same account and media profile. Ranking happens inside SuggestArr, so feedback reasons and account/profile identifiers are not sent to TMDb or the configured LLM provider.
- Choose **No feedback** to delete a saved signal. Feedback is otherwise retained until it is cleared or the SuggestArr account is deleted.

Example schedule choices:

```text
daily
every_12h
0 3 * * *
```

Use standard cron only if presets are not enough.
Numeric weekdays follow standard cron: `0` and `7` are Sunday, `1` is Monday.

### Pause Jobs While Seer Requests Are Pending

Each discover or recommendation job has a schedule option:

```text
Pause while Seer requests are pending
```

When enabled, SuggestArr checks Seer before the job runs. If Seer has any request still awaiting approval or denial, SuggestArr skips that job for this run.

This applies to:

- normal scheduled runs
- Run now for one job
- Force run all jobs

Paused jobs are logged in execution history as skipped with this reason:

```text
Paused: Seer has pending requests awaiting approval or denial.
```

Use this option when you review or approve Seer requests manually. It prevents a second automation run from adding more requests before the previous batch has been accepted or rejected.

If you want SuggestArr to keep requesting even while Seer has pending approvals, leave this option disabled.

### AI Recommendations and AI Search

AI features are optional. They work with OpenAI-compatible APIs.

Enable:

1. Go to Settings > Advanced.
2. Configure AI provider.
3. Enable the AI suggestion algorithm if you want automated AI recommendations.

OpenAI example:

```text
API Key: sk-proj-...
Base URL: leave empty
Model: gpt-4o-mini
```

Ollama example with Docker Compose:

```yaml
services:
  suggestarr:
    image: ciuse99/suggestarr:latest
    container_name: suggestarr
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./config_files:/app/config/config_files
    environment:
      - SUGGESTARR_PORT=5000
      - LOG_LEVEL=INFO
      - TZ=Europe/Rome

  ollama:
    image: ollama/ollama
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  ollama_data:
```

Pull a model:

```bash
docker exec -it ollama ollama pull mistral
```

Set in SuggestArr:

```text
Base URL: http://ollama:11434/v1
Model: mistral
API Key: leave empty
```

## Trakt Integration

Trakt support is optional. It adds extra watch-history context to recommendation jobs by using each user's own Trakt account.

### What is stored

SuggestArr stores:

- App-level Trakt Client ID in Services, plus an optional Client Secret for older apps.
- Per-media-user Trakt OAuth tokens in the database.
- The linked Trakt username and status.

SuggestArr does not expose Trakt access tokens in API responses or frontend lists.

Configuration export (Dashboard **Export**) can include Trakt link metadata and source settings by default. OAuth tokens are redacted unless you choose a full backup. See [UI Export and Import](#ui-export-and-import).

### Create a Trakt OAuth app

1. Open <https://developer.trakt.tv/apps/new> and sign in with your GitHub account (the Trakt developer portal requires a verified GitHub login).
2. Fill in the form:
   - **App name**: anything, e.g. `SuggestArr`.
   - **Description**: optional.
   - **Redirect URIs**: `urn:ietf:wg:oauth:2.0:oob` (one per line).
   - **Allowed origins**: leave empty.
3. Click **Create app**, then copy the Client ID from the app page. New Trakt apps created after the PKCE change do not receive a Client Secret; older apps can continue using theirs.
4. In SuggestArr, open Services > Trakt.
5. Paste the Client ID and, if your app has one, the optional Client Secret.
6. Save.

Device-code OAuth is used for user linking, so users do not need to paste Trakt passwords or tokens into SuggestArr.

SuggestArr sends `urn:ietf:wg:oauth:2.0:oob` as the redirect URI when refreshing tokens, so it must be listed in the app. Trakt shows an **Insecure redirect URIs** warning because it is not HTTPS; that is expected for the device-code flow and the form still saves it. Existing apps can add it from **Edit** on <https://developer.trakt.tv/apps>.

### Link media-server users first

Trakt links attach to a media-server profile. Before linking Trakt:

1. Make sure a media server is configured in Services.
2. Select the correct media-server users during setup, or assign them from Users.
3. Each user opens Profile and links their Plex, Jellyfin, or Emby account.

If a user has no linked media-server account, Profile > Trakt Account will ask them to link the media server first.

### Let users link Trakt

Each user can link Trakt without admin help after app credentials are configured:

1. Log in as the user.
2. Open Profile.
3. Find Trakt Account.
4. Click Link Trakt.
5. SuggestArr shows a device code and opens the Trakt activation page.
6. Enter the code on Trakt and approve access.
7. Wait for SuggestArr to show the linked Trakt username.

Admins can reach the same embedded profile area from Users.

### Verify with Recent Trakt Preview

After linking:

1. Open Profile > Trakt Account.
2. Expand Recent Trakt Preview.
3. SuggestArr automatically fetches recent Trakt items.
4. A loading icon is shown while data is loading.
5. Recent items display title, year, media type, TMDb ID, and watched date when available.

If no items appear:

- Confirm the Trakt account has watched history.
- Confirm the media-server account is linked.
- Confirm the Trakt Client ID is saved in Services. A Client Secret is optional for new Trakt apps.
- Check Logs for Trakt API errors.

### Use Trakt in jobs

Recommendation jobs can use linked Trakt accounts:

- Use Trakt as Seed: recent Trakt watches can seed recommendations.
- Use Trakt ratings (`use_trakt_ratings`, default on): the user's most recent Trakt ratings (`/sync/ratings`, same 1-10 scale) are added as seeds on every run, so ratings given in the Trakt app or synced into Trakt from streaming services steer recommendations. 7-10 counts as liked, 1-4 as did not like. A rating set in SuggestArr (Ratings page or CSV import) wins over the Trakt one for the same title. Needs Use Trakt as Seed; ratings are read live and are not shown on the Ratings page.
- Exclude Trakt Watched: watched Trakt items can be skipped.

If no linked Trakt accounts exist, job filters will warn that Trakt is not usable yet. Media-server history still works without Trakt.

### Send "Seen it" to Trakt

Enable **Send "Seen it" to Trakt** in Services > Trakt (`TRAKT_SYNC_SEEN_FEEDBACK`, default `false`) to copy a user's "Seen it" answers to their own linked Trakt account.

When the option is on and the user has linked Trakt, the eye button on a pending suggestion opens a rating dialog instead of the three icons:

- Pick **1 to 10 stars** (Trakt's scale) and **Save rating**, or choose **Seen it, no rating**.
- The rating is sent to Trakt as given. SuggestArr keeps its own verdict for future suggestions: 7-10 counts as liked, 1-4 as did not like, 5-6 and no rating as plain seen.
- Movies are added to the user's Trakt watch history.
- For a show, **Mark all episodes as watched** is off by default. Leave it off for a partly watched series and the show is only rated. With no stars and the box unticked the dialog says **Seen it, SuggestArr only**: nothing is sent to Trakt in that case.
- If saving fails, the dialog stays open with the chosen stars.

Users without a linked Trakt account, and everyone while the option is off, keep the three icons. Feedback on requests already sent to Seer follows the same rules without the dialog: liked and did not like are rated 8 and 3, a movie gets a play, and a show is only rated.

- **Whose account:** the Trakt account linked to the media profile of the user who clicked, not the media user the suggestion was made for, and only when that profile is **verified** (assigned by an admin or proven by the media server's sign-in). A self-selected Jellyfin or Emby profile is never written through, since it may name someone else's account.
- **No duplicate plays:** a movie that already has a play on Trakt gets no new one, and a show only gets plays for its aired episodes that are still unwatched. Saving the same feedback again, changing the rating or retrying is therefore safe. A new play is stamped with the time of the click, because SuggestArr does not know when the title was actually watched.
- Other feedback (interested, not interested, too similar, save for later) is never sent.
- The write happens in the background after the feedback is saved. A Trakt failure is logged and never blocks the feedback or the rejection that follows it.
- Removing feedback in SuggestArr does not remove the play or rating from Trakt.

The feedback endpoints (`PUT /api/automation/requests/workflow/<id>/feedback` and `PUT /api/automation/requests/media/<type>/<tmdb_id>/feedback`) accept two optional fields for this: `rating` (integer 1-10) and `mark_watched` (boolean). When `mark_watched` is omitted, a movie gets a play and a show does not. `GET /api/trakt/me` reports `sync_seen_feedback: true` when the option is on and the caller's verified profile has a linked Trakt account.

## Auto-decline pending Seerr requests

Open **Approvals -> Seerr pending requests**:

1. Set **Auto-decline after (days)** to an integer from 1 to 365. `0` disables both scheduled and manual expiry.
2. Keep **Preview only (dry-run)** enabled, save, and select **Preview now** to review the audit log.
3. To enable real declines, disable preview-only mode and save. The daily run at 04:30 server time now applies declines; **Decline expired requests** runs it immediately. Expand **Activity log** to inspect the results or refresh the log.

These settings are independent of approval inside SuggestArr. They use `SEER_AUTO_DECLINE_DAYS` (default `0`) and `SEER_AUTO_DECLINE_DRY_RUN` (default `true`) in the runtime configuration. Preview always reads the saved settings, so save pending changes before running it.

Only requests sent after installing this version are tracked. SuggestArr saves the exact remote request ID, creation timestamp, and Seerr base URL even when expiry is disabled. It does not infer identities for older requests. Each pass verifies the current remote identity and pending status before declining; changing the configured Seerr URL excludes requests tracked for the previous URL. Age is measured in UTC from creation in Seerr, not generation of the suggestion in SuggestArr.

The Seerr API key must have `MANAGE_REQUESTS` or `ADMIN` permissions. Requests already approved, declined or removed are skipped. Failures are logged and retried on a later pass; no media files are deleted. Local request history remains in place to prevent immediate resubmission.

Admins can also use `POST /api/automation/requests/expiry/run` with an optional boolean `dry_run`, and `GET /api/automation/requests/expiry/log?limit=100` (maximum 500 entries). Concurrent runs return `409`; manual runs are limited to five per minute. The run returns candidate, simulated, declined, skipped and error counts. The log records delivery/Seerr/TMDb IDs, media type, time, mode, outcome and reason.

### Replace rejected requests

In **Settings → Approvals**, enable **Generate an alternative after rejection** (`REPLACE_REJECTED_REQUESTS`, default `false`) to try another title when a tracked SuggestArr request is explicitly declined in Seerr, Jellyseerr or Overseerr. Checks run every 15 minutes; admins can also use **Check rejections now** after saving the setting.

Only deliveries with a saved remote request ID, creation timestamp, instance URL and originating job are eligible. Older untracked requests are not matched by title. Deleted requests, API failures and identity mismatches never count as rejections. Automatic expiry declines are excluded, including attempts interrupted after the decline was requested.

Each rejection can produce at most one alternative, recorded atomically with its queue entry so repeated checks and restarts cannot produce duplicates. Alternatives use the originating job's **current** filters, profiles and approval rules, restricted to the original media user and media type. Disabled jobs, pending-approval pauses and unwatched-content pauses defer the attempt. Removed jobs, changed ownership and users or media types removed from a job are skipped. Confirmed rejected titles remain in request history to avoid suggesting them again, but no longer block the unwatched-content gate. An admin's rejection does not automatically become personal dislike feedback.

Each check examines up to 50 tracked requests and attempts up to 10 replacements, respecting each job's maximum request count within that check. Discover and Trakt jobs search up to 100 candidates for a single alternative; no match is recorded as `exhausted` and is not retried. Generation failures are deferred to a later check. A replacement that is later explicitly declined can itself produce one alternative. The setting creates suggestions; Seerr/Sonarr/Radarr still control approval and downloading.

Admins can inspect recent decisions in the same settings card, or call `GET /api/automation/requests/replacements/log?limit=100` (maximum 500). `POST /api/automation/requests/replacements/run` runs the enabled check and returns counts for checked requests, queued alternatives, deferred attempts, exhausted searches, ignored decisions and errors. Both endpoints require an administrator; manual checks are limited to five per minute and return `409` if expiry or another replacement check is already running. Turning the setting off stops checks and new alternatives; existing queued suggestions retain their normal lifecycle.

## Simkl Integration

Simkl support is optional and works like Trakt: it adds each user's own watch history to recommendation jobs. A user can link Trakt and Simkl simultaneously; titles reported by both are merged rather than counted twice.

### What is stored

SuggestArr stores:

- An app-level Simkl AUTH V2 Client ID in Services. There is no client secret — the device flow does not use one.
- Per-media-user Simkl access and refresh tokens in the database.
- The linked Simkl username and status.
- A local cache of the account's watch history (see [Why Simkl history is cached](#why-simkl-history-is-cached)).

SuggestArr does not expose Simkl access tokens in API responses or frontend lists.

### Create a Simkl app

1. Open <https://simkl.com/settings/developer/>.
2. Create a new **AUTH V2** application and choose **TV, devices & command line** as the client type.
3. Copy the Client ID.
4. In SuggestArr, open Services > Simkl.
5. Paste the Client ID.
6. Save.

SuggestArr uses Simkl's RFC 8628 device flow, so it never needs a redirect URI or client secret. The private device code stays on the server; users only see the public code and approval URL.

### Link media-server users first

As with Trakt, Simkl links attach to a media-server profile. If a user has no linked media-server account, Profile > Simkl Account will ask them to link the media server first.

### Let users link Simkl

1. Log in as the user.
2. Open Profile.
3. Find Simkl Account.
4. Click Link Simkl.
5. SuggestArr shows a device code. Open its approval URL or enter the code at <https://simkl.com/pin> and approve access.
6. Wait for SuggestArr to show the linked Simkl username.

The PIN is valid for about fifteen minutes. **Cancel** abandons the attempt and clears the pending code on the server so it cannot be used later.

Admins can reach the same embedded profile area from Users.

### Verify with Recent Simkl Preview

1. Open Profile > Simkl Account.
2. Expand Recent Simkl Preview.

The first sync runs in the background after linking, so the panel may say it is still syncing before any titles appear. Once the sync completes, an empty panel means the account genuinely has no watch history.

If no items appear after the first sync:

- Confirm the Simkl account has watch history.
- Confirm the media-server account is linked.
- Confirm the Simkl Client ID is saved in Services.
- Check Logs for Simkl API errors.

### Use Simkl in jobs

Recommendation jobs have their own Simkl filters, independent of the Trakt ones:

- Use Simkl as Seed: titles marked *watching* or *completed* can seed recommendations.
- Exclude Simkl Watched: *completed* titles can be skipped. Titles still in progress are deliberately not skipped, so a show you are midway through can still produce suggestions.

Movies, TV, and anime are all read. Anime is treated as TV for recommendation purposes.

### Why Simkl history is cached

Simkl asks applications not to poll its history endpoints on a schedule and suspends client IDs that do, without warning. SuggestArr therefore checks a cheap activity-timestamp endpoint first and only re-reads history when that timestamp has actually moved, keeping a local cache in between. Jobs read the cache rather than the API, so total Simkl traffic is bounded by elapsed time rather than by how many jobs and users you have.

### Re-link required

Simkl access tokens are refreshed automatically from the stored AUTH V2 refresh token. If both tokens are rejected — for example because the app was removed at <https://simkl.com/settings/connected-apps/> — the account shows **Re-link required** and the user runs the device flow again.

If the Simkl **Client ID** itself is rejected, that is an install-wide problem rather than one user's, and SuggestArr shows it as a separate banner on the Simkl panel. It means the ID is wrong, the app was suspended, or it is over its request limit.

### Unlinking revokes access at Simkl

SuggestArr revokes AUTH V2 access when the refresh token is available, then deletes its local token and cached history. Legacy access-only links are removed locally and can be revoked manually at <https://simkl.com/settings/connected-apps/>.

## Cleanup Automation

Cleanup Automation removes old SuggestArr-originated requests and their media files when users did not mark the item as a favorite in the configured media server.

It is designed as a safety valve for automated requests:

1. SuggestArr creates requests through Seer.
2. Users have a grace period to watch or review the content.
3. If they want to keep it, they favorite it in Plex, Jellyfin, or Emby.
4. Cleanup checks old SuggestArr requests after the grace period.
5. Favorited items are kept.
6. Non-favorited items become deletion candidates.
7. In real mode, SuggestArr asks Seer to delete the media file.

Cleanup supports Plex, Jellyfin, and Emby.

### Where to configure

Open:

```text
Advanced > Cleanup Automation
```

Available settings:

- Enable cleanup automation: daily cleanup runs at 04:15 server time.
- Dry-run mode: logs what would be deleted without touching files.
- Grace period: number of days after request creation before an item is checked.
- Run now (dry-run): immediately preview cleanup actions.
- Run now (real): immediately perform deletion actions when cleanup is enabled.
- Audit log: shows cleanup actions, mode, rating, and reason.

### Safe setup

Recommended first setup:

1. Leave Dry-run mode enabled.
2. Set a conservative grace period, such as 14 or 30 days.
3. Click Run now (dry-run).
4. Review the audit log.
5. Keep dry-run for several scheduled cycles.
6. Disable dry-run only after you trust the candidate list.

Cleanup is destructive in real mode. It asks Seer to delete matching media files and removes the SuggestArr request row after Seer accepts the deletion request.

### How favorites are detected

Plex:

- Cleanup reads library items.
- Items with userRating `10` are treated as favorites and kept.

Jellyfin and Emby:

- Cleanup reads favorite items for selected users and libraries.
- Favorited movies and series are treated as keepers.

Items not found in the media library are logged as skipped because there is nothing local to delete.

### Cleanup audit actions

Common audit actions:

- `would_delete`: dry-run candidate that would be deleted in real mode.
- `deleted`: Seer accepted the file deletion request.
- `kept_favorited`: item is favorited and was kept.
- `skipped_not_in_library`: item was not found in the media library.
- `delete_failed`: Seer did not accept the deletion request.
- `error`: unexpected cleanup error for that item.

### Notes and limits

- Cleanup only considers requests tracked by SuggestArr.
- Cleanup does not run when disabled, except manual Run now can force a dry-run or real run.
- Cleanup requires Seer URL/token and a configured Plex, Jellyfin, or Emby server.
- Only admins can change cleanup settings or run cleanup manually.

## External Database

SQLite is default and best for most home installs. Use PostgreSQL or MySQL/MariaDB when you want stronger multi-process behavior, centralized backups, or larger deployments.

Set database values in Settings > Database, or in `config.yaml`.

PostgreSQL example:

```yaml
DB_TYPE: postgres
DB_HOST: postgres
DB_PORT: 5432
DB_USER: suggestarr
DB_PASSWORD: change-me
DB_NAME: suggestarr
```

MySQL/MariaDB example:

```yaml
DB_TYPE: mysql
DB_HOST: mariadb
DB_PORT: 3306
DB_USER: suggestarr
DB_PASSWORD: change-me
DB_NAME: suggestarr
```

If using Docker Compose, put database and SuggestArr on the same Compose network and use the database service name as host.

## Reverse Proxy

SuggestArr can run behind a reverse proxy. Recommended:

- Keep SuggestArr listening internally on port `5000`.
- Terminate HTTPS at the proxy.
- Forward `X-Forwarded-For`, `X-Forwarded-Proto`, and `Host`.
- Set `SUGGESTARR_ALLOWED_ORIGINS` if exposing the frontend from a different origin.
- Set `SUBPATH` only when hosting under a path such as `/suggestarr`.

Example environment:

```yaml
environment:
  - SUGGESTARR_PORT=5000
  - SUGGESTARR_ALLOWED_ORIGINS=https://suggestarr.example.com
```

Subpath example:

```yaml
environment:
  - SUBPATH=suggestarr
```

Then proxy:

```text
https://example.com/suggestarr
```

## Authentication

Authentication is enabled by default and should stay enabled.

Important options:

- `ALLOW_REGISTRATION=false`: default. Only admins create users.
- `REGISTRATION_DEFAULT_TABS=requests,jobs,profile`: pages a self-registered
  account can see. Profile is always included. Set it under **Users** when
  sign-ups are on.
- `AUTH_MODE=enabled`: normal login required.
- `AUTH_MODE=local_bypass`: trusted local networks can bypass login.
- `AUTH_MODE=trusted_header`: a reverse proxy authenticates users and passes
  the username in a header (see below).
- `SUGGESTARR_AUTH_DISABLED=true`: disables auth. Use only for isolated testing.
- `AUTH_TRUSTED_CIDRS`: trusted CIDR list for local bypass and trusted header.
- `AUTH_TRUSTED_PROXY_CIDRS`: comma-separated proxy IPs/CIDRs allowed to supply
  `X-Forwarded-For` for local bypass and anonymous rate limiting. Default: empty.
  Keep this separate from the networks whose clients may bypass login. Explicit
  empty or invalid trust lists grant no trust.

For `local_bypass` behind a reverse proxy, explicitly list every trusted proxy
hop, for example `AUTH_TRUSTED_PROXY_CIDRS=10.0.20.11/32`, and put the permitted
client networks in `AUTH_TRUSTED_CIDRS`. The proxy must overwrite incoming
forwarding headers or append the actual connecting client to `X-Forwarded-For`.
SuggestArr walks that chain from the nearest proxy to the first non-proxy client.
Missing/malformed chains and forwarded requests from unlisted peers cannot
bypass login. With no forwarding headers, direct LAN access still works.
Do not expose the backend directly or deploy an unlisted LAN proxy that omits
forwarding headers: the backend cannot distinguish it from a direct LAN client.

If the database cannot establish whether authentication accounts exist,
SuggestArr returns `503` rather than enabling setup. The login screen offers
a retry. Restore database availability before creating the first admin account.

Integration configuration, connectivity tests, service discovery and setup OAuth
endpoints require an administrator. Personal account linking remains available
to authenticated users against configured providers. Job and approval profile
lookups (`GET /api/seer/radarr-servers` and `/sonarr-servers`) use saved Seer
credentials only and reject query/body overrides. Their responses contain only
selection data, never upstream credentials or service addresses.

For Plex, Jellyfin/Emby and Seer, use a complete HTTP/HTTPS base URL without
embedded credentials, query strings or fragments. Reverse-proxy paths such as
`https://media.example/jellyfin` remain supported. Changing an existing base URL
requires an explicit token in saves/imports: a redacted `***` token cannot carry
the old credential to a new destination. Replacing the Seer destination or API
token clears its saved session. Invalid existing bases must be corrected manually.

These integration requests do not follow redirects. Configure their final URL,
including the correct HTTP/HTTPS scheme. LAN, localhost and Docker destinations
remain supported for configured integrations. Public-only destinations, including
external profile images and webhooks without `allow_private`, reject non-global
addresses (including CGNAT), 6to4, Teredo and standard NAT64 prefixes. The HTTP
connector validates the addresses it actually uses, including after DNS changes;
TLS certificate validation and the original hostname remain enabled. Private
webhooks still require explicit `allow_private` and the existing destination
allowlist; delivery signatures, queueing and retry behavior remain unchanged.

Do not expose SuggestArr publicly with authentication disabled or local bypass enabled unless a separate trusted authentication layer protects it.

### Trusted header (reverse proxy / SSO)

If you already run single sign-on in front of SuggestArr — Authelia, Authentik,
oauth2-proxy, Traefik forward-auth — `AUTH_MODE=trusted_header` lets those users
in with the identity the proxy has already established, so nobody needs a second
password. Each person still gets their own account, their own requests and their
own role; only the password step is gone.

- `AUTH_TRUSTED_HEADER`: header carrying the username. Default
  `X-Forwarded-User`; Authelia and Authentik's proxy outpost commonly use
  `Remote-User`.
- `AUTH_TRUSTED_HEADER_AUTO_CREATE`: default `true`. The first request for an
  unknown username creates a local account with `role=user`. Set it to `false`
  to allow only accounts an admin created beforehand.
- `AUTH_TRUSTED_CIDRS`: **set this to your proxy's address.** The header is only
  believed when the request comes from one of these ranges.

> **Set `AUTH_TRUSTED_CIDRS` as narrowly as you can.** The header is trusted
> input: anyone who can reach SuggestArr directly from an address inside those
> ranges can pick any identity by setting it themselves. The defaults cover
> whole private networks, which is convenient for `local_bypass` but too wide
> here — ideally list only the proxy, e.g. `AUTH_TRUSTED_CIDRS=10.0.20.11/32`.
>
> Since 3.2.0, while `AUTH_TRUSTED_CIDRS` is left at those defaults,
> `trusted_header` only believes the header from localhost and logs a warning
> at the first request. If your proxy runs elsewhere (another container or
> host), set its address or sign-in through the proxy will fail; password
> sign-in keeps working.

All of these can be set in **Settings → Advanced → Access & routing** by
choosing *Sign In Through Reverse Proxy (SSO)*; the environment variables
below still work and take precedence.

Accounts created this way get a random, unusable password hash: they exist to
carry an identity, and nobody can log into them with a password. Promote a user
to admin through the normal user-management screen.

Example (Caddy in front, proxy at `10.0.20.11`, Authentik setting `Remote-User`):

```yaml
environment:
  - AUTH_MODE=trusted_header
  - AUTH_TRUSTED_HEADER=Remote-User
  - AUTH_TRUSTED_CIDRS=10.0.20.11/32
```

## Unraid

Use the Community Applications template or create a container manually:

- Repository: `ciuse99/suggestarr:latest`
- Web UI port: `5000`
- Container path: `/app/config/config_files`
- Host path: `/mnt/user/appdata/suggestarr`
- Recommended network: host or bridge, depending on your media stack.

Open:

```text
http://<unraid-ip>:5000
```

If changing the Web UI port, keep `SUGGESTARR_PORT` and the mapped port aligned.

## Source Install

Source install is useful for development. Docker is better for normal deployment.

### Windows PowerShell

From repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r api_service\requirements.txt

cd client
npm ci
npm run build
cd ..

New-Item -ItemType Directory -Force static
Copy-Item -Path client\dist\* -Destination static -Recurse -Force

$env:SUGGESTARR_PORT = "5000"
python -m api_service.app
```

Open:

```text
http://localhost:5000
```

### Linux or macOS

From repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r api_service/requirements.txt

cd client
npm ci
npm run build
cd ..

mkdir -p static
cp -R client/dist/* static/

export SUGGESTARR_PORT=5000
python -m api_service.app
```

Open:

```text
http://localhost:5000
```

## Updating

Docker Compose:

```bash
docker compose pull
docker compose up -d
```

Then check logs:

```bash
docker logs -f suggestarr
```

Source install:

```bash
git pull
python -m pip install -r api_service/requirements.txt
cd client
npm ci
npm run build
cd ..
cp -R client/dist/* static/
python -m api_service.app
```

On Windows, use the PowerShell copy command from the source install section.

## Backup and Restore

SuggestArr has two backup methods:

- UI backup with Export/Import JSON. Best for moving configuration to a new instance.
- Filesystem backup of `config_files`. Best for full disaster recovery, especially with SQLite.

### UI Export and Import

In the footer of the web interface, admins can use:

- `Export`: downloads a configuration snapshot as a JSON file.
- `Import`: restores a configuration snapshot from a previously exported JSON file.

Use this when you want to start a new SuggestArr instance and restore the same configuration without manually entering every value again.

The Dashboard uses `GET /api/config/export` and `POST /api/config/import`. This is the **canonical** backup path and restores integrations, settings, and per-user Trakt and Simkl data.

#### What is included

Each export contains:

- `integrations`: service credentials from the database (URLs, API keys, tokens, and similar fields).
- `settings`: non-integration configuration from `config.yaml` (filters, scheduling, feature flags, and similar values).
- `media_users`: media-server user identities and per-user Trakt and Simkl link metadata (username, status, source settings).

Trakt app credentials remain under `integrations.trakt` and the Simkl Client ID under `integrations.simkl`. Per-user tokens are stored under `media_users[].trakt.oauth_tokens` and `media_users[].simkl.oauth_tokens`. A user linked to only one of the two still round-trips that link.

The cached Simkl watch history is deliberately left out. It is derived data that the next sync rebuilds, and including it would bloat every snapshot for no gain.

Config schema version is `2`. Older exports without `media_users` still import normally.

#### Safe export vs full backup

By default, exports are **safe for troubleshooting**:

- Secret fields are redacted as `***` (API keys, tokens, passwords, Trakt `client_secret`, and similar values). Simkl access and refresh tokens are both redacted.
- When OAuth tokens exist, `oauth_tokens` is still present but redacted:

```json
"oauth_tokens": {
  "access_token": "***",
  "refresh_token": "***",
  "expires_at": null
}
```

To download a **fully restorable backup**, check **Include all secrets (full backup)** in the export dialog. This sends `include_secrets=true` and includes live credentials plus Trakt and Simkl tokens. SuggestArr shows a warning when secrets are included.

Treat full backups like password files. Do not attach them to GitHub issues, Discord, or other public channels.

#### Import behavior

Import merges the snapshot into the running instance:

- Redacted `***` values do **not** overwrite existing secrets.
- If you import a safe export on a fresh instance, service credentials and Trakt and Simkl tokens must be re-entered or re-linked.
- If you import a safe export on an instance that already has credentials, existing secrets are preserved.
- A full backup import restores credentials and Trakt and Simkl tokens without re-linking.

After importing a safe export, links may still show as connected in metadata, but Trakt and Simkl features will not work until each user links again unless the import included live tokens.

#### Recommended flow

1. Open the old SuggestArr instance.
2. Click `Export` in the footer.
3. For disaster recovery, enable **Include all secrets (full backup)**. For troubleshooting or sharing config structure, leave it unchecked.
4. Save the downloaded JSON file somewhere safe.
5. Start the new SuggestArr instance.
6. Complete initial admin setup if required.
7. Click `Import` in the footer.
8. Select the exported JSON file.
9. Review services, database, jobs, and advanced settings.
10. Re-link Trakt and Simkl accounts if you imported a safe export without tokens.
11. Save or restart the container if needed.

#### API note

`GET /api/admin/export-config` is a separate, older endpoint. It exports integrations and settings only and does **not** include `media_users` or restore them on import. Use the Dashboard export/import flow (or `/api/config/export` directly) when Trakt or Simkl user links must move with the instance.

### Filesystem Backup

Back up the full persistent config folder:

```text
config_files/
```

For Docker Compose, stop the container before copying for the cleanest SQLite backup:

```bash
docker compose down
cp -R config_files config_files.backup
docker compose up -d
```

Restore by replacing `config_files` with your backup and starting SuggestArr again.

If using PostgreSQL or MySQL, also back up the external database with its native dump tool.

## Troubleshooting

### Web UI does not open

Check container:

```bash
docker ps
docker logs suggestarr
```

Confirm port mapping:

```yaml
ports:
  - "5000:5000"
```

### Seer or media server cannot connect

Do not use `localhost` for services outside the SuggestArr container. Use:

- Docker service name when in same Compose stack.
- Host LAN IP when service runs on host.
- Real hostname when service runs elsewhere.

### Login loop after restart

Make sure `config_files/secret.key` persists. If the key changes, active sessions become invalid and users must log in again.

### Profile pictures

SuggestArr uses the avatar of your assigned Seer account when available, then tries your verified linked account on the selected Plex, Jellyfin or Emby server. Link your media account under **My profile**; an administrator can assign your Seer account under **Users**. Accounts are matched by their linked IDs, never by username. Images are fetched through the authenticated SuggestArr backend, keeping service credentials out of the browser.

If no image is available or a service is offline, a local cinema/TV avatar is assigned automatically. Its symbol and theme colours stay consistent for your account across sessions and username changes. No external avatar service or image upload is required.

The same avatar component and image resolver are used in the sidebar, Profile and the Users account cards. Assigning a different media account or Seer identity refreshes that user's photo. The authenticated `/api/users/<id>/avatar` endpoint allows users to fetch their own image and administrators to fetch other users' images; `/api/auth/me/avatar` remains available for the current user.

### Configuration resets after update

Your volume is probably wrong. The host folder must map to:

```text
/app/config/config_files
```

### AI provider fails

Check:

- Base URL includes `/v1` for OpenAI-compatible local providers.
- Model exists and is pulled if using Ollama.
- Container can reach provider URL.
- API key is valid when provider requires one.

### Optional SearXNG web context

Set **SearXNG Base URL** in Advanced Settings to the base address of a self-hosted SearXNG instance (for example `http://searxng:8080`). SuggestArr calls its `/search?format=json` endpoint and provides at most three results as untrusted context to AI Search and AI recommendations. Leave it blank to keep the existing offline/LLM-only behavior. A failed or slow SearXNG request is ignored after five seconds.

### Need more logs

Temporarily set:

```yaml
environment:
  - LOG_LEVEL=DEBUG
```

Restart, reproduce issue, then return to `INFO`.
