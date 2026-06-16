# SuggestArr Installation Guide

SuggestArr is a self-hosted web app that reads watch activity from Plex, Jellyfin, or Emby, finds recommendations through TMDb, and sends requests to Seer. The recommended installation method is Docker Compose because it keeps the Python backend, built Vue frontend, dependencies, scheduler, and persistent data in one predictable container.

## Requirements

Before installing, prepare:

- Docker and Docker Compose, or Python 3.13 and Node.js 22 for a source install.
- A TMDb API key from <https://www.themoviedb.org/settings/api>.
- One media server: Plex, Jellyfin, or Emby.
- A running Seer instance, such as Jellyseerr or Overseerr-compatible Seer.
- Network access from SuggestArr to TMDb, your media server, and Seer.
- Optional: OMDb API key for IMDb-based filters.
- Optional: OpenAI-compatible LLM provider for AI recommendations and AI Search.
- Optional: Trakt OAuth app credentials for per-user Trakt watch-history integration.

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
8. Optional: add Trakt Client ID and Client Secret in Services > Trakt.
9. Save configuration.
10. Have each user link their media-server account from Profile.
11. Optional: have each user link their Trakt account from Profile > Trakt Account.
12. Create or adjust jobs from the Jobs page. 

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

Use this page to configure TMDb, optional OMDb, your media server, Trakt app credentials, and Seer.

For Trakt, Services stores only the shared app-level OAuth credentials. Individual Trakt accounts are linked by each user from their Profile page.

![SuggestArr services configuration](docs/assets/suggestarr-config-services.png)

### Users and Profile

Use this page to manage local accounts, assign media-server accounts, and link personal Trakt accounts.

- Admins use Users to create accounts, control permissions, and assign media accounts.
- Each user uses Profile to link their own Plex, Jellyfin, or Emby account.
- After the media account is linked, the user can link their own Trakt account from Profile > Trakt Account.
- Opening Recent Trakt Preview automatically fetches recent Trakt items and shows a loading icon while it loads.

### Jobs

Use this page to create, preview, run, enable, or disable automated recommendation and discovery jobs.

Jobs can also pause automatically while Seer has pending requests awaiting approval or denial.

![SuggestArr jobs configuration](docs/assets/suggestarr-config-jobs.png)

### Database

SQLite is the recommended default. PostgreSQL, MySQL, and MariaDB are available for larger or more advanced deployments.

![SuggestArr database configuration](docs/assets/suggestarr-config-database.png)

### Advanced

Use this page for beta features, AI provider setup, logging, caching, API timeouts, reverse-proxy subpath, registration, authentication, and Cleanup Automation.

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
- Use filters per job: genre, language, rating, runtime, provider exclusions.
- Run a dry run first.
- Check results in Seer before enabling full automation.
- Enable Pause while Seer requests are pending if Seer approvals are part of your flow.
- Use lower result counts for frequent jobs.

Example schedule choices:

```text
daily
every_12h
0 3 * * *
```

Use standard cron only if presets are not enough.

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

AI features are optional beta features. They work with OpenAI-compatible APIs.

Enable:

1. Go to Settings > Advanced.
2. Enable beta features.
3. Configure AI provider.
4. Enable advanced suggestion algorithm if you want automated AI recommendations.

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

- App-level Trakt Client ID and Client Secret in Services.
- Per-media-user Trakt OAuth tokens in the database.
- The linked Trakt username and status.

SuggestArr does not expose Trakt access tokens in API responses or frontend lists.

Configuration export (Dashboard **Export**) can include Trakt link metadata and source settings by default. OAuth tokens are redacted unless you choose a full backup. See [UI Export and Import](#ui-export-and-import).

### Create a Trakt OAuth app

1. Open <https://trakt.tv/oauth/applications>.
2. Create a new application.
3. Copy the Client ID and Client Secret.
4. In SuggestArr, open Services > Trakt.
5. Paste Client ID and Client Secret.
6. Save.

Device-code OAuth is used for user linking, so users do not need to paste Trakt passwords or tokens into SuggestArr.

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
- Confirm Trakt Client ID and Secret are saved in Services.
- Check Logs for Trakt API errors.

### Use Trakt in jobs

Recommendation jobs can use linked Trakt accounts:

- Use Trakt as Seed: recent Trakt watches can seed recommendations.
- Exclude Trakt Watched: watched Trakt items can be skipped.

If no linked Trakt accounts exist, job filters will warn that Trakt is not usable yet. Media-server history still works without Trakt.

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
- `AUTH_MODE=enabled`: normal login required.
- `AUTH_MODE=local_bypass`: trusted local networks can bypass login.
- `SUGGESTARR_AUTH_DISABLED=true`: disables auth. Use only for isolated testing.
- `AUTH_TRUSTED_CIDRS`: trusted CIDR list for local bypass.

Do not expose SuggestArr publicly with authentication disabled or local bypass enabled unless a separate trusted authentication layer protects it.

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
npm install
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
npm install
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
npm install
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

The Dashboard uses `GET /api/config/export` and `POST /api/config/import`. This is the **canonical** backup path and restores integrations, settings, and per-user Trakt data.

#### What is included

Each export contains:

- `integrations`: service credentials from the database (URLs, API keys, tokens, and similar fields).
- `settings`: non-integration configuration from `config.yaml` (filters, scheduling, feature flags, and similar values).
- `media_users`: media-server user identities and per-user Trakt link metadata (username, status, source settings).

Trakt app credentials remain under `integrations.trakt`. Per-user OAuth tokens are stored under `media_users[].trakt.oauth_tokens`.

Config schema version is `2`. Older exports without `media_users` still import normally.

#### Safe export vs full backup

By default, exports are **safe for troubleshooting**:

- Secret fields are redacted as `***` (API keys, tokens, passwords, Trakt `client_secret`, and similar values).
- When OAuth tokens exist, `oauth_tokens` is still present but redacted:

```json
"oauth_tokens": {
  "access_token": "***",
  "refresh_token": "***",
  "expires_at": null
}
```

To download a **fully restorable backup**, check **Include all secrets (full backup)** in the export dialog. This sends `include_secrets=true` and includes live credentials plus Trakt OAuth tokens. SuggestArr shows a warning when secrets are included.

Treat full backups like password files. Do not attach them to GitHub issues, Discord, or other public channels.

#### Import behavior

Import merges the snapshot into the running instance:

- Redacted `***` values do **not** overwrite existing secrets.
- If you import a safe export on a fresh instance, service credentials and Trakt OAuth tokens must be re-entered or re-linked.
- If you import a safe export on an instance that already has credentials, existing secrets are preserved.
- A full backup import restores credentials and Trakt tokens without re-linking.

After importing a safe export, Trakt links may still show as connected in metadata, but Trakt features will not work until each user links Trakt again unless the import included live OAuth tokens.

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
10. Re-link Trakt accounts if you imported a safe export without OAuth tokens.
11. Save or restart the container if needed.

#### API note

`GET /api/admin/export-config` is a separate, older endpoint. It exports integrations and settings only and does **not** include `media_users` or restore them on import. Use the Dashboard export/import flow (or `/api/config/export` directly) when Trakt user links must move with the instance.

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

### Need more logs

Temporarily set:

```yaml
environment:
  - LOG_LEVEL=DEBUG
```

Restart, reproduce issue, then return to `INFO`.
