const elements = {
  summary: document.querySelector("#summary"),
  state: document.querySelector("#state"),
  tier: document.querySelector("#tier"),
  available: document.querySelector("#available"),
  publicBenefit: document.querySelector("#public-benefit"),
  dailyBenefit: document.querySelector("#daily-benefit"),
  weeklyBenefit: document.querySelector("#weekly-benefit"),
  wallet: document.querySelector("#wallet"),
  expiry: document.querySelector("#expiry"),
  modelCount: document.querySelector("#model-count"),
  catalogBody: document.querySelector("#catalog-body"),
  error: document.querySelector("#error"),
  renew: document.querySelector("#renew"),
  account: document.querySelector("#account"),
  payment: document.querySelector("#payment"),
  pageTitle: document.querySelector("#page-title"),
  officialLink: document.querySelector("#official-link"),
  serviceNotice: document.querySelector("#service-notice"),
};

let currentStatus = null;
let busy = false;
let polling = false;

async function request(path, options = {}) {
  const response = await fetch(`/api/public-api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let message = "公益模型服务暂不可用，请稍后重试";
    try {
      const body = await response.json();
      if (typeof body.detail === "string" && body.detail) message = body.detail;
    } catch (_error) {
      // Keep the user-safe fallback.
    }
    throw new Error(message);
  }
  return response.json();
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function stateLabel(state) {
  return {
    active: "可用",
    degraded: "更新异常",
    unavailable: "不可用",
    disabled: "未启用",
  }[state] || "未知";
}

function accessLabel(status) {
  const identity = status.signed_in ? "已登录" : "匿名";
  const quotaState = {
    anonymous: "标准额度",
    authenticated: "登录权益",
    restricted: "受限额度",
  }[status.access_tier] || "额度未知";
  return `${identity} · ${quotaState}`;
}

function money(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? `¥${value.toFixed(2)}`
    : "—";
}

function remaining(limit, used) {
  if (!Number.isFinite(limit) || !Number.isFinite(used)) return null;
  return Math.max(0, limit - used);
}

function catalogPrice(value, currency) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const symbol = currency === "USD" ? "$" : "¥";
  return `${symbol}${new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value)}`;
}

function renderPriceCell(prices, field) {
  const cell = document.createElement("td");
  cell.className = "price-cell";
  for (const tier of prices) {
    const line = document.createElement("div");
    line.className = "price-line";
    const value = document.createElement("span");
    value.className = "price-value";
    value.textContent = catalogPrice(tier[field], tier.currency);
    if (tier.price_basis === "converted" && Number.isFinite(tier[field])) {
      const originalField = {
        input_price: "original_input_price",
        cache_hit_price: "original_cache_hit_price",
        output_price: "original_output_price",
      }[field];
      const original = document.createElement("span");
      original.className = "price-original";
      original.textContent = `(${catalogPrice(
        tier[originalField],
        tier.original_currency,
      )})`;
      value.append(original);
    }
    line.append(value);
    cell.append(line);
  }
  return cell;
}

function renderModelCell(model) {
  const cell = document.createElement("td");
  const content = document.createElement("div");
  content.className = "model-cell-content";
  const identity = document.createElement("div");
  identity.className = "model-identity";
  const name = document.createElement("strong");
  name.textContent = model.display_name;
  const id = document.createElement("span");
  id.className = "model-id";
  id.textContent = model.id;
  identity.append(name, id);
  content.append(identity);

  const labels = model.prices
    .map((tier) => tier.label || "")
    .filter(Boolean);
  if (labels.length) {
    const tiers = document.createElement("div");
    tiers.className = "model-tiers";
    for (const text of labels) {
      const label = document.createElement("span");
      label.className = "tier-label";
      label.textContent = text;
      tiers.append(label);
    }
    content.append(tiers);
  }
  cell.append(content);
  return cell;
}

function renderCatalog(models) {
  elements.catalogBody.replaceChildren();
  if (!Array.isArray(models) || models.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.className = "empty";
    cell.textContent = "当前分组暂无可用模型";
    row.append(cell);
    elements.catalogBody.append(row);
    return;
  }
  for (const model of models) {
    const row = document.createElement("tr");
    row.append(
      renderModelCell(model),
      renderPriceCell(model.prices, "input_price"),
      renderPriceCell(model.prices, "cache_hit_price"),
      renderPriceCell(model.prices, "output_price"),
    );
    elements.catalogBody.append(row);
  }
}

function render(status) {
  currentStatus = status;
  const available = status.state === "active" || status.state === "degraded";
  elements.state.textContent = stateLabel(status.state);
  elements.state.dataset.state = status.state;
  const ui = status.ui || {};
  elements.pageTitle.textContent = ui.provider_display_name || "笔枢公益模型";
  elements.officialLink.textContent = ui.attribution || "由笔枢写作（网页版）免费提供";
  elements.officialLink.href = isSafeOfficialUrl(ui.official_url)
    ? ui.official_url
    : "https://bishuxiezuo.cn/";
  elements.serviceNotice.textContent = ui.service_notice ? ` ${ui.service_notice}` : "";
  elements.summary.textContent = available
    ? (status.login_pending
      ? "请在浏览器完成笔枢登录"
      : (status.signed_in
        ? `已登录${status.account_display_name ? ` · ${status.account_display_name}` : "笔枢账号"}`
        : `匿名体验 · ${status.models.length} 个可用模型`))
    : (status.last_error || "暂时无法获取公益模型额度");
  elements.tier.textContent = accessLabel(status);
  const benefitAvailable = status.quota?.remaining_usd;
  const wallet = status.signed_in ? status.account_balance_usd : null;
  const availableBalance = Number.isFinite(benefitAvailable)
    ? benefitAvailable + (Number.isFinite(wallet) ? wallet : 0)
    : null;
  elements.available.textContent = money(availableBalance);
  elements.publicBenefit.textContent = money(benefitAvailable);
  elements.dailyBenefit.textContent = money(remaining(
    status.quota?.daily_limit_usd,
    status.quota?.daily_used_usd,
  ));
  elements.weeklyBenefit.textContent = money(remaining(
    status.quota?.weekly_limit_usd,
    status.quota?.weekly_used_usd,
  ));
  elements.wallet.textContent = money(wallet);
  elements.expiry.textContent = formatDate(status.expires_at);
  elements.modelCount.textContent = status.models.length
    ? `${status.models.length} 个`
    : "—";
  renderCatalog(status.model_catalog);
  elements.renew.textContent = available ? "刷新额度" : "重试";
  elements.account.textContent = status.login_pending
    ? "取消登录"
    : (status.signed_in ? "退出笔枢" : "登录笔枢");
  elements.account.hidden = !status.signed_in && !status.ui?.login_enabled;
  elements.payment.hidden = !(
    status.signed_in
    && status.ui?.payment_enabled
    && status.ui?.model_page_recharge_enabled
    && status.ui?.payment_url
  );
  elements.account.disabled = status.state === "disabled" || busy;
  elements.payment.disabled = status.state === "disabled" || busy;
  elements.renew.disabled = status.state === "disabled" || busy;
  const message = status.last_error && available ? status.last_error : "";
  elements.error.textContent = message;
  elements.error.hidden = !message;
}

function isSafeOfficialUrl(value) {
  if (typeof value !== "string") return false;
  try { return new URL(value).protocol === "https:"; }
  catch (_error) { return false; }
}

function setBusy(value) {
  busy = value;
  elements.renew.disabled = value || currentStatus?.state === "disabled";
  elements.account.disabled = value
    || currentStatus?.state === "disabled";
  elements.payment.disabled = value || currentStatus?.state === "disabled";
}

function showError(error) {
  elements.error.textContent = error instanceof Error ? error.message : String(error);
  elements.error.hidden = false;
}

async function run(action) {
  setBusy(true);
  elements.error.hidden = true;
  try {
    const status = await action();
    render(status);
    return true;
  } catch (error) {
    showError(error);
    return false;
  } finally {
    setBusy(false);
  }
}

elements.renew.addEventListener("click", () => {
  void run(() => request("/renew", { method: "POST" }));
});

elements.account.addEventListener("click", () => {
  if (currentStatus?.signed_in || currentStatus?.login_pending) {
    void run(() => request("/login", { method: "DELETE" }));
    return;
  }
  void run(() => request("/login", { method: "POST" })).then((succeeded) => {
    if (succeeded) void pollLogin();
  });
});

elements.payment.addEventListener("click", () => {
  const url = currentStatus?.ui?.payment_url;
  if (!isSafePaymentUrl(url)) return;
  window.open(url, "_blank", "noopener,noreferrer");
});

function isSafePaymentUrl(value) {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    if (url.protocol === "https:") return true;
    const loopback = url.hostname === "localhost"
      || url.hostname === "127.0.0.1"
      || url.hostname === "[::1]";
    return url.protocol === "http:" && loopback;
  } catch (_error) {
    return false;
  }
}

async function pollLogin() {
  if (polling) return;
  polling = true;
  try {
    while (currentStatus?.login_pending) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      try {
        render(await request("/status"));
      } catch (error) {
        showError(error);
        break;
      }
    }
  } finally {
    polling = false;
  }
}

void run(() => request("/status")).then(() => {
  if (currentStatus?.login_pending) void pollLogin();
});
