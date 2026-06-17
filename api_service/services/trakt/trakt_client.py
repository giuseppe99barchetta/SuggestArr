import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from api_service.db.database_manager import DatabaseManager
from api_service.services.http.base_client import BaseHTTPClient


class TraktDeviceFlowError(RuntimeError):
    """Base error for the Trakt device-code OAuth flow."""


class TraktDevicePending(TraktDeviceFlowError):
    """Device authorization is still pending (covers HTTP 400 and 429 slow_down)."""


class TraktDeviceExpired(TraktDeviceFlowError):
    """The Trakt device code has expired (HTTP 410)."""


class TraktDeviceDenied(TraktDeviceFlowError):
    """The user denied the Trakt authorization (HTTP 418/409)."""


class TraktClient(BaseHTTPClient):
    """Async client for Trakt OAuth and watched-history APIs."""

    BASE_URL = "https://api.trakt.tv"
    REFRESH_WINDOW_SECONDS = 300

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: str = "",
        refresh_token: str = "",
        expires_at: Optional[int] = None,
        session=None,
        db=None,
        link_id: Optional[int] = None,
        token_source: str = "manual_oauth",
    ):
        super().__init__()
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.access_token = access_token or ""
        self.refresh_token = refresh_token or ""
        self.expires_at = int(expires_at or 0)
        self.session = session
        self._owns_session = session is None
        self.db = db or DatabaseManager()
        self.link_id = link_id
        self.token_source = token_source
        self.existing_content = {"movie": [], "tv": []}

    async def _get_session(self):
        if self.session is not None and not getattr(self.session, "closed", False):
            return self.session
        return await super()._get_session()

    async def close(self):
        if self._owns_session:
            await super().close()

    def _headers(self, authenticated: bool = True) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "trakt-api-key": self.client_id,
            "trakt-api-version": "2",
        }
        if authenticated and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def request_device_code(self) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/oauth/device/code",
            json={"client_id": self.client_id},
            authenticated=False,
        )

    async def poll_for_token(self, device_code: str) -> dict[str, Any]:
        """
        Poll the Trakt device-token endpoint and map its status to the flow state.

        Trakt signals device-flow state via HTTP status codes with mostly empty
        bodies, so this method bypasses the generic ``_request`` error path and
        translates each status into a dedicated outcome.

        Args:
            device_code: The device code returned by ``request_device_code``.

        Returns:
            dict[str, Any]: The persisted token payload on success.

        Raises:
            TraktDevicePending: Authorization still pending (HTTP 400/429).
            TraktDeviceExpired: The device code expired (HTTP 410).
            TraktDeviceDenied: The user denied authorization (HTTP 418/409).
            TraktDeviceFlowError: Any other unexpected status code.
            RuntimeError: Network-level failures from aiohttp.
        """
        url = f"{self.BASE_URL}/oauth/device/token"
        session = await self._get_session()
        body = {
            "code": device_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with session.post(
                url,
                headers=self._headers(authenticated=False),
                json=body,
            ) as response:
                status = response.status
                if status in self.HTTP_OK:
                    payload = await response.json()
                    return self._apply_and_persist_tokens(payload)
                if status in (400, 429):
                    raise TraktDevicePending("Trakt device authorization pending")
                if status == 410:
                    raise TraktDeviceExpired("Trakt device code expired")
                if status in (418, 409):
                    raise TraktDeviceDenied("Trakt authorization was denied")
                raise TraktDeviceFlowError(f"Trakt device authorization failed (status {status})")
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"Trakt API request failed: POST {url}: {exc}") from exc

    async def refresh_access_token(self) -> dict[str, Any]:
        if not self.refresh_token:
            raise RuntimeError("Cannot refresh Trakt token without a refresh token")

        payload = await self._request(
            "POST",
            "/oauth/token",
            json={
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                "grant_type": "refresh_token",
            },
            authenticated=False,
        )
        return self._apply_and_persist_tokens(payload)

    async def get_recent_items(self, limit: int = 10) -> list[dict[str, str]]:
        payload = await self._request(
            "GET",
            "/sync/history",
            params={"limit": limit},
            authenticated=True,
        )
        return self._normalize_recent_items(payload)

    async def get_user_settings(self) -> dict[str, Any]:
        """Fetch and normalize the authenticated Trakt user's settings."""
        payload = await self._request("GET", "/users/settings", authenticated=True)
        return self._normalize_user_settings(payload)

    async def init_existing_content(self) -> None:
        movies = await self._request("GET", "/sync/watched/movies", authenticated=True)
        shows = await self._request("GET", "/sync/watched/shows", authenticated=True)
        self.existing_content = {
            "movie": self._normalize_watched_items(movies, "movie"),
            "tv": self._normalize_watched_items(shows, "show"),
        }

    async def get_recommendations(
        self,
        media_type: str,
        *,
        limit: int = 20,
        ignore_collected: bool = False,
        ignore_watched: bool = False,
    ) -> list[dict[str, str]]:
        """Fetch personalized Trakt recommendations for the authenticated user.

        Args:
            media_type: ``movie`` or ``tv``.
            limit: Maximum number of recommendations to return.
            ignore_collected: When True, omit items already in the user's collection.
            ignore_watched: When True, omit items already marked watched.

        Returns:
            Normalized recommendation items with ``tmdb_id``, ``media_type``,
            ``title``, and ``year`` keys.
        """
        if media_type not in ("movie", "tv"):
            raise ValueError("media_type must be 'movie' or 'tv'")

        path = "/recommendations/movies" if media_type == "movie" else "/recommendations/shows"
        params: dict[str, Any] = {
            "limit": max(1, min(int(limit), 100)),
            "extended": "min",
        }
        if ignore_collected:
            params["ignore_collected"] = "true"
        if ignore_watched:
            params["ignore_watched"] = "true"

        payload = await self._request("GET", path, params=params, authenticated=True)
        return self._normalize_recommendation_items(payload, media_type)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        authenticated: bool = True,
        retry_auth: bool = True,
        retry_rate_limit: bool = True,
    ) -> Any:
        if authenticated:
            await self._refresh_if_needed()

        url = path if path.startswith("http") else f"{self.BASE_URL}{path}"
        session = await self._get_session()
        request_method = getattr(session, method.lower())
        kwargs: dict[str, Any] = {"headers": self._headers(authenticated)}
        if params is not None:
            kwargs["params"] = params
        if json is not None:
            kwargs["json"] = json

        try:
            async with request_method(url, **kwargs) as response:
                if response.status in self.HTTP_OK:
                    return await response.json()

                if response.status == 429 and retry_rate_limit:
                    retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                    if retry_after > 0:
                        await asyncio.sleep(retry_after)
                    return await self._request(
                        method,
                        path,
                        params=params,
                        json=json,
                        authenticated=authenticated,
                        retry_auth=retry_auth,
                        retry_rate_limit=False,
                    )

                if response.status == 401 and authenticated and retry_auth:
                    await self.refresh_access_token()
                    return await self._request(
                        method,
                        path,
                        params=params,
                        json=json,
                        authenticated=authenticated,
                        retry_auth=False,
                        retry_rate_limit=retry_rate_limit,
                    )

                body = await response.text()
                raise RuntimeError(f"Trakt API request failed: {method} {url} returned {response.status}: {body}")
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"Trakt API request failed: {method} {url}: {exc}") from exc

    async def _refresh_if_needed(self) -> None:
        if not self.refresh_token or not self.expires_at:
            return
        if self.expires_at <= int(time.time()) + self.REFRESH_WINDOW_SECONDS:
            await self.refresh_access_token()

    def _apply_and_persist_tokens(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.access_token = payload.get("access_token", self.access_token)
        self.refresh_token = payload.get("refresh_token", self.refresh_token)
        expires_in = int(payload.get("expires_in") or 0)
        if expires_in:
            self.expires_at = int(time.time()) + expires_in

        if self.link_id and self.token_source == "manual_oauth":
            self.db.update_trakt_oauth_tokens(
                self.link_id,
                self.access_token,
                self.refresh_token,
                self.expires_at,
            )

        result = dict(payload)
        result["expires_at"] = self.expires_at
        return result

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def _normalize_recent_items(self, payload: list[dict[str, Any]]) -> list[dict[str, str]]:
        items = []
        seen: dict[tuple[str, str], int] = {}
        for entry in payload or []:
            entry_type = entry.get("type")
            if entry_type == "movie":
                normalized = self._normalize_media_item(entry.get("movie"), "movie")
            elif entry_type in ("episode", "show"):
                normalized = self._normalize_media_item(entry.get("show"), "tv")
            else:
                normalized = None

            if not normalized:
                continue

            watched_at_raw = entry.get("watched_at")
            watched_at = self._parse_iso(watched_at_raw) if watched_at_raw else 0

            key = (normalized["media_type"], normalized["tmdb_id"])
            if key in seen:
                if watched_at <= seen[key]:
                    continue
                items = [s for s in items if (s["media_type"], s["tmdb_id"]) != key]
            seen[key] = watched_at
            normalized["watched_at"] = watched_at
            items.append(normalized)
        return items

    @staticmethod
    def _parse_iso(ts: Optional[str]) -> int:
        """Parse ISO 8601 timestamp to Unix timestamp."""
        if not ts:
            return 0
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _normalize_media_item(item: Optional[dict[str, Any]], media_type: str) -> Optional[dict[str, str]]:
        if not item:
            return None
        tmdb_id = item.get("ids", {}).get("tmdb")
        if not tmdb_id:
            return None
        title = item.get("title") or item.get("name") or ""
        return {
            "tmdb_id": str(tmdb_id),
            "media_type": media_type,
            "title": title,
            "year": item.get("year"),
        }

    def _normalize_recommendation_items(
        self,
        payload: list[dict[str, Any]],
        media_type: str,
    ) -> list[dict[str, str]]:
        """Normalize Trakt recommendation payloads into TMDB-keyed items."""
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for entry in payload or []:
            normalized = self._normalize_media_item(entry, media_type)
            if not normalized:
                continue
            tmdb_id = normalized["tmdb_id"]
            if tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            items.append(normalized)
        return items

    @staticmethod
    def _normalize_watched_items(payload: list[dict[str, Any]], item_key: str) -> list[dict[str, str]]:
        normalized = []
        seen = set()
        for entry in payload or []:
            item = entry.get(item_key) or {}
            tmdb_id = item.get("ids", {}).get("tmdb")
            if not tmdb_id:
                continue
            tmdb_id = str(tmdb_id)
            if tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            normalized.append({
                "tmdb_id": tmdb_id,
                "title": item.get("title") or item.get("name") or "",
                "year": item.get("year"),
            })
        return normalized

    @staticmethod
    def _normalize_user_settings(payload: Optional[dict[str, Any]]) -> dict[str, Any]:
        payload = payload or {}
        user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
        ids = user.get("ids") if isinstance(user.get("ids"), dict) else {}
        username = user.get("username") or user.get("name") or user.get("slug") or ids.get("slug") or ""
        trakt_user_id = ids.get("uuid") or ids.get("slug") or ids.get("trakt") or user.get("id")
        if trakt_user_id is None:
            trakt_user_id = username
        return {
            "trakt_user_id": str(trakt_user_id) if trakt_user_id is not None else "",
            "trakt_username": str(username) if username is not None else "",
        }
