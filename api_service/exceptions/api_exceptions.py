"""Custom exceptions for API client errors."""


class APIClientError(Exception):
    """Base class for all API client related errors."""
    def __init__(self, message, service_name=None):
        self.service_name = service_name
        self.message = message
        super().__init__(self._format_error())

    def _format_error(self):
        if self.service_name:
            return f"{self.service_name} API error: {self.message}"
        return f"API error: {self.message}"


class PlexConnectionError(APIClientError):
    """Specific error for Plex connection issues."""
    def __init__(self, message):
        super().__init__(message, "Plex")


class PlexClientError(APIClientError):
    """General error for Plex client operations."""
    def __init__(self, message):
        super().__init__(message, "Plex")


class JellyfinConnectionError(APIClientError):
    """Specific error for Jellyfin connection issues."""
    def __init__(self, message):
        super().__init__(message, "Jellyfin")


class JellyfinClientError(APIClientError):
    """General error for Jellyfin client operations."""
    def __init__(self, message):
        super().__init__(message, "Jellyfin")


class TMDBConnectionError(APIClientError):
    """Specific error for TMDB connection issues."""
    def __init__(self, message):
        super().__init__(message, "TMDB")


class TMDBClientError(APIClientError):
    """General error for TMDB client operations."""
    def __init__(self, message):
        super().__init__(message, "TMDB")


class SeerConnectionError(APIClientError):
    """Specific error for Seer connection issues."""
    def __init__(self, message):
        super().__init__(message, "Seer")


class SeerClientError(APIClientError):
    """General error for Seer client operations."""
    def __init__(self, message):
        super().__init__(message, "Seer")


class LLMValidationError(Exception):
    """Raised when the LLM response fails Pydantic validation after all retries."""