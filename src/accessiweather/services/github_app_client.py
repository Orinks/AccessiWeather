from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import Callable

import httpx

from accessiweather.constants import GITHUB_API_BASE_URL
from accessiweather.version import __version__ as APP_VERSION

logger = logging.getLogger(__name__)

try:  # Optional dependency; actual usage will raise clear error if missing
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
except Exception:  # pragma: no cover - handled at runtime on first use
    hashes = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    padding = None  # type: ignore[assignment]
    load_pem_private_key = None  # type: ignore[assignment]


class GitHubAppClient:
    """GitHub App client providing JWT-based authentication and installation tokens.

    This client mirrors the HTTP patterns used by PackSubmissionService, including
    headers, timeouts, error handling, and optional progress/cancellation semantics.
    """

    def __init__(
        self,
        app_id: int | str,
        private_key_pem: str,
        installation_id: int | str,
        *,
        user_agent: str | None = None,
        api_base_url: str | None = None,
    ) -> None:
        """Initialize the GitHub App client.

        Args:
            app_id: GitHub App ID (numeric)
            private_key_pem: PEM-encoded private key for the App
            installation_id: Target installation ID to request access tokens for
            user_agent: Optional user-agent string
            api_base_url: Override base API URL (defaults to GitHub public API)

        """
        self.app_id = int(app_id)
        self.private_key_pem = private_key_pem
        self.installation_id = int(installation_id)
        self.user_agent = user_agent or f"AccessiWeather/{APP_VERSION}"
        self.api_base_url = (api_base_url or GITHUB_API_BASE_URL).rstrip("/") + "/"

        # Token cache
        self._installation_token: str | None = None
        self._installation_token_exp: int | None = None  # epoch seconds
        # Guard concurrent token refreshes
        self._token_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------
    # Public API
    # ------------------------
    async def github_request(
        self,
        method: str,
        url: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        expected: int | tuple[int, ...] = (200, 201),
        cancel_event: asyncio.Event | None = None,
    ) -> dict:
        """Perform an authenticated GitHub API request using an installation token.

        Args:
            method: HTTP method (GET/POST/...)
            url: Absolute or relative URL (relative to GitHub API base)
            json: Optional JSON body
            params: Optional query params
            expected: Expected status code(s)
            cancel_event: Optional asyncio.Event to support cancellation

        """
        self._raise_if_cancelled(cancel_event)
        token = await self.get_installation_token(cancel_event=cancel_event)

        # Normalize URL
        req_url = url if url.startswith(("http://", "https://")) else url.lstrip("/")

        expected_tuple = expected if isinstance(expected, tuple) else (expected,)
        result: dict
        async with self._get_installation_client(token) as client:
            resp = await client.request(method, req_url, json=json, params=params)
            if resp.status_code == 404 and 404 in expected_tuple:
                result = {}
            elif resp.status_code not in expected_tuple:
                try:
                    detail = resp.json()
                except Exception:
                    detail = {"message": resp.text}
                raise RuntimeError(f"GitHub API error {resp.status_code} for {req_url}: {detail}")
            else:
                try:
                    result = resp.json()
                except Exception:
                    result = {}
        return result

    async def get_installation_token(
        self,
        *,
        progress_callback: Callable[[float, str], bool | None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        """Return a valid (cached) installation access token, refreshing if needed."""
        if cancel_event is None:
            cancel_event = asyncio.Event()

        self._raise_if_cancelled(cancel_event)

        # Fast path: If cached and not expiring in the next 120 seconds, reuse
        now = int(time.time())
        if (
            self._installation_token
            and self._installation_token_exp
            and (self._installation_token_exp - now > 120)
        ):
            return self._installation_token

        async def report(pct: float, status: str) -> None:
            try:
                if progress_callback is not None:
                    res = progress_callback(pct, status)
                    if asyncio.iscoroutine(res):
                        res = await res
                    if res is False:
                        cancel_event.set()
                        raise asyncio.CancelledError("Operation cancelled by user")
            except asyncio.CancelledError:
                raise
            except Exception:
                # Non-fatal for progress updates
                pass

        await report(5.0, "Generating GitHub App JWT...")
        jwt_token = self._generate_jwt()

        # Guard concurrent refreshes
        async with self._token_lock:
            # Re-check cache under lock
            now = int(time.time())
            if (
                self._installation_token
                and self._installation_token_exp
                and (self._installation_token_exp - now > 120)
            ):
                return self._installation_token

            await report(30.0, "Requesting installation access token...")
            url = f"/app/installations/{self.installation_id}/access_tokens"

            async with self._get_app_client(jwt_token) as client:
                resp = await client.post(url)
                if resp.status_code not in (201,):
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = {"message": resp.text}
                    raise RuntimeError(
                        f"Failed to obtain installation token (HTTP {resp.status_code}): {detail}"
                    )
                data = resp.json()
                token = data.get("token")
                expires_at = data.get("expires_at")  # ISO-8601 string
                if not token or not expires_at:
                    raise RuntimeError("GitHub API did not return a token or expiration time")

                # GitHub returns ISO time; parse conservatively to epoch
                exp_epoch = _iso8601_to_epoch(expires_at) if isinstance(expires_at, str) else None
                # Fallback: 50 minutes from now if parsing fails (installation tokens are ~1h)
                self._installation_token = token
                self._installation_token_exp = exp_epoch or (int(time.time()) + 50 * 60)

        await report(100.0, "Installation token ready")
        return self._installation_token  # type: ignore[return-value]

    # ------------------------
    # Internals
    # ------------------------
    def _generate_jwt(self) -> str:
        """Create an RS256-signed JWT suitable for GitHub App authentication.

        Follows GitHub guidance: iat up to 60s in the past; exp within 10 minutes.
        """
        if load_pem_private_key is None or padding is None or hashes is None:
            raise RuntimeError(
                "cryptography is required to generate GitHub App JWTs. Please install 'cryptography'."
            )

        key = load_pem_private_key(self.private_key_pem.encode("utf-8"), password=None)

        header = {"alg": "RS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "iat": now - 60,  # allow small clock skew
            "exp": now + 9 * 60,  # 9 minutes
            "iss": self.app_id,
        }

        signing_input = ".".join(
            _b64url(json.dumps(obj, separators=(",", ":")).encode("utf-8"))
            for obj in (header, payload)
        )

        signature = key.sign(
            signing_input.encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return f"{signing_input}.{_b64url(signature)}"

    def _get_app_client(self, jwt_token: str) -> httpx.AsyncClient:
        """Construct an authenticated AsyncClient for GitHub App API using JWT token with Bearer scheme."""
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        timeout = httpx.Timeout(30.0)
        return httpx.AsyncClient(base_url=self.api_base_url, headers=headers, timeout=timeout)

    def _get_installation_client(self, installation_token: str) -> httpx.AsyncClient:
        """Construct an authenticated AsyncClient for GitHub API using installation token with token scheme."""
        headers = {
            "Authorization": f"token {installation_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        timeout = httpx.Timeout(30.0)
        return httpx.AsyncClient(base_url=self.api_base_url, headers=headers, timeout=timeout)

    @staticmethod
    def _raise_if_cancelled(cancel_event: asyncio.Event | None) -> None:
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Operation cancelled by user")


# ------------------------
# Helpers
# ------------------------


def _b64url(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    s = base64.urlsafe_b64encode(data).decode("ascii")
    return s.rstrip("=")


def _iso8601_to_epoch(value: str) -> int | None:
    """Parse a strict subset of ISO-8601 Zulu timestamps to epoch seconds.

    Example: 2023-01-01T12:34:56Z
    """
    try:
        if not value.endswith("Z"):
            return None
        date, timepart = value[:-1].split("T", 1)
        year, month, day = (int(x) for x in date.split("-", 2))
        hh, mm, ss = (int(x) for x in timepart.split(":", 2))
        # Use time.gmtime-like conversion (assume UTC)
        import calendar

        return int(calendar.timegm((year, month, day, hh, mm, ss, 0, 0, 0)))
    except Exception:  # pragma: no cover - robustness
        logger.debug("Failed to parse ISO8601 timestamp: %s", value, exc_info=True)
        return None
