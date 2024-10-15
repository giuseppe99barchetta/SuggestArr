
# Jellyfin TMDb Sync Automation
![jellyfin github](https://github.com/user-attachments/assets/78c0616b-f7d2-49f6-9ff6-2c1f9969aae9)

This project is designed to fully automate the process of managing media content recommendations and downloads based on user activity within Jellyfin. Specifically, it focuses on retrieving recently watched movies and TV shows from Jellyfin, searching for similar titles using the TMDb API, and sending automated download requests for the recommended content directly to Jellyseer.

## Features
- Fetches recently watched movies and TV shows from Jellyfin for all users.
- Searches for similar movies and TV shows on TMDb.
- Sends download requests for similar content to Jellyseer.
- Web Interface: A user-friendly web interface for configuration management.
- Cron Job Management: Easily update the cron job schedule directly from the web interface.

## Prerequisites
- Python 3.x or Docker
- Python packages: `requests`
- Virtual Python environment (optional but recommended)
- Configured Jellyfin instance with users
- Access to TMDb and Jellyseer APIs

## Links to required tools:
- **[Jellyfin](https://jellyfin.org/)**: An open-source media server that helps you organize, watch, and share your media.
- **[Jellyseer](https://github.com/Fallenbagel/jellyseerr)**: A companion tool to help automate media requests for Jellyfin.
- **[TMDb API](https://www.themoviedb.org/documentation/api)**: A popular API for retrieving movie and TV show information.

## Environment Variables
The project uses the following environment variables that can be passed via the Docker Compose file or set manually:
- `TMDB_API_KEY`: Your TMDb API key.
- `JELLYFIN_API_URL`: The URL of your Jellyfin instance.
- `JELLYFIN_TOKEN`: The API token for accessing Jellyfin.
- `JELLYSEER_API_URL`: The URL of your Jellyseer instance.
- `JELLYSEER_TOKEN`: The API token for accessing Jellyseer.
- `MAX_SIMILAR_MOVIE`: (Optional) The maximum number of similar movies to download. Default is 3, with a max limit of 20.
- `MAX_SIMILAR_TV`: (Optional) The maximum number of similar TV shows to download. Default is 2, with a max limit of 20.
- `CRON_TIMES`: (Optional) Your preferred cron schedule otherwise it runs at midnight.

## Docker Usage

You can run the project using Docker Compose for easy setup and execution.

### Docker Compose Example

```yaml
version: "3.8"

services:
  automation:
    image: ciuse99/jellyseer_request_automation
    environment:
      TMDB_API_KEY: ${TMDB_API_KEY}
      JELLYFIN_API_URL: ${JELLYFIN_API_URL}
      JELLYFIN_TOKEN: ${JELLYFIN_TOKEN}
      JELLYSEER_API_URL: ${JELLYSEER_API_URL}
      JELLYSEER_USER: ${JELLYSEER_USER}
      JELLYSEER_PASSWORD: ${JELLYSEER_PASSWORD}
      MAX_SIMILAR_MOVIE: ${MAX_SIMILAR_MOVIE:-3}  # Default is 3
      MAX_SIMILAR_TV: ${MAX_SIMILAR_TV:-2}  # Default is 2
      CRON_TIMES: ${CRON_TIMES:-0 0 * * *}  # Default cron schedule is midnight
    volumes:
      - .:/app
    container_name: automation_job
    restart: always
```
To start the container with Docker Compose:

```bash
docker-compose up --build
```

## Running Without Docker
You can also run the project locally by installing the dependencies and setting the environment variables.

### Steps:
1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment variables:

```bash
export TMDB_API_KEY=your_tmdb_api_key
export JELLYFIN_API_URL=http://your_jellyfin_url
export JELLYFIN_TOKEN=your_jellyfin_token
export JELLYSEER_API_URL=http://your_jellyseer_url
export JELLYSEER_TOKEN=your_jellyseer_token
export CRON_TIMES="0 0 * * *"  # Optional, your preferred cron schedule
```

Or create an .env file inside the project.

3. Run the project:

```bash
python automate_process.py
```

## Contribute
Contributions are highly welcome! Feel free to open issues, submit pull requests, or provide any feedback that can improve the project. Whether you're fixing bugs, improving documentation, or adding new features, all contributions are greatly appreciated.

## License
This project is licensed under the MIT License.

