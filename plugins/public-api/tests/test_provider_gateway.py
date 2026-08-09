from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, Request

from determinflow_plugin_public_api.backend.provider import CoreProviderGateway


def test_gateway_uses_existing_provider_http_contract() -> None:
    async def scenario() -> None:
        app = FastAPI()
        providers: dict[str, dict[str, Any]] = {
            "deepseek": {
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "deepseek-key",
                "models": ["deepseek-chat"],
            }
        }
        priority: list[str] = []

        @app.get("/api/model-providers")
        async def list_providers():
            masked = {
                provider_id: {
                    **config,
                    "api_key": "***" if config.get("api_key") else "",
                }
                for provider_id, config in providers.items()
            }
            return {"providers": masked}

        @app.post("/api/model-providers")
        async def add_provider(payload: dict[str, Any], request: Request):
            assert request.headers["x-determinflow-provider-owner"] == "public-api"
            provider_id = payload.pop("provider_id")
            providers[provider_id] = payload
            return {"success": True}

        @app.put("/api/model-providers/{provider_id}")
        async def update_provider(
            provider_id: str,
            payload: dict[str, Any],
            request: Request,
        ):
            assert request.headers["x-determinflow-provider-owner"] == "public-api"
            providers[provider_id].update(payload)
            return {"success": True}

        @app.put("/api/model-providers/{provider_id}/priority")
        async def prioritize_provider(provider_id: str, request: Request):
            assert request.headers["x-determinflow-provider-owner"] == "public-api"
            priority.append(provider_id)
            return {"success": True}

        @app.delete("/api/model-providers/{provider_id}")
        async def delete_provider(provider_id: str, request: Request):
            assert request.headers["x-determinflow-provider-owner"] == "public-api"
            providers.pop(provider_id, None)
            return {"success": True}

        gateway = CoreProviderGateway(app, owner="public-api")
        credential = {
            "provider_id": "determinflow-public",
            "base_url": "https://relay.example.test/v1",
            "api_key": "public-key",
            "models": ["public-model"],
            "models_config": {
                "public-model": {
                    "provider_type": "openai_compatible",
                }
            },
        }
        await gateway.apply(credential)

        assert await gateway.is_usable("determinflow-public") is True
        assert providers["determinflow-public"]["api_key"] == "public-key"
        assert providers["determinflow-public"]["provider_type"] == (
            "openai_compatible"
        )
        assert providers["determinflow-public"]["managed_by"] == "public-api"
        assert providers["determinflow-public"]["error_messages"] == {
            "quota_exhausted": "公益模型额度已用完，请稍后再试",
            "rate_limited": "公益模型请求过于频繁，请稍后再试",
            "authentication_failed": "公益模型授权已失效",
            "service_unavailable": "公益模型暂时不可用，请稍后再试",
            "unknown": "公益模型调用失败，请稍后再试",
        }
        assert providers["determinflow-public"]["models_config"] == (
            credential["models_config"]
        )
        assert priority == ["determinflow-public"]

        credential["api_key"] = "renewed-key"
        await gateway.apply(credential)
        assert providers["determinflow-public"]["api_key"] == "renewed-key"
        assert priority == ["determinflow-public", "determinflow-public"]

        await gateway.remove("determinflow-public")
        assert "determinflow-public" not in providers

    asyncio.run(scenario())
