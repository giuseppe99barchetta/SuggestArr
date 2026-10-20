<div align="center">

## 🚀 SuggestArr - Media Automation Made Simple

![ezgif com-optimize (2)](https://github.com/user-attachments/assets/d5c48bdb-3c11-4f35-bb55-849297d521e7)

![Build Status](https://img.shields.io/github/actions/workflow/status/giuseppe99barchetta/suggestarr/docker_hub_build.yml?branch=main&label=Build&logo=github)
![Platform Support](https://img.shields.io/badge/platforms-linux%2Famd64%20|%20linux%2Farm64-blue?logo=linux)
![Docker Pulls](https://img.shields.io/docker/pulls/ciuse99/suggestarr?label=Docker%20Pulls&logo=docker)
[![Buy Me a Coffee](https://img.shields.io/badge/Donate-Buy%20Me%20a%20Coffee-orange?logo=buy-me-a-coffee)](https://buymeacoffee.com/suggestarr)
[![](https://dcbadge.limes.pink/api/server/https://discord.com/invite/JXwFd3PnXY?style=flat)](https://discord.com/invite/JXwFd3PnXY)
</div>

SuggestArr is a project designed to automate media content recommendations and download requests based on user activity in media servers like **Jellyfin**, **Plex**, and now **Emby**. It retrieves recently watched content, searches for similar titles using the TMDb API, and sends automated download requests to **Seer**.

New jobs follow the global **Approve requests before sending them to Seer** setting,
disabled by default under **Advanced**. Each job can inherit that setting or override
it to always approve or always send automatically. Held results appear on the
Requests page, where the job owner or an administrator can send them to Seer,
reject them, or blacklist them globally.

The global Request Workflow settings can also pause a job while its SuggestArr
suggestions await review and automatically reject suggestions left pending for a
configured number of days. The pause behavior can be overridden per job.

## Features
- **Multi-Media Server Support**: Supports Jellyfin, Plex, and Emby for retrieving media content.
- **TMDb Integration**: Searches for similar movies and TV shows on TMDb.
- **AI-Powered Recommendations**: Uses any OpenAI-compatible LLM (OpenAI, Ollama, Gemini, LiteLLM…) to generate hyper-personalized suggestions based on watch history, complete with AI reasoning for each pick.
- **AI Search**: Describe in natural language what you want to watch and let the AI find matching titles, personalised to your viewing history, with one-click request to Seer.
- **Trakt Watch History**: Let each user link their own Trakt account. SuggestArr can use Trakt recent watches as recommendation seeds and skip content already watched on Trakt.
- **Imported Watch History**: Add CSV or manually searched TMDb titles with optional 0–10 ratings to personalise recommendations even after media has been removed from a server. See [the import format](docs/WATCH_HISTORY_IMPORT.md).
- **Automated Requests**: Sends download requests for recommended content to Seer.
- **Pending-Request Job Pause**: Skip scheduled or manual jobs while Seer still has requests waiting for approval or denial.
- **Unwatched-Suggestion Pause**: Optionally pause scheduled recommendation jobs when a user has not watched a SuggestArr request within a configurable number of days; manual runs remain available.
- **Cleanup Automation**: Optionally prune old SuggestArr-originated requests and files when users never favorite them in Plex, Jellyfin, or Emby.
- **Web Interface**: A user-friendly interface for configuration and management.
- **Real-Time Logs**: View and filter logs in real time (e.g., `INFO`, `ERROR`, `DEBUG`).
- **User Selection**: Choose specific users to initiate requests, allowing management and approval of auto-requested content.
- **Per-User Request Visibility**: Filter requests by media-server account, or let administrators limit regular users to requests for their linked Plex, Jellyfin, or Emby account.
- **Cron Job Management**: Update the cron job schedule directly from the web interface.
- **Configuration Pre-testing**: Automatically validates API keys and URLs during setup.
- **Content Filtering**: Exclude requests for content already available on streaming platforms in your country.
- **External Database Support**: Use external databases (PostgreSQL, MySQL) in addition to SQLite for improved scalability and performance.

## Prerequisites
- **Python 3.x** or **Docker**
- **[TMDb API Key](https://www.themoviedb.org/documentation/api)**
- Configured **[Jellyfin](https://jellyfin.org/)**, **[Plex](https://www.plex.tv/)**, or **[Emby](https://emby.media/)**
- Configured **[Seer](https://github.com/seerr-team/seerr)**
- (Optional) External database (PostgreSQL or MySQL) for improved performance
- (Optional) **[Trakt application](https://developer.trakt.tv/apps/new)** for per-user Trakt watch-history integration

## Docker Usage

You can run the project using Docker Compose for easy setup and execution.
Images are also available from GitHub Container Registry as `ghcr.io/giuseppe99barchetta/suggestarr:latest`.

### Docker Compose Example

```yaml
services:
  suggestarr:
    image: ciuse99/suggestarr:latest
    container_name: SuggestArr
    restart: always
    ports:
      - "${SUGGESTARR_PORT:-5000}:${SUGGESTARR_PORT:-5000}"
    volumes:
      - ./config_files:/app/config/config_files
    environment:
      # Optional: Only needed if something goes wrong and you need to inspect deeper
      - LOG_LEVEL=${LOG_LEVEL:-info}
      # Optional: Customize the port (defaults to 5000 if not set)
      - SUGGESTARR_PORT=${SUGGESTARR_PORT:-5000}
```
To start the container with Docker Compose:

```bash
docker-compose up
```

## Web Interface

Access the web interface at: http://localhost:5000 (or your custom port if configured with SUGGESTARR_PORT). Use this interface to configure the application, select your media service, and manage cron schedules.

Make sure your environment is set up correctly and that the application is running to access the web interface.

### Using a Specific Seer User for Requests
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

### Docker Compose with Ollama (example)

```yaml
services:
  suggestarr:
    image: ciuse99/suggestarr:latest
    container_name: SuggestArr
    restart: always
    ports:
      - "5000:5000"
    volumes:
      - ./config_files:/app/config/config_files

  ollama:
    image: ollama/ollama
    container_name: ollama
    restart: always
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  ollama_data:
```

After starting both containers, pull your preferred model:

```bash
docker exec -it ollama ollama pull mistral
```

Then in SuggestArr Advanced settings set:
- **Base URL** → `http://ollama:11434/v1`
- **Model** → `mistral`
- **API Key** → *(leave blank)*

---

## 🔍 AI Search

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

---

## Installation
For Docker, Unraid, source install, reverse proxy, backup, and recommended configuration instructions, see the [Installation Guide](/docs/INSTALLATION.md).

## Public API and Swagger

External integrations use the stable public API at `/api/v1`; dashboard
endpoints under `/api/*` are internal. The interactive Swagger UI is served by
the backend at `http://localhost:5000/docs` (or
`http://localhost:5000/<SUBPATH>/docs` when `SUBPATH` is configured). The
OpenAPI document is also available as
`/api/v1/openapi.json` and `/api/v1/openapi.yaml`.

See the [Public API v1 guide](/docs/API.md) for authentication, addresses, and
usage details.

## Support SuggestArr ❤️

Celebrate your discoveries with milestone badges and a shareable recap in Home. Recaps include your recorded title count, movie/TV breakdown and a fan of your top-rated requested titles, rendered locally in your browser. Share shortcuts put Reddit first, alongside Discord, X and Bluesky; cover artwork can be hidden before sharing. Administrators can manage occasional support invitations in **My profile → Support reminders**. See [Your SuggestArr journey](docs/RECAP.md) for counting rules, privacy and reminder preferences.

**Year recap**, shown in Home from December 15 through January 31, turns recorded annual requests into seven downloadable stories, with monthly discoveries, genres and recent covers. January opens the year just completed. Load available Plex/Jellyfin watch activity explicitly; partial history is labelled, and unavailable watch hours are never estimated from runtime. A separate 2026 sample-data mode remains available within the seasonal recap to preview the complete visual experience.
If you enjoy SuggestArr, consider making a donation to support its continued development and help keep the project running at its best:

- ☕ [Ko-fi](https://ko-fi.com/ciuse99)
- 💛 [Buy Me a Coffee](https://buymeacoffee.com/suggestarr)

Every contribution, no matter the size, is greatly appreciated. Thank you for supporting SuggestArr!

## Join Our Discord Community
Feel free to join our Discord community to share ideas, ask questions, or get help with SuggestArr: [Join here](https://discord.gg/JXwFd3PnXY).

## Contribute
Contributions are highly welcome! Feel free to open issues, submit pull requests, or provide any feedback that can improve the project. Whether you're fixing bugs, improving documentation, or adding new features, all contributions are greatly appreciated.

## License
This project is licensed under the MIT License.

