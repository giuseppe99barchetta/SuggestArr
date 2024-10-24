
# SuggestArr
![image](https://github.com/user-attachments/assets/b9296eb8-f264-45d5-a8df-c03783af7bb9)

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

## Prerequisites
- **Python 3.x** or **Docker**
- **[TMDb API Key](https://www.themoviedb.org/documentation/api)**
- Configured **[Jellyfin](https://jellyfin.org/)**, **[Plex](https://www.plex.tv/)**, or **[Emby](https://emby.media/)**
- Configured **[Jellyseer](https://github.com/Fallenbagel/jellyseerr)** or **[Overseer](https://github.com/sct/overseerr)**

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
      - "5000:5000"
    volumes:
      - ./config_files:/app/config/config_files
```
To start the container with Docker Compose:

```bash
docker-compose up
```

## Web Interface

Access the web interface at: http://localhost:5000. Use this interface to configure the application, select your media service, and manage cron schedules.

Make sure your environment is set up correctly and that the application is running to access the web interface.

### Using a Specific Jellyseer/Overseer User for Requests
If you'd like to use a specific Jellyseer user to make media requests, follow these steps:

1. In the web interface, enable the user selection option by checking the corresponding box.
2. Select the desired user from the dropdown list.
3. Enter the password for the selected user.
4. The system will now use this user to make media requests, rather than using the admin or default profile.

Note: Currently, only local Jellyseer users are supported.

## Running Without Docker
You can also run the project locally by installing the dependencies and setting the environment variables.

### Steps:
1. Install Python dependencies:

```bash
pip install -r requirements.txt
```
2. Run the project:

```bash
python app.py
```

3. Access to the web interface
The web interface will be available at: [http://localhost:5000](http://localhost:5000).

## Contribute
Contributions are highly welcome! Feel free to open issues, submit pull requests, or provide any feedback that can improve the project. Whether you're fixing bugs, improving documentation, or adding new features, all contributions are greatly appreciated.

## License
This project is licensed under the MIT License.

