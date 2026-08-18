"""Dynamic public model catalog served by the relay."""

from __future__ import annotations

from typing import Any

import httpx


class CatalogRequestError(RuntimeError):
    """The relay mapping was unavailable or contained no usable model."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


_PROVIDER_TYPES = {
    "deepseek",
    "mimo",
    "qwen",
    "openai",
    "openai_compatible",
    "anthropic",
}


class PublicModelCatalogClient:
    """Fetch the credential-scoped model, Provider, and pricing catalog."""

    def __init__(
        self,
        *,
        app_version: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.app_version = app_version
        self.transport = transport

    async def fetch(
        self,
        relay_base_url: str,
        api_key: str,
        allowed_models: list[str],
    ) -> dict[str, Any]:
        normalized_base_url = relay_base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(6.0, connect=3.0),
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"{normalized_base_url}/public-models",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "User-Agent": (
                            f"DeterminFlow-Public-API-Plugin/{self.app_version}"
                        ),
                    },
                )
        except httpx.RequestError as exc:
            raise CatalogRequestError("暂时无法获取公益模型目录") from exc
        if response.status_code >= 400:
            raise CatalogRequestError("公益模型目录暂不可用")
        try:
            body = response.json()
        except ValueError as exc:
            raise CatalogRequestError("公益模型目录格式无效") from exc
        if not isinstance(body, dict):
            raise CatalogRequestError("公益模型目录格式无效")
        return self._normalize(body, allowed_models)

    def _normalize(
        self,
        body: dict[str, Any],
        allowed_models: list[str],
    ) -> dict[str, Any]:
        if body.get("unit") != "per_million_tokens":
            raise CatalogRequestError("公益模型目录计价单位无效")
        raw_models = body.get("models")
        raw_catalog = body.get("catalog_models")
        has_full_catalog = raw_catalog is not None
        if not isinstance(raw_models, list) or (
            has_full_catalog and not isinstance(raw_catalog, list)
        ):
            raise CatalogRequestError("公益模型目录格式无效")
        if raw_catalog is None:
            raw_catalog = raw_models

        allowed = set(allowed_models)
        accessible = {
            item.get("id")
            for item in raw_models
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item.get("id") in allowed
        }
        ordered_models: list[str] = []
        models_config: dict[str, dict[str, Any]] = {}
        model_catalog: list[dict[str, Any]] = []
        for item in raw_catalog:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            display_name = item.get("display_name")
            provider_type = item.get("provider_type")
            prices = item.get("prices")
            if (
                not isinstance(model_id, str)
                or not isinstance(display_name, str)
                or not display_name.strip()
                or not isinstance(provider_type, str)
                or not isinstance(prices, list)
                or not prices
            ):
                continue
            provider_type = provider_type.strip().lower()
            if provider_type not in _PROVIDER_TYPES:
                continue
            normalized_prices: list[dict[str, Any]] = []
            for price in prices:
                if not isinstance(price, dict):
                    normalized_prices = []
                    break
                label = price.get("label")
                input_price = price.get("input_price")
                cache_hit_price = price.get("cache_hit_price")
                output_price = price.get("output_price")
                currency = price.get("currency")
                price_basis = price.get("price_basis")
                original_input_price = price.get("original_input_price")
                original_cache_hit_price = price.get("original_cache_hit_price")
                original_output_price = price.get("original_output_price")
                original_currency = price.get("original_currency")
                if price_basis is None:
                    price_basis = "converted" if currency == "USD" else "domestic"
                if (
                    (label is not None and not isinstance(label, str))
                    or not isinstance(input_price, (int, float))
                    or isinstance(input_price, bool)
                    or input_price < 0
                    or (
                        cache_hit_price is not None
                        and (
                            not isinstance(cache_hit_price, (int, float))
                            or isinstance(cache_hit_price, bool)
                            or cache_hit_price < 0
                        )
                    )
                    or not isinstance(output_price, (int, float))
                    or isinstance(output_price, bool)
                    or output_price < 0
                    or currency not in {"CNY", "USD"}
                    or price_basis not in {"domestic", "converted"}
                ):
                    normalized_prices = []
                    break
                if price_basis == "converted" and (
                    currency != "CNY"
                    or not isinstance(original_input_price, (int, float))
                    or isinstance(original_input_price, bool)
                    or original_input_price < 0
                    or not isinstance(original_output_price, (int, float))
                    or isinstance(original_output_price, bool)
                    or original_output_price < 0
                    or original_currency != "USD"
                    or (
                        cache_hit_price is not None
                        and (
                            not isinstance(original_cache_hit_price, (int, float))
                            or isinstance(original_cache_hit_price, bool)
                            or original_cache_hit_price < 0
                        )
                    )
                    or (
                        cache_hit_price is None
                        and original_cache_hit_price is not None
                    )
                ):
                    normalized_prices = []
                    break
                normalized_prices.append(
                    {
                        "label": label.strip() if isinstance(label, str) else None,
                        "input_price": float(input_price),
                        "cache_hit_price": (
                            float(cache_hit_price)
                            if cache_hit_price is not None
                            else None
                        ),
                        "output_price": float(output_price),
                        "currency": currency,
                        "price_basis": price_basis,
                        "original_input_price": (
                            float(original_input_price)
                            if price_basis == "converted"
                            else None
                        ),
                        "original_cache_hit_price": (
                            float(original_cache_hit_price)
                            if price_basis == "converted"
                            and original_cache_hit_price is not None
                            else None
                        ),
                        "original_output_price": (
                            float(original_output_price)
                            if price_basis == "converted"
                            else None
                        ),
                        "original_currency": (
                            original_currency if price_basis == "converted" else None
                        ),
                    }
                )
            if not normalized_prices:
                continue
            model_catalog.append(
                {
                    "id": model_id,
                    "display_name": display_name.strip(),
                    "prices": normalized_prices,
                }
            )
            if model_id in accessible:
                ordered_models.append(model_id)
                models_config[model_id] = {"provider_type": provider_type}

        if not has_full_catalog:
            model_catalog = [
                model for model in model_catalog if model["id"] in accessible
            ]

        if not ordered_models:
            raise CatalogRequestError("当前凭据没有可用的公益模型")
        return {
            "models": ordered_models,
            "models_config": models_config,
            "model_catalog": model_catalog,
        }
