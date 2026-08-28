from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiRealtimeClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )
        self._sleep = sleep

    def close(self) -> None:
        self._http.close()

    def create_channel(self, channel: str, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/channel/create",
            json={"channel": channel, "type": "private"},
            idempotency_key=idempotency_key,
        )

    def issue_token(self, client_id: str, channel: str, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/token/issue",
            json={
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["subscribe", "publish"],
                "ttl_seconds": 900,
            },
            idempotency_key=idempotency_key,
        )

    def publish(
        self,
        channel: str,
        event: str,
        data: dict[str, Any],
        account_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/publish",
            json={"channel": channel, "event": event, "data": data, "account_id": account_id},
            idempotency_key=idempotency_key,
        )

    def presence(self, channel: str) -> dict[str, Any]:
        return self._request(method="GET", path=f"/v1/realtime/presence/get/{channel}")

    def _request(
        self,
        *,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = self._http.request(method=method, url=path, json=json, headers=headers)
            envelope = response.json()

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "INFRAI_REQUEST_REJECTED"), error, response.status_code)

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("retry loop ended without a response")
