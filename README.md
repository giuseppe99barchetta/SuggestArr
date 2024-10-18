
# SuggestArr
![jellyfin github](https://github.com/user-attachments/assets/78c0616b-f7d2-49f6-9ff6-2c1f9969aae9)

This project is designed to fully automate the process of managing media content recommendations and downloads based on user activity within Jellyfin. Specifically, it focuses on retrieving recently watched movies and TV shows from Jellyfin, searching for similar titles using the TMDb API, and sending automated download requests for the recommended content directly to Jellyseer.

## Features
- Fetches recently watched movies and TV shows from Jellyfin for all users.
- Searches for similar movies and TV shows on TMDb.
- Sends download requests for similar content to Jellyseer.
- Web Interface: A user-friendly web interface for configuration management.
- User Selection: Choose a specific Jellyseer user to initiate requests, enabling you to manage and approve auto-requested content.
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

## Docker Usage

You can run the project using Docker Compose for easy setup and execution.

### Docker Compose Example

```yaml
services:
  automation:
    image: ciuse99/suggestarr:latest
    environment:
    container_name: SuggestArr
    restart: always
    ports:
      - "5000:5000"
```
To start the container with Docker Compose:

```bash
docker-compose up
```

## Web Interface

The web interface will be available at: [http://localhost:5000](http://localhost:5000). This interface allows you to manage the automation process more efficiently and specify custom cron schedules. It also provides the ability to select a specific Jellyseer user to make requests on their behalf.

Make sure your environment is set up correctly and that the application is running to access the web interface.

### Using a Specific Jellyseer User for Requests
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

