
# Frequently Asked Questions

## Q: How do I set up the TMDb API key?
A: You can get a TMDb API key by following these steps:
1. Visit [TMDb](https://www.themoviedb.org/).
2. Create an account or log in if you already have one.
3. Go to the API section (https://www.themoviedb.org/settings/api) and request an API key.
4. Once approved, you will receive your API key. Set it as an environment variable `TMDB_API_KEY` or add it to your `.env` file.

## Q: How do I set up the Jellyfin API token?
A: To obtain the Jellyfin API token:
1. Install and configure [Jellyfin](https://jellyfin.org/).
2. Log into your Jellyfin server as an administrator.
3. Navigate to the "API Keys" section in the dashboard (under Admin > Dashboard > API Keys).
4. Create a new API key for the automation tool and set it as `JELLYFIN_TOKEN`.

## Q: How do I set up Jellyseer and obtain the API credentials?
A: For Jellyseer API credentials:
1. Install [Jellyseer](https://github.com/Fallenbagel/jellyseerr) to manage your media requests.
2. Log into Jellyseer as an admin.
3. Navigate to settings and copy the API KEY and set it to `JELLYSEER_TOKEN`.
4. The base URL of Jellyseer can be set as `JELLYSEER_API_URL`.

## Q: What environment variables do I need to set up?
A: The following environment variables are required for the project to run:
- `TMDB_API_KEY`: The API key for TMDb.
- `JELLYFIN_API_URL`: The URL of your Jellyfin server.
- `JELLYFIN_TOKEN`: The API token for Jellyfin.
- `JELLYSEER_API_URL`: The URL of your Jellyseer instance.
- `JELLYSEER_TOKEN`: The API token for Jellyseer.

## Q: How can I contribute to the project?
A: Please check the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines on how to contribute to the project.
