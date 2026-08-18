from __future__ import annotations

import asyncio

import httpx
import pytest
from determinflow_plugin_public_api.backend.catalog import (
    CatalogRequestError,
    PublicModelCatalogClient,
)


def test_catalog_filters_credential_models_and_maps_provider_types() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/public-models"
            assert request.headers.get("authorization") == "Bearer test-public-key"
            return httpx.Response(
                200,
                json={
                    "unit": "per_million_tokens",
                    "models": [
                        {
                            "id": "gpt-5.6-luna",
                            "display_name": "GPT 5.6 Luna",
                            "provider_type": "openai",
                            "prices": [
                                {
                                    "label": "≤ 272K",
                                    "input_price": 1.46,
                                    "cache_hit_price": 0.146,
                                    "output_price": 8.76,
                                    "currency": "CNY",
                                    "price_basis": "converted",
                                    "original_input_price": 0.2,
                                    "original_cache_hit_price": 0.02,
                                    "original_output_price": 1.2,
                                    "original_currency": "USD",
                                }
                            ],
                        },
                    ],
                    "catalog_models": [
                        {
                            "id": "not-allowed",
                            "display_name": "Not allowed",
                            "provider_type": "anthropic",
                            "prices": [
                                {
                                    "input_price": 1,
                                    "output_price": 2,
                                    "currency": "CNY",
                                }
                            ],
                        },
                        {
                            "id": "gpt-5.6-luna",
                            "display_name": "GPT 5.6 Luna",
                            "provider_type": "openai",
                            "prices": [
                                {
                                    "label": "≤ 272K",
                                    "input_price": 1.46,
                                    "cache_hit_price": 0.146,
                                    "output_price": 8.76,
                                    "currency": "CNY",
                                    "price_basis": "converted",
                                    "original_input_price": 0.2,
                                    "original_cache_hit_price": 0.02,
                                    "original_output_price": 1.2,
                                    "original_currency": "USD",
                                }
                            ],
                        },
                    ],
                },
            )

        client = PublicModelCatalogClient(
            app_version="0.1.6",
            transport=httpx.MockTransport(handler),
        )
        catalog = await client.fetch(
            "https://relay.example.test/v1",
            "test-public-key",
            ["gpt-5.6-luna"],
        )

        assert catalog["models"] == ["gpt-5.6-luna"]
        assert catalog["models_config"] == {"gpt-5.6-luna": {"provider_type": "openai"}}
        assert catalog["model_catalog"] == [
            {
                "id": "not-allowed",
                "display_name": "Not allowed",
                "prices": [
                    {
                        "label": None,
                        "input_price": 1.0,
                        "cache_hit_price": None,
                        "output_price": 2.0,
                        "currency": "CNY",
                        "price_basis": "domestic",
                        "original_input_price": None,
                        "original_cache_hit_price": None,
                        "original_output_price": None,
                        "original_currency": None,
                    }
                ],
            },
            {
                "id": "gpt-5.6-luna",
                "display_name": "GPT 5.6 Luna",
                "prices": [
                    {
                        "label": "≤ 272K",
                        "input_price": 1.46,
                        "cache_hit_price": 0.146,
                        "output_price": 8.76,
                        "currency": "CNY",
                        "price_basis": "converted",
                        "original_input_price": 0.2,
                        "original_cache_hit_price": 0.02,
                        "original_output_price": 1.2,
                        "original_currency": "USD",
                    }
                ],
            }
        ]

    asyncio.run(scenario())


def test_catalog_keeps_legacy_response_credential_scoped() -> None:
    client = PublicModelCatalogClient(app_version="0.1.32")
    catalog = client._normalize(
        {
            "unit": "per_million_tokens",
            "models": [
                {
                    "id": "not-allowed",
                    "display_name": "Not allowed",
                    "provider_type": "anthropic",
                    "prices": [{"input_price": 1, "output_price": 2, "currency": "CNY"}],
                },
                {
                    "id": "allowed",
                    "display_name": "Allowed",
                    "provider_type": "openai",
                    "prices": [{"input_price": 1, "output_price": 2, "currency": "CNY"}],
                },
            ],
        },
        ["allowed"],
    )

    assert catalog["models"] == ["allowed"]
    assert [item["id"] for item in catalog["model_catalog"]] == ["allowed"]


def test_catalog_rejects_catalog_without_supported_provider_mapping() -> None:
    async def scenario() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "unit": "per_million_tokens",
                    "models": [
                        {
                            "id": "public-model",
                            "display_name": "Public model",
                            "provider_type": "unsupported",
                            "prices": [
                                {
                                    "input_price": 1,
                                    "output_price": 2,
                                    "currency": "USD",
                                }
                            ],
                        }
                    ],
                },
            )

        client = PublicModelCatalogClient(
            app_version="0.1.6",
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(CatalogRequestError, match="没有可用"):
            await client.fetch(
                "https://relay.example.test/v1",
                "test-public-key",
                ["public-model"],
            )

    asyncio.run(scenario())
