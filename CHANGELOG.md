# Changelog
# Changelog

## [1.0.6] - 2024-10-21

### 🚨 Important
- **Frontend Migration to Vue.js**: The entire frontend has been migrated to Vue.js, allowing for a more dynamic, reactive, and modular interface. The new design enhances usability and simplifies future feature expansions.

### ✨ Added
- **Step-Based Interface**: The interface has been completely redesigned to guide users through configuration in a step-by-step wizard format, making the process more intuitive and easier to follow.
- **API Testing**: Added API testing functionality directly in the interface, allowing users to validate TMDB, Jellyseer and Jellyfin API connections before proceeding with configuration.
- **Library Selection for Checks**: Implemented the ability to select specific Jellyfin libraries that will be used for content checks, providing more granular control over what content gets processed.
- **Cron Next Run Time**: Added a feature that displays the remaining time until the next scheduled cron execution, improving transparency and scheduling insights for users.

### 🐛 Fixed
- **Cron Execution**: Fixed an issue preventing the cron job from starting correctly.

### 🚀 Improved.
- **Optimized API Efficiency**: Reduced redundant API calls by improving caching mechanisms, particularly during configuration and testing phases.
- **Jellyseer User Selection**: The user selection dropdown now displays only local users.

## [1.0.5] - 2024-10-19
### 🚨 Important
- **Docker Compose Update**: Volume path is no longer required, and environment variables are no longer needed.

### ✨ Added
- **Asynchronous Processing**: The entire codebase has been refactored to support asynchronous operations, enhancing performance and responsiveness.

### 🐛 Fixed
- **Worker Timeout**: Resolved an issue where long-running requests caused the worker to be killed.
- **Out of Memory**: Fixed a Docker issue that triggered out-of-memory exceptions and resulted in worker restarts.
- **Cron Execution**: Fixed an issue preventing the cron job from starting correctly.

### 🚀 Improved
- **Docker Performance**: Optimized Docker performance for smoother operation.

## [1.0.4] - 2024-10-17
### Important
- **Approve automatic request**: To have the ability to approve automatic request made by SuggestArr you need to create a new local account in Jellyseer and provide the credential in the web interface or via the docker-compose file.
### Added
- **Asynchronous Processing**: Refactored the `JellyseerClient` and `ContentAutomation` to use asynchronous methods for improved performance, handling media requests concurrently.
- **Caching of Jellyseer Requests**: Implemented caching of all Jellyseer requests upon client initialization, reducing the number of API calls made during the media request verification process.
  
### Fixed
- **Duplicate Requests Prevention**: Resolved an issue where requests for already available content in Jellyseer were being re-requested, optimizing the workflow to skip items that had been previously requested.
- **Duplicate Requests Prevention**: User selection not working as expected. Need to login via user and password to perform request action as a specific user.

### Improved
- **Docker Performance**: Addressed issues where long-running processes in Docker would cause premature termination. Refined the logic to ensure processes complete successfully without interruption.

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
