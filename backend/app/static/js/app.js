(function () {
  const ALERTS_ENDPOINT = "/api/alerts/active";

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

  function renderAlert(alert) {
    const item = createElement("article", `alert-card ${alert.severity_color || "severity-unknown"}`);
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

  async function loadAlerts() {
    const container = document.getElementById("alerts-list");
    if (!container) {
      return;
    }

    try {
      const response = await window.fetch(ALERTS_ENDPOINT);
      if (!response.ok) {
        renderEmptyState(container);
        return;
      }

      const payload = await response.json();
      renderAlerts(container, payload.alerts);
    } catch (_error) {
      renderEmptyState(container);
    }
  }

  document.addEventListener("DOMContentLoaded", loadAlerts);
})();
