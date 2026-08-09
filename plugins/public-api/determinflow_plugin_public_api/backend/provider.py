"""Adapter for DeterminFlow's existing public Provider HTTP contract."""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import quote

import httpx


PUBLIC_PROVIDER_ERROR_MESSAGES = {
    "quota_exhausted": "公益模型额度已用完，请稍后再试",
    "rate_limited": "公益模型请求过于频繁，请稍后再试",
    "authentication_failed": "公益模型授权已失效",
    "service_unavailable": "公益模型暂时不可用，请稍后再试",
    "unknown": "公益模型调用失败，请稍后再试",
}


class ProviderRequestError(RuntimeError):
    """The Core Provider contract could not apply the managed credential."""


class ProviderGateway(Protocol):
    async def is_usable(self, provider_id: str) -> bool: ...

    async def apply(self, credential: dict[str, Any]) -> None: ...

    async def remove(self, provider_id: str) -> None: ...


class CoreProviderGateway:
    """Use Core's stable HTTP API without importing model-manager internals."""

    def __init__(self, app: Any, *, owner: str) -> None:
        self._transport = httpx.ASGITransport(app=app)
        self._owner = owner

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(
            transport=self._transport,
            base_url="http://determinflow.local",
        ) as client:
            response = await client.request(
                method,
                path,
                json=payload,
                headers={"X-DeterminFlow-Provider-Owner": self._owner},
            )
        if response.status_code >= 400:
            raise ProviderRequestError(f"Provider API 返回 HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderRequestError("Provider API 未返回 JSON") from exc
        if not isinstance(body, dict):
            raise ProviderRequestError("Provider API 返回格式无效")
        return body

    async def _providers(self) -> dict[str, dict[str, Any]]:
        body = await self._request("GET", "/api/model-providers")
        providers = body.get("providers")
        if not isinstance(providers, dict):
            raise ProviderRequestError("Provider API 缺少 providers")
        return {
            str(provider_id): dict(config)
            for provider_id, config in providers.items()
            if isinstance(config, dict)
        }

    async def is_usable(self, provider_id: str) -> bool:
        provider = (await self._providers()).get(provider_id) or {}
        return bool(provider.get("api_key") and provider.get("base_url"))

    async def apply(self, credential: dict[str, Any]) -> None:
        providers = await self._providers()
        provider_id = credential["provider_id"]
        provider = {
            "name": credential.get("provider_display_name") or "笔枢公益模型",
            "provider_type": "openai_compatible",
            "base_url": credential["base_url"],
            "api_key": credential["api_key"],
            "models": credential["models"],
            "maxContextTokens": 128000,
            "models_config": credential["models_config"],
            "hyperparameter_values": {},
            "error_messages": PUBLIC_PROVIDER_ERROR_MESSAGES,
            "managed_by": self._owner,
        }
        encoded = quote(provider_id, safe="")
        if provider_id in providers:
            await self._request(
                "PUT",
                f"/api/model-providers/{encoded}",
                payload=provider,
            )
        else:
            await self._request(
                "POST",
                "/api/model-providers",
                payload={"provider_id": provider_id, **provider},
            )
        await self._request(
            "PUT",
            f"/api/model-providers/{encoded}/priority",
        )

    async def remove(self, provider_id: str) -> None:
        encoded = quote(provider_id, safe="")
        await self._request("DELETE", f"/api/model-providers/{encoded}")
