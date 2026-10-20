<div align="center">

## 🚀 SuggestArr - Media Automation Made Simple

![ezgif com-optimize (2)](https://github.com/user-attachments/assets/d5c48bdb-3c11-4f35-bb55-849297d521e7)

![Build Status](https://img.shields.io/github/actions/workflow/status/giuseppe99barchetta/suggestarr/docker_hub_build.yml?branch=main&label=Build&logo=github)
![Platform Support](https://img.shields.io/badge/platforms-linux%2Famd64%20|%20linux%2Farm64-blue?logo=linux)
![Docker Pulls](https://img.shields.io/docker/pulls/ciuse99/suggestarr?label=Docker%20Pulls&logo=docker)
[![Buy Me a Coffee](https://img.shields.io/badge/Donate-Buy%20Me%20a%20Coffee-orange?logo=buy-me-a-coffee)](https://buymeacoffee.com/suggestarr)
[![](https://dcbadge.limes.pink/api/server/https://discord.com/invite/JXwFd3PnXY?style=flat)](https://discord.com/invite/JXwFd3PnXY)
</div>

SuggestArr automates media recommendations and download requests based on what your users watch on **Jellyfin**, **Plex** or **Emby**. It takes recently watched content, finds similar titles through TMDb (or an AI model), and sends the requests to **Seer**.

## Features

- **Jellyfin, Plex and Emby** as watch-history sources, plus optional per-user **Trakt** history and [imported watch history](docs/WATCH_HISTORY_IMPORT.md) (CSV or manual TMDb titles with ratings).
- **Recommendations** from TMDb, or from any OpenAI-compatible LLM (OpenAI, Ollama, OpenRouter, LiteLLM…) with a short reason for each pick.
- **AI Search**: describe what you want to watch in plain language and request results in one click.
- **Public list import** from MDBList or Trakt, as a scheduled job or a single import.
- **Request control**: optional approval before sending to Seer, pause jobs while Seer requests are pending or suggestions are still unwatched, auto-decline stale Seerr requests.
- **Cleanup automation**: remove old SuggestArr requests that nobody added to favorites (dry-run by default).
- **Filters**: skip content already on streaming services in your country, plus quality and per-user filters.
- **Web interface** for setup, scheduling, users, requests and live logs, with connection tests during setup.
- **Recaps and milestones** you can share ([details](docs/RECAP.md)).
- **SQLite, PostgreSQL or MySQL** database.
- **Public REST API** with Swagger UI.

See the [Feature Guide](docs/FEATURES.md) for how each feature works.

## Requirements

- **Docker** (recommended) or Python 3
- A **[TMDb API key](https://www.themoviedb.org/documentation/api)**
- **[Jellyfin](https://jellyfin.org/)**, **[Plex](https://www.plex.tv/)** or **[Emby](https://emby.media/)**
- **[Seer](https://github.com/seerr-team/seerr)**
- Optional: PostgreSQL/MySQL, an OpenAI-compatible LLM, a [Trakt app](https://developer.trakt.tv/apps/new)

## Quick start

```yaml
services:
  suggestarr:
    image: ciuse99/suggestarr:latest   # also ghcr.io/giuseppe99barchetta/suggestarr:latest
    container_name: SuggestArr
    restart: always
    ports:
      - "${SUGGESTARR_PORT:-5000}:${SUGGESTARR_PORT:-5000}"
    volumes:
      - ./config_files:/app/config/config_files
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-info}           # optional
      - SUGGESTARR_PORT=${SUGGESTARR_PORT:-5000} # optional
```

```bash
docker compose up -d
```

Then open http://localhost:5000 and follow the setup wizard.

For Unraid, source install, reverse proxy, authentication, backups and recommended settings, see the [Installation Guide](docs/INSTALLATION.md).

## Public API

External integrations use the stable API at `/api/v1` (endpoints under `/api/*` are internal). Swagger UI is at `http://localhost:5000/docs` (or `/<SUBPATH>/docs`), and the OpenAPI document at `/api/v1/openapi.json` and `/api/v1/openapi.yaml`. See the [API guide](docs/API.md).

## Support SuggestArr ❤️

If you enjoy SuggestArr, you can support its development:

- ☕ [Ko-fi](https://ko-fi.com/ciuse99)
- 💛 [Buy Me a Coffee](https://buymeacoffee.com/suggestarr)

## Community and contributing

Questions, ideas and help on [Discord](https://discord.gg/JXwFd3PnXY). Issues and pull requests are welcome.

## License

MIT
