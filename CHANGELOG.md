# Changelog  
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
