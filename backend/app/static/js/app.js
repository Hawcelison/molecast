(function () {
  const ALERTS_ENDPOINT = "/api/alerts/active";
  const DEFAULT_REFRESH_SECONDS = 60;

  let expandedAlertIds = new Set();
  let previousAlertIds = new Set();
  let hasRenderedBanners = false;
  let refreshTimer = null;

  function createElement(tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (text) {
      element.textContent = text;
    }
    return element;
  }

  function getString(value, fallback) {
    return typeof value === "string" && value.trim() ? value.trim() : fallback;
  }

  function alertId(alert, index) {
    return getString(alert.id, `${getString(alert.event, "alert")}-${getString(alert.expires, String(index))}`);
  }

  function validAlert(alert) {
    return alert && typeof alert === "object" && !Array.isArray(alert);
  }

  function hexToRgb(hexColor) {
    const normalized = String(hexColor || "").replace("#", "");
    if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
      return null;
    }

    return {
      r: Number.parseInt(normalized.slice(0, 2), 16),
      g: Number.parseInt(normalized.slice(2, 4), 16),
      b: Number.parseInt(normalized.slice(4, 6), 16),
    };
  }

  function textColorForHex(hexColor) {
    const rgb = hexToRgb(hexColor);
    if (!rgb) {
      return "#ffffff";
    }

    const channels = [rgb.r, rgb.g, rgb.b].map(function (channel) {
      const normalized = channel / 255;
      return normalized <= 0.03928
        ? normalized / 12.92
        : Math.pow((normalized + 0.055) / 1.055, 2.4);
    });
    const luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    return luminance > 0.48 ? "#111827" : "#ffffff";
  }

  function detailText(alert, fieldName) {
    return getString(alert[fieldName], "");
  }

  function formatAlertTime(value) {
    const time = new Date(value || "");
    if (Number.isNaN(time.getTime())) {
      return getString(value, "");
    }

    return new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(time);
  }

  function formatDetailTime(value) {
    const time = new Date(value || "");
    if (Number.isNaN(time.getTime())) {
      return getString(value, "");
    }

    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(time);
  }

  function formatBannerTitle(alert) {
    const event = getString(alert.event, getString(alert.title, "Weather Alert"));
    const area = getString(alert.areaDesc, getString(alert.subtitle, "Unknown Area"));
    const expiresAt = formatAlertTime(alert.expires);
    const expires = expiresAt || getString(alert.expires_in, "Unknown");
    return `${event} - ${area} - Expires ${expires}`.toUpperCase();
  }

  function appendDetail(details, label, value) {
    const text = getString(value, "");
    if (!text) {
      return;
    }

    const row = createElement("div", "alert-banner__detail-row");
    row.append(createElement("dt", "", label));
    row.append(createElement("dd", "", text));
    details.append(row);
  }

  function renderEmptyState(container) {
    container.replaceChildren(createElement("p", "alert-empty", "No alerts at this time"));
  }

  function renderBannerEmptyState(container) {
    container.replaceChildren();
  }

  function renderAlertBanner(alert, index) {
    const id = alertId(alert, index);
    const headline = detailText(alert, "headline") || detailText(alert, "title");
    const description = detailText(alert, "description");
    const instruction = detailText(alert, "instruction") || getString((alert.raw_properties || {}).instruction, "");
    const accentColor = getAlertColor(alert);
    const foregroundColor = textColorForHex(accentColor);
    const expanded = expandedAlertIds.has(id);
    const detailsId = `alert-banner-details-${index}`;

    const item = createElement("article", "alert-banner");
    item.setAttribute("role", "listitem");
    item.setAttribute("tabindex", "0");
    item.setAttribute("aria-expanded", expanded ? "true" : "false");
    item.setAttribute("aria-controls", detailsId);
    item.style.setProperty("--alert-accent", accentColor);
    item.style.setProperty("--alert-fg", foregroundColor);

    const compact = createElement("div", "alert-banner__compact");
    compact.append(createElement("strong", "alert-banner__title", formatBannerTitle(alert)));
    item.append(compact);

    const details = createElement("dl", "alert-banner__details");
    details.id = detailsId;
    appendDetail(details, "Headline", headline);
    appendDetail(details, "Description", description);
    appendDetail(details, "Instruction", instruction);
    appendDetail(details, "Source", alert.source || "nws");
    appendDetail(details, "Severity", alert.severity);
    appendDetail(details, "Urgency", alert.urgency);
    appendDetail(details, "Certainty", alert.certainty);
    appendDetail(details, "Effective", formatDetailTime(alert.effective));
    appendDetail(details, "Expires", formatDetailTime(alert.expires));
    item.append(details);

    item.addEventListener("click", function () {
      toggleBanner(id, item);
    });
    item.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleBanner(id, item);
      }
    });

    return item;
  }

  function toggleBanner(id, item) {
    if (expandedAlertIds.has(id)) {
      expandedAlertIds.delete(id);
      item.setAttribute("aria-expanded", "false");
      return;
    }

    expandedAlertIds.add(id);
    item.setAttribute("aria-expanded", "true");
  }

  function renderAlertBanners(alerts) {
    const container = document.getElementById("alert-banner-container");
    if (!container) {
      return;
    }

    const usableAlerts = (Array.isArray(alerts) ? alerts : []).filter(validAlert);
    if (usableAlerts.length === 0) {
      expandedAlertIds.clear();
      previousAlertIds = new Set();
      hasRenderedBanners = true;
      renderBannerEmptyState(container);
      return;
    }

    const currentIds = new Set(usableAlerts.map(alertId));
    const hasNewAlert = hasRenderedBanners && usableAlerts.some(function (alert, index) {
      return !previousAlertIds.has(alertId(alert, index));
    });

    if (hasNewAlert) {
      expandedAlertIds = new Set(currentIds);
    } else {
      expandedAlertIds = new Set(
        Array.from(expandedAlertIds).filter(function (id) {
          return currentIds.has(id);
        })
      );
    }

    container.replaceChildren(...usableAlerts.map(renderAlertBanner));
    previousAlertIds = currentIds;
    hasRenderedBanners = true;
  }

  function renderAlert(alert) {
    const accentColor = getAlertColor(alert);
    const item = createElement("article", "alert-card");
    item.style.backgroundColor = accentColor;
    item.setAttribute("role", "listitem");

    const body = createElement("div", "alert-card__body");
    const header = createElement("div", "alert-card__header");
    const title = createElement("h3", "alert-card__title", alert.title || "WEATHER ALERT");
    const source = createElement("span", "alert-card__source", `Source: ${alert.source || "nws"}`);
    const expires = createElement("span", "alert-card__expires", alert.expires_in || "Unknown");
    const subtitle = createElement("p", "alert-card__subtitle", alert.subtitle || "");

    header.append(title, source, expires);
    body.append(header, subtitle);

    if (Array.isArray(alert.tags) && alert.tags.length > 0) {
      const tags = createElement("div", "alert-card__tags");
      alert.tags.forEach(function (tag) {
        tags.append(createElement("span", "alert-card__tag", tag));
      });
      body.append(tags);
    }

    item.append(body);
    return item;
  }

  function renderAlerts(container, alerts) {
    if (!Array.isArray(alerts) || alerts.length === 0) {
      renderEmptyState(container);
      return;
    }

    container.replaceChildren(...alerts.map(renderAlert));
  }

  function scheduleNextLoad(refreshSeconds) {
    const seconds = Number.isFinite(refreshSeconds) && refreshSeconds > 0
      ? refreshSeconds
      : DEFAULT_REFRESH_SECONDS;

    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(loadAlerts, seconds * 1000);
  }

  async function loadAlerts() {
    const alertList = document.getElementById("alerts-list");
    const bannerContainer = document.getElementById("alert-banner-container");
    if (!alertList && !bannerContainer) {
      return;
    }

    try {
      const response = await window.fetch(ALERTS_ENDPOINT);
      if (!response.ok) {
        if (alertList) {
          renderEmptyState(alertList);
        }
        if (bannerContainer) {
          renderBannerEmptyState(bannerContainer);
        }
        scheduleNextLoad(DEFAULT_REFRESH_SECONDS);
        return;
      }

      const payload = await response.json();
      const alerts = payload && Array.isArray(payload.alerts) ? payload.alerts : [];
      renderAlertBanners(alerts);
      if (alertList) {
        renderAlerts(alertList, alerts);
      }
      scheduleNextLoad(Number(payload && payload.refresh_interval_seconds) || DEFAULT_REFRESH_SECONDS);
    } catch (_error) {
      if (alertList) {
        renderEmptyState(alertList);
      }
      if (bannerContainer) {
        renderBannerEmptyState(bannerContainer);
      }
      scheduleNextLoad(DEFAULT_REFRESH_SECONDS);
    }
  }

  document.addEventListener("DOMContentLoaded", loadAlerts);
})();
