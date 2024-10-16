# Changelog  
## [1.0.3] - 2024-10-16 
### Added
- **User Selection**: Added the ability to select a specific Jellyseer user to initiate requests, enabling management and approval of content.
- **Web Interface Redesign**: Completely revamped the web interface for improved user experience and functionality.

## [1.0.2] - 2024-10-16  
### Added  
- **Utility Class**: Introduced `AppUtils` utility class to handle environment loading, worker identification, and welcome message logging. This improves code modularity and reusability.  
- **Worker Identification Enhancement**: Added a new function to identify the last Gunicorn worker based on the highest PID, optimizing the welcome message to be printed only by the last worker.  
- **Welcome Message**: Implemented a clear welcome message to guide users on systems like Unraid, helping them understand what actions to take.  

### Improved  
- **Modularity**: Refactored various utility functions (`is_last_worker`, `load_environment`, `print_welcome_message`) into a dedicated utility class (`AppUtils`), making the codebase more maintainable.
- **Cross-Platform Compatibility**: Added a cross-platform method using `psutil` to determine the last worker process, allowing the project to run seamlessly on different operating systems.

## [1.0.1] - 2024-10-15  
### Added  
- **Web Interface for Environment Variables**: Introduced a user-friendly web interface to easily set and manage environment variables directly from the application.  
- **Force Run Feature**: Added the ability to manually trigger tasks with a "Run Now" option.  
- **Customizable Cron Jobs**: Enabled customizable scheduling through a cron configuration directly in the Web Interface.
- **Reporting logs to Docker**: All application log will be also reported on docker container logs.

### Removed  
- **Documentation Cleanup**: Removed `FAQ.md` and `CONTRIBUTING.md`, with the corresponding information migrated to a dedicated Wiki page for easier access and maintenance.

## [1.0.0] - 2024-10-14
### Added
- Initial release of the project.
- Fetch recently watched movies and TV shows from Jellyfin.
- Search for similar movies and TV shows using TMDb API.
- Automated download requests via Jellyseer.
