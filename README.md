<div align="center">

## 🚀 SuggestArr - Media Automation Made Simple

![ezgif com-optimize (2)](https://github.com/user-attachments/assets/d5c48bdb-3c11-4f35-bb55-849297d521e7)

![Build Status](https://img.shields.io/github/actions/workflow/status/giuseppe99barchetta/suggestarr/docker_hub_build.yml?branch=main&label=Build&logo=github)
![Platform Support](https://img.shields.io/badge/platforms-linux%2Famd64%20|%20linux%2Farm64-blue?logo=linux)
![Docker Pulls](https://img.shields.io/docker/pulls/ciuse99/suggestarr?label=Docker%20Pulls&logo=docker)
[![Buy Me a Coffee](https://img.shields.io/badge/Donate-Buy%20Me%20a%20Coffee-orange?logo=buy-me-a-coffee)](https://buymeacoffee.com/suggestarr)
[![](https://dcbadge.limes.pink/api/server/https://discord.com/invite/JXwFd3PnXY?style=flat)](https://discord.com/invite/JXwFd3PnXY)
</div>

SuggestArr is a project designed to automate media content recommendations and download requests based on user activity in media servers like **Jellyfin**, **Plex**, and now **Emby**. It retrieves recently watched content, searches for similar titles using the TMDb API, and sends automated download requests to **Jellyseer** or **Overseer**.

## Features
- **Multi-Media Server Support**: Supports Jellyfin, Plex, and Emby for retrieving media content.
- **TMDb Integration**: Searches for similar movies and TV shows on TMDb.
- **AI-Powered Recommendations** *(beta)*: Uses any OpenAI-compatible LLM (OpenAI, Ollama, Gemini, LiteLLM…) to generate hyper-personalized suggestions based on watch history, complete with AI reasoning for each pick.
- **AI Search** *(beta)*: Describe in natural language what you want to watch and let the AI find matching titles, personalised to your viewing history, with one-click request to Seer.
- **Automated Requests**: Sends download requests for recommended content to Jellyseer or Seer.
- **Web Interface**: A user-friendly interface for configuration and management.
- **Real-Time Logs**: View and filter logs in real time (e.g., `INFO`, `ERROR`, `DEBUG`).
- **User Selection**: Choose specific users to initiate requests, allowing management and approval of auto-requested content.
- **Cron Job Management**: Update the cron job schedule directly from the web interface.
- **Configuration Pre-testing**: Automatically validates API keys and URLs during setup.
- **Content Filtering**: Exclude requests for content already available on streaming platforms in your country.
- **External Database Support**: Use external databases (PostgreSQL, MySQL) in addition to SQLite for improved scalability and performance.

## Prerequisites
- **Python 3.x** or **Docker**
- **[TMDb API Key](https://www.themoviedb.org/documentation/api)**
- Configured **[Jellyfin](https://jellyfin.org/)**, **[Plex](https://www.plex.tv/)**, or **[Emby](https://emby.media/)**
- Configured **[Jellyseer](https://github.com/Fallenbagel/jellyseerr)** or **[Overseer](https://github.com/sct/overseerr)**
- (Optional) External database (PostgreSQL or MySQL) for improved performance

## Docker Usage

You can run the project using Docker Compose for easy setup and execution.

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

### Using a Specific Jellyseer/Overseer User for Requests
If you'd like to use a specific Jellyseer user to make media requests, follow these steps:

1. In the web interface, enable the user selection option by checking the corresponding box.
2. Select the desired user from the dropdown list.
3. Enter the password for the selected user.
4. The system will now use this user to make media requests, rather than using the admin or default profile.

Note: Currently, only local Jellyseer users are supported.

## AI-Powered Recommendations (Beta)

SuggestArr includes an optional AI recommendation engine that analyzes your watch history and suggests titles that match your taste, with a short explanation for each pick.

The engine works with **any OpenAI-compatible API**, so you can use a cloud provider or a local model running on your own machine.

### How to enable

1. Open the web interface and go to **Settings → Advanced**.
2. Check **Enable beta features**.
3. Check **Use advanced suggestion algorithm**.
4. Fill in the **AI Provider Configuration** fields that appear (click the **ⓘ** button next to the section title for an in-app guide).
5. Save. The AI engine will be used automatically on the next automation run.

> If the LLM is unavailable or returns no results, SuggestArr falls back to the standard TMDb-based recommendation algorithm transparently.

### Supported providers

| Provider | API Key | Base URL | Example model |
|---|---|---|---|
| **OpenAI** | Required (`sk-proj-...`) | *(leave blank)* | `gpt-4o-mini` |
| **Ollama** (local) | Not required | `http://localhost:11434/v1` | `mistral`, `llama3` |
| **OpenRouter** | Required (`sk-or-v1-...`) | `https://openrouter.ai/api/v1` | `meta-llama/llama-3-8b-instruct` |
| **LiteLLM Proxy** | Depends on config | `http://<your-proxy>:4000` | Depends on config |

**Note for Ollama users:** make sure Ollama is running and the model is pulled (`ollama pull mistral`) before saving. The API Key field can be left blank — SuggestArr will use a placeholder automatically.

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

## 🔍 AI Search (Beta)

SuggestArr includes an **AI Search** tab in the dashboard that lets you find movies and TV shows using plain text, no browsing required.

### How it works

Type a natural-language description of what you feel like watching. The LLM interprets your query (genres, era, language, rating threshold, mood…) and translates it into structured TMDB filters. Results are ranked and enriched with an AI-generated rationale explaining why each title was picked for you.

**Examples of queries you can use:**
- *"A psychological thriller from the 90s with a twist ending"*
- *"Feel-good anime with strong friendships"*
- *"80s sci-fi movies with practical effects"*
- *"A dark comedy series like Breaking Bad"*

### Key capabilities

- **Natural language queries** — describe mood, genre, decade, language, or specific themes
- **Viewing-history personalisation** — the AI tailors results based on what you (or your users) have already watched
- **Exclude already-watched titles** — hide content you've already seen
- **One-click requesting** — send results directly to Jellyseer/Overseer without leaving the page
- **Query interpretation badge** — see how the AI parsed your query (genres, year range, language, min rating)

### How to enable

AI Search requires an LLM to be configured (same setup as AI-Powered Recommendations):

1. Open the web interface → **Settings → Advanced**.
2. Check **Enable beta features**.
3. Fill in the **AI Provider Configuration** fields (API key, base URL, model).
4. Save. The **AI Search** tab will become active in the dashboard.

> AI Search is independent of the automated recommendations run — it is triggered manually from the dashboard and does not affect cron-based automation.

---

## Running Without Docker
For detailed instructions on setting up SuggestArr withouth Docker or as a system service, please refer to our [Installation Guide](https://github.com/giuseppe99barchetta/SuggestArr/wiki/Installation#documentation-to-run-the-project-without-docker).

## Join Our Discord Community
Feel free to join our Discord community to share ideas, ask questions, or get help with SuggestArr: [Join here](https://discord.gg/JXwFd3PnXY).

## Contribute
Contributions are highly welcome! Feel free to open issues, submit pull requests, or provide any feedback that can improve the project. Whether you're fixing bugs, improving documentation, or adding new features, all contributions are greatly appreciated.

## License
This project is licensed under the MIT License.

