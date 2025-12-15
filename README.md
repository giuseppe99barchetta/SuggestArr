<div align="center">

## 🚀 SuggestArr - Media Automation Made Simple
Forked from: https://github.com/giuseppe99barchetta/SuggestArr

![ezgif com-optimize (2)](https://github.com/user-attachments/assets/d5c48bdb-3c11-4f35-bb55-849297d521e7)

SuggestArr is a project designed to automate media content recommendations and download requests based on user activity in media servers like **Jellyfin**, **Plex**, and now **Emby**. It retrieves recently watched content, searches for similar titles using the TMDb API, and sends automated download requests to **Jellyseer** or **Overseer**.

## Features
- **Multi-Media Server Support**: Supports Jellyfin, Plex, and Emby for retrieving media content.
- **TMDb Integration**: Searches for similar movies and TV shows on TMDb.
- **Automated Requests**: Sends download requests for recommended content to Jellyseer or Overseer.
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
    image: ghcr.io/todd2982/suggestarr:latest
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

## Running Without Docker
For detailed instructions on setting up SuggestArr withouth Docker or as a system service, please refer to our [Installation Guide](https://github.com/giuseppe99barchetta/SuggestArr/wiki/Installation#documentation-to-run-the-project-without-docker).

## Contribute
Contributions are highly welcome! Feel free to open issues, submit pull requests, or provide any feedback that can improve the project. Whether you're fixing bugs, improving documentation, or adding new features, all contributions are greatly appreciated.

## License
This project is licensed under the MIT License.
