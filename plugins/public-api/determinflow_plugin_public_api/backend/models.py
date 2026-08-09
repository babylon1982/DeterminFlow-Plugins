"""Public API Plugin request and status contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PublicApiQuota(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remaining_usd: float = Field(ge=0)
    total_limit_usd: float = Field(ge=0)
    total_used_usd: float = Field(ge=0)
    daily_limit_usd: float = Field(ge=0)
    daily_used_usd: float = Field(ge=0)
    weekly_limit_usd: float = Field(ge=0)
    weekly_used_usd: float = Field(ge=0)
    measured_at: datetime

    @model_validator(mode="after")
    def validate_measurement(self) -> PublicApiQuota:
        if self.measured_at.tzinfo is None or self.measured_at.utcoffset() is None:
            raise ValueError("measured_at must include a timezone")
        if self.remaining_usd > self.total_limit_usd:
            raise ValueError("remaining_usd must not exceed total_limit_usd")
        return self


class PublicApiClientUI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_enabled: bool = True
    login_enabled: bool = False
    payment_enabled: bool = False
    header_recharge_enabled: bool = False
    model_page_recharge_enabled: bool = False
    payment_url: str | None = None
    recharge_ratio: float = Field(default=0.8, gt=0, le=1)
    provider_display_name: str = Field(default="笔枢公益模型", min_length=1, max_length=80)
    attribution: str = Field(default="由笔枢写作（网页版）免费提供", min_length=1, max_length=160)
    service_notice: str = Field(default=(
        "本服务由笔枢写作公益提供。上游来自第三方，不保证配额、稳定性与数据安全，"
        "仅供体验项目使用；长期使用强烈建议自行购买模型官方 API。"
    ), min_length=1, max_length=600)
    official_url: str = "https://bishuxiezuo.cn/"
    top_up_title: str = Field(default="笔枢点数充值", min_length=1, max_length=120)
    top_up_subtitle: str = Field(default="充值金额进入当前账号。", min_length=1, max_length=240)
    top_up_ratio_notice: str = Field(default="当前比例 {ratio}。", min_length=1, max_length=240)

    @field_validator("official_url")
    @classmethod
    def validate_official_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("official_url must use HTTPS")
        return value


class PublicModelPriceTier(BaseModel):
    label: str | None = None
    input_price: float = Field(ge=0)
    cache_hit_price: float | None = Field(default=None, ge=0)
    output_price: float = Field(ge=0)
    currency: Literal["CNY", "USD"]
    price_basis: Literal["domestic", "converted"] = "domestic"
    original_input_price: float | None = Field(default=None, ge=0)
    original_cache_hit_price: float | None = Field(default=None, ge=0)
    original_output_price: float | None = Field(default=None, ge=0)
    original_currency: Literal["USD"] | None = None


class PublicModelCatalogItem(BaseModel):
    id: str
    display_name: str
    prices: list[PublicModelPriceTier]


class HeaderStatusMetric(BaseModel):
    label: str
    value: str


class HeaderStatusAction(BaseModel):
    id: str
    label: str
    kind: Literal["manage", "link", "page", "request"]
    href: str | None = None
    endpoint: str | None = None
    method: Literal["POST", "DELETE"] | None = None


class HeaderStatus(BaseModel):
    visible: bool
    label: str
    value: str
    title: str
    summary: str
    summary_href: str | None = None
    tone: Literal["normal", "attention", "critical", "stale"]
    metrics: list[HeaderStatusMetric]
    metadata: list[HeaderStatusMetric]
    actions: list[HeaderStatusAction]
    refresh_after_ms: int | None = Field(default=None, ge=500, le=60_000)
    updated_at: datetime


class PublicApiStatus(BaseModel):
    state: Literal["disabled", "active", "degraded", "unavailable"]
    signed_in: bool
    login_pending: bool = False
    access_tier: Literal["anonymous", "authenticated", "restricted"] | None
    provider_id: str | None
    models: list[str]
    model_catalog: list[PublicModelCatalogItem]
    expires_at: datetime | None
    renewal_due_at: datetime | None
    last_attempt_at: datetime | None
    last_error: str | None
    quota: PublicApiQuota | None
    account_balance_usd: float | None
    account_display_name: str | None = Field(default=None, max_length=80)
    login_endpoint: str = "/api/public-api/login"
    ui: PublicApiClientUI
    header_status: HeaderStatus | None
