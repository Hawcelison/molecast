(function () {
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

  function renderEmptyState(container) {
    container.replaceChildren(createElement("p", "alert-empty", "No alerts at this time"));
  }

  function getAlertCardColor(alert) {
    if (alert && typeof alert.color_hex === "string" && /^#[0-9a-fA-F]{6}$/.test(alert.color_hex)) {
      return alert.color_hex;
    }
    // Temporary safety fallback for older API payloads without backend color fields.
    if (window.getAlertColor) {
      return window.getAlertColor(alert);
    }
    return "#3399FF";
  }

  function renderAlert(alert) {
    const accentColor = getAlertCardColor(alert);
    const item = createElement("article", "alert-card");
    item.style.backgroundColor = accentColor;
    item.setAttribute("role", "listitem");

    const body = createElement("div", "alert-card__body");
    const header = createElement("div", "alert-card__header");
    const title = createElement("h3", "alert-card__title", alert.title || alert.event || "WEATHER ALERT");
    const source = createElement("span", "alert-card__source", `Source: ${alert.source || "nws"}`);
    const expires = createElement("span", "alert-card__expires", alert.expires_in || "Unknown");
    const subtitle = createElement("p", "alert-card__subtitle", alert.subtitle || alert.areaDesc || "");

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
      : window.MolecastAlertsApi.DEFAULT_REFRESH_SECONDS;

    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(loadAlerts, seconds * 1000);
  }

  function resetAlertViews(alertList, bannerContainer) {
    if (alertList) {
      renderEmptyState(alertList);
    }
    window.MolecastAlertBanners.reset(bannerContainer);
    scheduleNextLoad(window.MolecastAlertsApi.DEFAULT_REFRESH_SECONDS);
  }

  async function loadAlerts() {
    const alertList = document.getElementById("alerts-list");
    const bannerContainer = document.getElementById("alert-banner-container");
    if (!alertList && !bannerContainer) {
      return;
    }

    try {
      const result = await window.MolecastAlertsApi.fetchActiveAlerts();
      window.MolecastAlertBanners.render(bannerContainer, result.alerts);
      if (alertList) {
        renderAlerts(alertList, result.alerts);
      }
      scheduleNextLoad(result.refreshIntervalSeconds);
    } catch (_error) {
      resetAlertViews(alertList, bannerContainer);
    }
  }

  document.addEventListener("DOMContentLoaded", loadAlerts);
})();
