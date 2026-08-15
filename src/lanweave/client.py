"""Small, testable client for the local UniFi Network API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv


class CredentialsError(ValueError):
    """Raised when controller credentials are absent or unsafe."""


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise CredentialsError(f"{name} must be true or false")


def _reject_unresolved(values: dict[str, str]) -> None:
    unresolved = sorted(name for name, value in values.items() if value.startswith("op://"))
    if unresolved:
        raise CredentialsError(
            "unresolved secret-manager reference in: "
            + ", ".join(unresolved)
            + ". Resolve it before starting the tool."
        )


@dataclass(frozen=True)
class ControllerSettings:
    """Connection settings loaded from environment variables."""

    host: str
    site: str = "default"
    verify_tls: bool = True
    api_key: str = ""
    username: str = ""
    password: str = ""

    @classmethod
    def from_env(cls) -> ControllerSettings:
        load_dotenv()
        settings = cls(
            host=os.getenv("UNIFI_HOST", "").rstrip("/"),
            site=os.getenv("UNIFI_SITE", "default"),
            verify_tls=_env_bool("UNIFI_VERIFY_TLS", True),
            api_key=os.getenv("UNIFI_API_KEY", ""),
            username=os.getenv("UNIFI_USER", ""),
            password=os.getenv("UNIFI_PASS", ""),
        )
        _reject_unresolved(
            {
                "UNIFI_API_KEY": settings.api_key,
                "UNIFI_USER": settings.username,
                "UNIFI_PASS": settings.password,
            }
        )
        if not settings.host:
            raise CredentialsError("UNIFI_HOST is required")
        if not settings.api_key and not (settings.username and settings.password):
            raise CredentialsError(
                "set UNIFI_API_KEY or both UNIFI_USER and UNIFI_PASS"
            )
        return settings


class UniFiClient:
    """HTTP client with API-key and session authentication support."""

    def __init__(
        self,
        settings: ControllerSettings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._http = httpx.Client(
            base_url=settings.host,
            verify=settings.verify_tls,
            timeout=15.0,
            follow_redirects=True,
            transport=transport,
        )
        self._csrf_token: str | None = None

    def __enter__(self) -> UniFiClient:
        if not self.settings.api_key:
            self.login()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def login(self) -> None:
        response = self._http.post(
            "/api/auth/login",
            json={
                "username": self.settings.username,
                "password": self.settings.password,
            },
        )
        response.raise_for_status()
        self._csrf_token = response.headers.get("X-CSRF-Token") or response.cookies.get("TOKEN")

    def site_url(self, path: str) -> str:
        return f"/proxy/network/api/s/{self.settings.site}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.settings.api_key:
            headers["X-API-Key"] = self.settings.api_key
        elif self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token
        return headers

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = urljoin("/", path.lstrip("/"))
        response = self._http.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code == 401 and not self.settings.api_key:
            self.login()
            response = self._http.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(
                f"UniFi API returned HTTP {response.status_code} for {method} {path}"
            )
        if not response.content:
            return None
        payload = response.json()
        if isinstance(payload, dict):
            return payload.get("data", payload)
        return payload

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return self.request("POST", path, json=json, **kwargs)

    def put(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return self.request("PUT", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    def networks(self) -> list[dict[str, Any]]:
        return self.get(self.site_url("rest/networkconf")) or []

    def wlans(self) -> list[dict[str, Any]]:
        return self.get(self.site_url("rest/wlanconf")) or []

    def devices(self) -> list[dict[str, Any]]:
        return self.get(self.site_url("stat/device")) or []

    def clients(self) -> list[dict[str, Any]]:
        return self.get(self.site_url("stat/sta")) or []

    def health(self) -> list[dict[str, Any]]:
        return self.get(self.site_url("stat/health")) or []
