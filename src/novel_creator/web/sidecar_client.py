"""Casdoor Auth Sidecar HTTP client (async).

Mirrors the Go SidecarClient in PinHaoClaw (server/sidecar.go).
Calls the sidecar's /api/auth/verify, login, logout, etc. endpoints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from novel_creator.config import settings

logger = logging.getLogger("novel_creator.web.sidecar")


@dataclass
class SidecarIdentity:
    """User identity returned by the auth sidecar."""
    sub: str = ""
    username: str = ""
    display_name: str = ""
    email: str = ""
    avatar: str = ""
    organization: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "SidecarIdentity":
        return cls(
            sub=data.get("sub", ""),
            username=data.get("username", ""),
            display_name=data.get("display_name", ""),
            email=data.get("email", ""),
            avatar=data.get("avatar", ""),
            organization=data.get("organization", ""),
        )


@dataclass
class VerifyResult:
    """Result of sidecar verify call."""
    ok: bool
    token: str = ""
    identity: SidecarIdentity | None = None
    error: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "VerifyResult":
        identity = None
        if data.get("identity"):
            identity = SidecarIdentity.from_dict(data["identity"])
        return cls(
            ok=data.get("ok", False),
            token=data.get("token", ""),
            identity=identity,
            error=data.get("error", ""),
        )


class SidecarClient:
    """Async HTTP client for casdoor-auth-sidecar."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = (base_url or settings.auth_sidecar_url).rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self._client

    # ── Verify ────────────────────────────────────────

    async def verify(self, token: str) -> VerifyResult:
        """POST /api/auth/verify — validate token, return identity.

        Called by auth dependency on every protected request.
        """
        if not self.base_url:
            return VerifyResult(ok=False, error="sidecar URL not configured")

        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/api/auth/verify",
                json={"token": token},
                headers={"X-User-Token": token},
            )
            data = resp.json()
            result = VerifyResult.from_dict(data)
            if resp.status_code != 200:
                result.ok = False
                if not result.error:
                    result.error = data.get("error", f"verify failed ({resp.status_code})")
            return result
        except httpx.TimeoutException:
            logger.warning("sidecar verify timeout")
            return VerifyResult(ok=False, error="sidecar unreachable: timeout")
        except Exception as e:
            logger.warning("sidecar verify error: %s", e)
            return VerifyResult(ok=False, error=f"sidecar unreachable: {e}")

    # ── Login / OAuth proxy ───────────────────────────

    async def proxy_get(
        self, path: str, params: dict | None = None, headers: dict | None = None,
    ) -> httpx.Response | None:
        """Proxy a GET request to the sidecar (for login, callback, etc.)."""
        if not self.base_url:
            return None
        client = await self._get_client()
        return await client.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            follow_redirects=False,  # don't follow OAuth redirects
        )

    async def proxy_post(
        self, path: str, json_data: dict | None = None,
        headers: dict | None = None, content: bytes | None = None,
    ) -> httpx.Response | None:
        """Proxy a POST request to the sidecar."""
        if not self.base_url:
            return None
        client = await self._get_client()
        return await client.post(
            f"{self.base_url}{path}",
            json=json_data,
            content=content,
            headers=headers,
            follow_redirects=False,
        )

    # ── Logout ────────────────────────────────────────

    async def logout(self, token: str) -> bool:
        """POST /api/auth/logout — destroy sidecar session."""
        result = await self.verify(token)
        if not result.ok:
            return False
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/api/auth/logout",
                json={"token": token},
                headers={"X-User-Token": token},
            )
            return resp.status_code < 400
        except Exception:
            return False

    # ── Refresh ───────────────────────────────────────

    async def refresh(self, token: str) -> VerifyResult:
        """POST /api/auth/refresh — refresh sidecar session."""
        if not self.base_url:
            return VerifyResult(ok=False, error="sidecar URL not configured")
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/api/auth/refresh",
                json={"token": token},
                headers={"X-User-Token": token},
            )
            data = resp.json()
            return VerifyResult.from_dict(data)
        except Exception as e:
            return VerifyResult(ok=False, error=str(e))

    # ── Config ────────────────────────────────────────

    async def get_app_config(self) -> dict | None:
        """GET /api/app/config — get sidecar app config (org, app name)."""
        if not self.base_url:
            return None
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/api/app/config")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None


# Singleton
_sidecar: SidecarClient | None = None


def get_sidecar() -> SidecarClient:
    global _sidecar
    if _sidecar is None:
        _sidecar = SidecarClient()
    return _sidecar
