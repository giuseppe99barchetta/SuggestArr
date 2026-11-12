"""Custom exceptions for API client errors."""
import asyncio

import aiohttp


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

class BackendUnavailableError(APIClientError):
    """A delivery backend (Seer, Radarr, Sonarr) could not be reached or answered 502/503/504.

    Unlike a rejection, it says nothing about the request itself, so it must not count as a failed attempt.
    """


TRANSPORT_ERRORS = (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError)


def is_transport_error(exc: BaseException) -> bool:
    """Return True when ``exc`` means the backend could not be reached (network, timeout, outage).

    :param exc: Exception raised while delivering a request.
    :return: True for transport failures and :class:`BackendUnavailableError`.
    """
    return isinstance(exc, (*TRANSPORT_ERRORS, BackendUnavailableError))
