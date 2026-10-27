# SuggestArr Feature Guide

Detailed behaviour of SuggestArr features. For setup, see the [Installation Guide](INSTALLATION.md).

- [Request approval workflow](#request-approval-workflow)
- [Using a specific Seer user for requests](#using-a-specific-seer-user-for-requests)
- [Public list import](#public-list-import)
- [Trakt watch history](#trakt-watch-history-integration)
- [Job pause and cleanup automation](#job-pause-and-cleanup-automation)
- [AI-powered recommendations](#ai-powered-recommendations)
- [AI Search](#ai-search)

## Request approval workflow

New jobs follow the global **Approve requests before sending them to Seer** setting,
disabled by default under **Advanced**. Each job can inherit that setting or override
it to always approve or always send automatically. Held results appear on the
Requests page, where the job owner or an administrator can send them to Seer,
reject them, or blacklist them globally.

The global Request Workflow settings can also pause a job while its SuggestArr
suggestions await review and automatically reject suggestions left pending for a
configured number of days. The pause behavior can be overridden per job.

## Using a Specific Seer User for Requests
If you'd like to use a specific Seer user to make media requests, follow these steps:

1. In the web interface, enable the user selection option by checking the corresponding box.
2. Select the desired user from the dropdown list.
3. Enter the password for the selected user.
4. The system will now use this user to make media requests, rather than using the admin or default profile.

Password-based selection supports local Seer users. For Jellyfin/Emby recommendation jobs,
**Mapped Seer user (fallback to technical)** matches the user whose watch history is being
processed to Seerr's `jellyfinUserId`, then submits with the configured API key and that
user's Seerr ID. This also supports Jellyfin-authenticated Seerr accounts without a local
password. If no match can be resolved, the configured technical Seer identity is used.

## Public List Import

Create an **Import list** job in Jobs to request missing titles from one public
MDBList or Trakt list. In **Connections**, configure an MDBList API key (from
[MDBList Preferences](https://mdblist.com/preferences/)) or the shared Trakt
Client ID. Public Trakt lists do not require a linked personal Trakt account.

Use **Test connection** on the MDBList card to validate the API key without a list.
Connections automatically rechecks saved MDBList credentials when reopened, including
after restarting the browser. Editing the key clears its previous connection status.

For a single import, choose **Import list once** on the Jobs page. It processes the
entire public list in the background without creating a job or schedule, using
your chosen media types, quality filters, delivery mode and Seer identity. Existing
library titles, requests and queued items are skipped. Progress stays visible in
Jobs after navigating away or closing the browser; it counts titles checked and
new requests queued, not completed downloads. Only one import runs per user at a
time. Use **Resume import** after a provider error or server interruption. Only
your latest one-time import is retained; creating a new one replaces that progress.
After a server restart, resume becomes available when the previous worker lease
expires (up to 10 minutes).

**Preview list** is available before saving a job or starting a one-time import.
It checks up to 100 list entries at a time without creating requests; use
**Load more titles** to inspect the next page. The import rechecks availability
before enqueueing, so titles acquired since the preview are still excluded.

Use `https://mdblist.com/lists/username/list-name` or
`https://trakt.tv/users/username/lists/list-name`, then **Verify list**. Private
lists, watchlists, seasons, episodes, people and entries without a valid TMDb ID
are not supported. Select movies, shows or both, quality filters, schedule,
delivery mode and request profiles. **Mapped Seer user** credits the job owner,
with the existing fallback to the configured technical user.

The first run includes existing list entries. Each run follows list order and
creates up to **20 new requests by default**, skipping titles already requested,
queued, blocked by feedback or present in the library. Manual approval and rolling
job limits still apply. Lists are read in pages of 100, scanning at most 1,000
entries per run. A persistent cursor resumes the next run and returns to the
beginning at the end, so later cycles reconsider changed lists. Changing source,
media type or filters restarts the scan. List order changes may defer an entry
until the next cycle; queue duplicate guards prevent duplicate requests.

Preview uses the current cursor without advancing it or creating requests.
Provider failures preserve requests already queued; subsequent runs resume safely.
Removing an entry from a list never removes a Seer request or library content.
If rejected-request replacement is enabled, alternatives come from the same list
with the current filters and original request's media type.

## Trakt Watch History Integration

SuggestArr can enrich recommendations with each user's own Trakt watch history. Trakt is optional: media-server history still works without it.

### What Trakt adds

- Recent Trakt watches can be used as recommendation seeds.
- Titles rated on Trakt (in the Trakt app, the site, or synced in from streaming services) steer recommendations as liked or disliked seeds; a rating set in SuggestArr wins. Toggle it per job with **Use Trakt ratings**.
- Fully watched Trakt items can be added to the skip-watched set.
- Each SuggestArr user links their own Trakt account from their profile.
- Admins configure only the shared Trakt app credentials.
- A collapsible **Recent Trakt Preview** panel shows the latest items fetched from Trakt when opened.

### How to enable

1. Create a Trakt app at <https://developer.trakt.tv/apps/new> (sign in with GitHub): set any **App name**, enter `urn:ietf:wg:oauth:2.0:oob` in **Redirect URIs**, leave **Allowed origins** empty, then click **Create app**.
2. In SuggestArr, go to **Services -> Trakt**.
3. Enter the Trakt **Client ID**, then save. New Trakt apps no longer receive a Client Secret; existing apps may keep their secret configured.
4. Each user goes to **Profile -> Trakt Account** and clicks **Link Trakt**.
5. Enter the Trakt device code shown by SuggestArr at the Trakt activation URL.
6. Open **Recent Trakt Preview** to verify the latest Trakt history is being read.

For admins, the same profile panel is available under **Users**. Trakt links are tied to the user's linked Plex, Jellyfin, or Emby media profile, so users should link their media-server account first.

SuggestArr uses Trakt's device-code flow and sends `urn:ietf:wg:oauth:2.0:oob` as the redirect URI when refreshing tokens. Trakt shows an **Insecure redirect URIs** warning for it, but the form accepts it; no HTTPS callback is needed.

## Job Pause and Cleanup Automation

SuggestArr includes safety tools for running automation without flooding Seer or keeping unwanted media forever.

### Pause jobs while Seer has pending requests

Each job has a **Pause while Seer requests are pending** option in its schedule settings.

When enabled, SuggestArr checks Seer before running that job. If Seer has requests still awaiting approval or denial, the job is skipped and logged as paused/skipped. This applies to scheduled runs, single job runs, and force-run-all.

Recommendation and Trakt Recommendation jobs can also enable **Pause if suggestions remain unwatched**. Movie and TV activity is tracked separately per linked media user. Watching a requested movie or one episode of a requested show starts a fresh cycle; only scheduled runs are paused.

Use this when Seer approvals are part of your workflow and you want new automation runs to wait until the previous batch has been reviewed.

### Auto-decline pending Seerr requests

Under **Approvals -> Seerr pending requests**, set **Auto-decline after (days)** to expire requests still waiting for approval in Seerr. `0` disables the feature; preview-only mode is enabled by default. Runs happen daily at 04:30 server time, or manually from the same page, which also shows the audit log.

Only new requests delivered by SuggestArr after upgrading can be tracked, including deliveries made while expiry is disabled. Existing requests are excluded. Age starts at creation in Seerr. Approved requests and media files are untouched; SuggestArr keeps its history and duplicate guards. The Seerr API key needs `MANAGE_REQUESTS` or `ADMIN` permissions for real declines.

### Cleanup Automation

Cleanup Automation is available under **Advanced -> Cleanup Automation**.

It looks at requests created by SuggestArr, waits for the configured grace period, checks whether the item is favorited in Plex, Jellyfin, or Emby, and then:

- keeps favorited items
- skips items no longer present in the media library
- logs what would be deleted in dry-run mode
- asks Seer to delete matching media files when real mode is enabled

Cleanup is off by default and starts safely in dry-run mode. Always run dry-run first and review the audit log before enabling real deletions.

## AI-Powered Recommendations

SuggestArr includes an optional AI recommendation engine that analyzes your watch history and suggests titles that match your taste, with a short explanation for each pick.

Recent watches are treated as neutral viewing context, not automatic proof that a user liked them. When TMDb metadata is available, the AI also receives each item's media type and genres.

The engine works with **any OpenAI-compatible API**, so you can use a cloud provider or a local model running on your own machine.

### How to enable

1. Open the web interface and go to **Settings → Advanced**.
2. Fill in the **AI Provider Configuration** fields (click the **ⓘ** button next to the section title for an in-app guide).
3. Check **Use AI suggestion algorithm**.
4. Save. The AI engine will be used automatically on the next automation run.

> If the LLM is unavailable or returns no results, SuggestArr falls back to the standard TMDb-based recommendation algorithm transparently.

### Supported providers

| Provider | API Key | Base URL | Example model |
|---|---|---|---|
| **OpenAI** | Required (`sk-proj-...`) | *(leave blank)* | `gpt-4o-mini` |
| **Ollama** (local) | Not required | `http://localhost:11434/v1` | `mistral`, `llama3` |
| **OpenRouter** | Required (`sk-or-v1-...`) | `https://openrouter.ai/api/v1` | `meta-llama/llama-3-8b-instruct` |
| **OrcaRouter** | Required (`sk-orca-...`) | `https://api.orcarouter.ai/v1` | `openai/gpt-5.5` |
| **LiteLLM Proxy** | Depends on config | `http://<your-proxy>:4000` | Depends on config |

**Note for Ollama users:** make sure Ollama is running and the model is pulled (`ollama pull mistral`) before saving. The API Key field can be left blank — SuggestArr will use a placeholder automatically.

### Generation settings

The **Temperature** field defaults to `legacy`, preserving the existing values: `0.7` for scheduled recommendations and `0.8` for AI Search. Clear the field and save to omit `temperature` from LLM requests, which is useful for models that reject it; enter a value from `0` to `2` to override both flows.

**Reasoning effort** is optional (`low`, `medium`, or `high`) and is sent only for direct OpenAI GPT-5 and o-series models. It is provider/model dependent, so other OpenAI-compatible endpoints leave it out.

### Docker Compose with Ollama

See the Ollama example in the [Installation Guide](INSTALLATION.md#ai-recommendations-and-ai-search).

## AI Search

SuggestArr includes an **AI Search** tab in the dashboard that lets you find movies and TV shows using plain text, no browsing required.

### How it works

Type a natural-language description of what you feel like watching. The LLM interprets your query (genres, era, language, rating threshold, mood…) and translates it into structured TMDB filters. Results are ranked and enriched with an AI-generated rationale explaining why each title was picked for you.

**Examples of queries you can use:**
- *"A psychological thriller from the 90s with a twist ending"*
- *"Feel-good anime with strong friendships"*
- *"80s sci-fi movies with practical effects"*
- *"A dark comedy series like Breaking Bad"*

### Key capabilities

- **Search starters** — choose a mood or a title from your linked Plex/Jellyfin/Emby viewing history to prepare an editable query. Titles added to your watch history in Profile are also included. Missing posters use a placeholder, and an unavailable history service never blocks searching.
- **Recent searches** — revisit up to five successful searches, saved per SuggestArr account in the current browser. Starters and recent searches fill the input; press **Search** when ready. These sections give way to results, with **Explore search ideas** to bring them back.
- **Natural language queries** — describe mood, genre, decade, language, or specific themes
- **Viewing-history personalisation** — the AI tailors results based on what you (or your users) have already watched
- **Exclude already-watched titles** — hide content you've already seen
- **One-click requesting** — send results directly to Seer without leaving the page
- **Query interpretation badge** — see how the AI parsed your query (genres, year range, language, min rating)

### How to enable

AI Search requires an LLM to be configured (same setup as AI-Powered Recommendations):

1. Open the web interface → **Settings → Advanced**.
2. Fill in the **AI Provider Configuration** fields (API key, base URL, model).
3. Save. The **AI Search** tab will become active in the dashboard.

> AI Search is independent of the automated recommendations run — it is triggered manually from the dashboard and does not affect cron-based automation.

