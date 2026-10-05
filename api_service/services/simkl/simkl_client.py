"""Async client for the Simkl device auth and library-sync APIs.

Mirrors :mod:`api_service.services.trakt.trakt_client` in shape, but differs in
three ways that are forced by the Simkl API rather than by preference:

* Auth is the RFC 8628 device flow, which needs no ``client_secret`` or redirect
  URI and returns refreshable OAuth V2 tokens.
* Access tokens expire after seven days, so the client refreshes them before
  use and persists the replacement with the link.
* Reads are metered and ungated polling of ``/sync/all-items`` gets the
  ``client_id`` suspended, so requests are serialized and deterministic errors
  are never retried.
"""
import asyncio
import random
import time
from typing import Any, Optional

import aiohttp

from api_service.services.http.base_client import BaseHTTPClient
from api_service.version import APP_NAME, APP_VERSION, USER_AGENT


class SimklError(RuntimeError):
    """Base error for all Simkl API failures."""


class SimklPinFlowError(SimklError):
    """Base error for the Simkl PIN authorization flow."""


class SimklPinPending(SimklPinFlowError):
    """The user has not entered the PIN yet; keep polling."""

    def __init__(self, message: str = "Simkl device authorization pending", interval: Optional[int] = None):
        super().__init__(message)
        self.interval = interval


class SimklPinExpired(SimklPinFlowError):
    """The PIN was consumed or expired; a new one must be requested."""


class SimklAuthError(SimklError):
    """HTTP 401 ``user_token_failed``.

    The caller can retry once after a refresh; if the refresh is also rejected,
    the link needs a new device authorization.
    """


class SimklClientIdError(SimklError):
    """HTTP 412 ``client_id_failed``.

    Install-wide rather than per-user: the ``client_id`` is wrong, suspended,
    or over its request cap. Never retried, and surfaced on the integration
    settings card rather than against any one user's link.
    """


class SimklClient(BaseHTTPClient):
    """Async client for Simkl PIN auth and watched-library APIs."""

    BASE_URL = "https://api.simkl.com"

    # A first full library sync pulls several hundred entries per type; the
    # base client's 10s budget is sized for single-resource calls.
    REQUEST_TIMEOUT = 60

    # Simkl documents 1s/2s/4s/8s/16s with jitter, then give up.
    RETRY_STATUSES = frozenset({429, 500, 502, 503})
    MAX_RETRIES = 5

    # Statuses that exist per media type. Requesting movies/watching returns
    # {} with HTTP 200 rather than an error, so a wrong entry here would waste
    # a call on every sync without ever announcing itself.
    STATUSES_BY_TYPE = {
        "shows": ("watching", "completed", "hold", "dropped"),
        "anime": ("watching", "completed", "hold", "dropped"),
        "movies": ("completed", "dropped"),
    }

    # /sync/activities keys its buckets differently from the /sync/all-items
    # path segment: "tv_shows" there, "shows" in the URL.
    ACTIVITIES_KEY_BY_TYPE = {
        "shows": "tv_shows",
        "anime": "anime",
        "movies": "movies",
    }

    def __init__(
        self,
        client_id: str,
        access_token: str = "",
        refresh_token: str = "",
        expires_at: Optional[int] = None,
        session=None,
        db=None,
        link_id: Optional[int] = None,
    ):
        super().__init__()
        self.client_id = (client_id or "").strip()
        self.access_token = access_token or ""
        self.refresh_token = refresh_token or ""
        self.expires_at = int(expires_at or 0)
        self.session = session
        self._owns_session = session is None
        self.db = db
        self.link_id = link_id
        # Simkl allows parallelism only on edge-cached endpoints; sync and
        # user-state calls must stay sequential. Enforced here rather than
        # trusting every caller to serialize correctly.
        self._request_lock = asyncio.Lock()

    async def _get_session(self):
        if self.session is not None and not getattr(self.session, "closed", False):
            return self.session
        return await super()._get_session()

    async def close(self):
        if self._owns_session:
            await super().close()

    def _headers(self, authenticated: bool = True, form: bool = False) -> dict[str, str]:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded" if form else "application/json",
            "User-Agent": USER_AGENT,
        }
        if authenticated and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _app_params(self) -> dict[str, str]:
        """The three query parameters Simkl requires on every request."""
        return {
            "client_id": self.client_id,
            "app-name": APP_NAME,
            "app-version": APP_VERSION,
        }

    # ---- Device flow ----------------------------------------------------------

    async def request_pin_code(self) -> dict[str, Any]:
        """Request a new device code, returning only user-facing fields.

        Returns:
            dict[str, Any]: The public code and verification URLs. The private
            ``device_code`` is retained only in the server-side pending state.
        """
        payload = await self._request(
            "POST",
            "/oauth2/device",
            data={"client_id": self.client_id, "scope": "media:read"},
            authenticated=False,
        )
        return {
            "user_code": payload.get("user_code") or "",
            "verification_uri": payload.get("verification_uri") or "https://simkl.com/pin",
            "verification_uri_complete": payload.get("verification_uri_complete") or "",
            "device_code": payload.get("device_code") or "",
            "expires_in": int(payload.get("expires_in") or 900),
            "interval": int(payload.get("interval") or 5),
        }

    async def poll_for_token(self, device_code: str) -> dict[str, Any]:
        """Poll a pending device authorization once.

        Simkl answers with HTTP 200 in every case and puts the state in the
        body, so this maps body shape to flow state.

        Args:
            device_code: The private code returned by :meth:`request_pin_code`.

        Returns:
            dict[str, Any]: The V2 token response, once the user has authorized.

        Raises:
            SimklPinPending: The user has not entered the code yet.
            SimklPinExpired: The code was consumed or expired.
            SimklPinFlowError: The response matched no known shape.
        """
        device_code = str(device_code or "").strip()
        if not device_code:
            raise SimklPinFlowError("Cannot poll Simkl without a device code")

        status, payload = await self._post_oauth_form(
            "/oauth2/token",
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": self.client_id,
                "device_code": device_code,
            },
        )
        if status in self.HTTP_OK:
            if not isinstance(payload, dict) or not payload.get("access_token"):
                raise SimklPinFlowError("Simkl returned no access token")
            return self._apply_and_persist_tokens(payload)

        error = payload.get("error") if isinstance(payload, dict) else None
        if error == "authorization_pending":
            raise SimklPinPending()
        if error == "slow_down":
            raise SimklPinPending("Simkl asked the client to slow down", interval=10)
        if error == "expired_token":
            raise SimklPinExpired("Simkl device code expired")
        if error == "invalid_client":
            raise SimklClientIdError("Simkl rejected the client ID for OAuth V2")
        raise SimklPinFlowError(
            str((payload or {}).get("error_description") or "Simkl device authorization failed")
        )

    async def refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token and persist the new expiry and token pair."""
        if not self.refresh_token:
            raise SimklAuthError("Simkl access token expired; re-authorization required")
        payload = await self._request(
            "POST",
            "/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": self.refresh_token,
            },
            authenticated=False,
        )
        return self._apply_and_persist_tokens(payload)

    async def revoke_token(self, token: str) -> None:
        """Revoke one V2 grant; Simkl invalidates its access and refresh pair."""
        if not token:
            return
        status, _ = await self._post_oauth_form(
            "/oauth2/revoke", {"client_id": self.client_id, "token": token},
        )
        if status not in self.HTTP_OK:
            self._raise_for_deterministic_status(
                status, "POST", f"{self.BASE_URL}/oauth2/revoke", False,
            )
            raise SimklError(f"Simkl token revocation failed with status {status}")

    # ---- User + sync ----------------------------------------------------------

    async def get_user_settings(self) -> dict[str, Any]:
        """Fetch and normalize the authenticated user's Simkl identity.

        ``POST`` for historical reasons; the endpoint takes no body. The raw
        payload carries profile PII (age, gender, bio, location) that we
        deliberately do not read or persist.
        """
        payload = await self._request("POST", "/users/settings", authenticated=True)
        return self._normalize_user_settings(payload)

    async def get_activities(self) -> dict[str, Any]:
        """Fetch per-list last-modified timestamps.

        The cheapest call in the API and the gate for every sync: nothing else
        is fetched unless a timestamp here has moved.
        """
        return await self._request("GET", "/sync/activities", authenticated=True) or {}

    async def get_all_items(
        self,
        media_type: str,
        status: str,
        *,
        date_from: Optional[str] = None,
        ids_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch one ``(type, status)`` bucket of the user's library.

        Args:
            media_type: ``shows``, ``movies``, or ``anime``.
            status: A status valid for that type; see :attr:`STATUSES_BY_TYPE`.
            date_from: ISO 8601 timestamp limiting the response to changes since.
            ids_only: Request the ``ids_only`` projection. This drops ``title``,
                ``year``, and ``last_watched_at``, so it is only useful for the
                removal reconcile, which needs the ID set and nothing else.

        Returns:
            list[dict[str, Any]]: Raw entry envelopes, or an empty list. Simkl
            answers an empty bucket with ``{}``, not an empty array.

        Raises:
            SimklError: The body was not a JSON object. An empty list here
                means "this bucket is empty", which the removal reconcile acts
                on by deleting cached rows, so a shape we cannot read must not
                be allowed to masquerade as one.
        """
        if media_type not in self.STATUSES_BY_TYPE:
            raise ValueError(f"Unknown Simkl media type: {media_type}")

        params: dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from
        if ids_only:
            params["extended"] = "ids_only"

        path = f"/sync/all-items/{media_type}/{status}" if status else f"/sync/all-items/{media_type}"
        payload = await self._request("GET", path, params=params, authenticated=True)
        if not isinstance(payload, dict):
            raise SimklError(
                f"Simkl returned a {type(payload).__name__} for "
                f"/sync/all-items/{media_type}/{status}; expected a JSON object"
            )
        # The response key is the media type, except that anime entries are
        # returned under "anime" while each entry wraps its media object in a
        # "show" key like TV does.
        return payload.get(media_type) or []

    # ---- Transport ------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        authenticated: bool = True,
    ) -> Any:
        if authenticated:
            await self._refresh_if_needed()
        url = f"{self.BASE_URL}{path}"
        query = self._app_params()
        if params:
            query.update({k: v for k, v in params.items() if v is not None})

        async with self._request_lock:
            return await self._request_with_retries(method, url, query, data, authenticated)

    async def _post_oauth_form(self, path: str, data: dict[str, Any]) -> tuple[int, Any]:
        """Post an OAuth form without applying API retry or error mapping."""
        url = f"{self.BASE_URL}{path}"
        async with self._request_lock:
            session = await self._get_session()
            try:
                async with session.post(
                    url,
                    headers=self._headers(authenticated=False, form=True),
                    params=self._app_params(),
                    data=data,
                ) as response:
                    try:
                        payload = await response.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError):
                        payload = {}
                    return response.status, payload
            except aiohttp.ClientError as exc:
                raise SimklError(f"Simkl OAuth request failed: POST {url}: {exc}") from exc

    async def _request_with_retries(
        self,
        method: str,
        url: str,
        query: dict[str, Any],
        data: Optional[dict[str, Any]],
        authenticated: bool,
    ) -> Any:
        last_status = None
        for attempt in range(self.MAX_RETRIES):
            session = await self._get_session()
            request_method = getattr(session, method.lower())
            try:
                kwargs = {"headers": self._headers(authenticated), "params": query}
                if data is not None:
                    kwargs["data"] = data
                    kwargs["headers"] = self._headers(authenticated, form=True)
                async with request_method(url, **kwargs) as response:
                    if response.status in self.HTTP_OK:
                        return await response.json(content_type=None)

                    self._raise_for_deterministic_status(
                        response.status, method, url, authenticated,
                    )

                    last_status = response.status
                    if response.status not in self.RETRY_STATUSES:
                        body = await response.text()
                        raise SimklError(
                            f"Simkl API request failed: {method} {url} returned "
                            f"{response.status}: {body[:200]}"
                        )
            except aiohttp.ClientError as exc:
                if attempt == self.MAX_RETRIES - 1:
                    raise SimklError(f"Simkl API request failed: {method} {url}: {exc}") from exc
                last_status = None

            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep((2 ** attempt) + random.random())

        raise SimklError(
            f"Simkl API request failed after {self.MAX_RETRIES} attempts: "
            f"{method} {url} (last status {last_status})"
        )

    @staticmethod
    def _raise_for_deterministic_status(
        status: int, method: str, url: str, authenticated: bool = True
    ) -> None:
        """Translate non-retryable statuses into typed errors.

        Simkl is explicit that retrying 4xx wastes quota and induces a 429, so
        these terminate the request immediately.
        """
        if status == 401:
            if authenticated:
                raise SimklAuthError("Simkl access token rejected; re-authorization required")
            raise SimklClientIdError("Simkl rejected the client ID for OAuth V2")
        if status == 412:
            raise SimklClientIdError(
                "Simkl rejected the client ID: wrong, suspended, or over its request limit"
            )
        if status in (400, 403, 404, 409):
            raise SimklError(f"Simkl API request failed: {method} {url} returned {status}")

    async def _refresh_if_needed(self) -> None:
        if self.refresh_token and self.expires_at and self.expires_at <= int(time.time()) + 300:
            await self.refresh_access_token()

    def _apply_and_persist_tokens(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.access_token = payload.get("access_token", self.access_token)
        self.refresh_token = payload.get("refresh_token", self.refresh_token)
        expires_in = int(payload.get("expires_in") or 0)
        if expires_in:
            self.expires_at = int(time.time()) + expires_in

        if self.db is not None and self.link_id:
            self.db.upsert_simkl_oauth_tokens(
                link_id=self.link_id,
                access_token=self.access_token,
                refresh_token=self.refresh_token,
                expires_at=self.expires_at or None,
            )

        result = dict(payload)
        result["expires_at"] = self.expires_at or None
        return result

    # ---- Normalization --------------------------------------------------------

    @staticmethod
    def _normalize_user_settings(payload: Optional[dict[str, Any]]) -> dict[str, Any]:
        """Reduce the settings payload to the two identity fields we store.

        Simkl offers only a mutable display name and an integer account id,
        where Trakt exposes ``username``/``slug``/``uuid``. The account id is
        the stable half, and is what a re-link compares against to decide
        whether a cached library still belongs to the same account.
        """
        payload = payload or {}
        user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
        account = payload.get("account") if isinstance(payload.get("account"), dict) else {}
        account_id = account.get("id")
        username = user.get("name") or ""
        return {
            "simkl_user_id": str(account_id) if account_id is not None else "",
            "simkl_username": str(username),
        }
