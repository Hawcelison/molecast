(function (global) {
  const SCOPES = {
    active: "Active Location",
    saved: "All Saved Locations",
  };

  let currentScope = "active";
  let lastSummary = null;
  let initialized = false;

  function createElement(tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (text !== undefined && text !== null) {
      element.textContent = String(text);
    }
    return element;
  }

  function container() {
    return document.getElementById("alert-summary-counter");
  }

  function getStoredScope() {
    const settings = global.MolecastSettingsStore?.getSettings?.() || {};
    return settings.alertCounterScope === "saved" ? "saved" : "active";
  }

  function setStoredScope(scope) {
    if (global.MolecastSettingsStore?.setAlertCounterScope) {
      global.MolecastSettingsStore.setAlertCounterScope(scope);
    }
  }

  function init() {
    if (initialized || !container()) {
      return;
    }
    initialized = true;
    currentScope = getStoredScope();
    renderLoading();
  }

  function renderLoading() {
    const root = container();
    if (!root) {
      return;
    }
    root.replaceChildren(
      renderHeader(),
      createElement("div", "alert-summary__body", "Loading alert counter")
    );
  }

  function renderError(message) {
    const root = container();
    if (!root) {
      return;
    }
    const body = createElement("div", "alert-summary__body");
    body.append(createElement("span", "alert-summary__empty", message || "Alert counter unavailable"));
    root.replaceChildren(renderHeader(), body);
  }

  function renderHeader() {
    const header = createElement("div", "alert-summary__header");
    const label = createElement("strong", "alert-summary__scope-label", `Counter: ${SCOPES[currentScope]}`);
    const selector = createElement("div", "alert-summary__scope-selector");
    selector.setAttribute("aria-label", "Alert counter scope");

    Object.entries(SCOPES).forEach(function ([scope, text]) {
      const button = createElement("button", "alert-summary__scope-button", text);
      button.type = "button";
      button.dataset.scope = scope;
      button.setAttribute("aria-pressed", scope === currentScope ? "true" : "false");
      if (scope === currentScope) {
        button.classList.add("is-selected");
      }
      button.addEventListener("click", function () {
        if (currentScope === scope) {
          return;
        }
        setScope(scope);
      });
      selector.append(button);
    });

    header.append(label, selector);
    return header;
  }

  async function setScope(scope) {
    currentScope = scope === "saved" ? "saved" : "active";
    setStoredScope(currentScope);
    renderLoading();
    await refresh();
  }

  async function refresh() {
    init();
    if (!container() || !global.MolecastAlertsApi?.fetchAlertSummary) {
      return null;
    }
    try {
      const summary = await global.MolecastAlertsApi.fetchAlertSummary(currentScope);
      lastSummary = summary;
      renderSummary(summary);
      return summary;
    } catch (error) {
      renderError(error.message || "Alert counter unavailable");
      return null;
    }
  }

  function renderSummary(summary) {
    const root = container();
    if (!root) {
      return;
    }
    const body = createElement("div", "alert-summary__body");
    const total = Number(summary?.total) || 0;
    body.append(
      metricChip("Total", total),
      metricChip("Warnings", summary?.warning_count),
      metricChip("Watches", summary?.watch_count),
      metricChip("Advisories", summary?.advisory_count),
      metricChip("Other", summary?.other_count)
    );

    if (total > 0 && summary?.highest_alert) {
      body.append(highestAlertChip(summary.highest_alert));
    } else {
      body.append(createElement("span", "alert-summary__empty", `No alerts for ${SCOPES[currentScope]}`));
    }

    const affectedCount = Number(summary?.affected_location_count);
    if (currentScope === "saved" && Number.isFinite(affectedCount)) {
      body.append(createElement("span", "alert-summary__note", `${affectedCount} ${affectedCount === 1 ? "location" : "locations"} affected`));
    }

    if (summary?.partial) {
      body.append(createElement("span", "alert-summary__partial", "Partial data"));
    }

    root.replaceChildren(renderHeader(), body);
  }

  function metricChip(label, value) {
    const chip = createElement("span", "alert-summary__chip");
    chip.append(
      createElement("span", "alert-summary__chip-label", label),
      createElement("strong", "alert-summary__chip-value", Number(value) || 0)
    );
    return chip;
  }

  function highestAlertChip(alert) {
    const chip = createElement("span", "alert-summary__chip alert-summary__chip--highest");
    const color = validHex(alert.color_hex) ? alert.color_hex : "#2563eb";
    chip.style.setProperty("--summary-accent", color);
    chip.style.setProperty("--summary-fg", textColorForHex(color));
    const source = String(alert.source || "").toLowerCase() === "test" ? "TEST: " : "";
    chip.append(
      createElement("span", "alert-summary__chip-label", "Highest"),
      createElement("strong", "alert-summary__chip-value", `${source}${alert.event || alert.id || "Alert"}`)
    );
    return chip;
  }

  function validHex(value) {
    return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
  }

  function textColorForHex(hex) {
    if (!validHex(hex)) {
      return "#ffffff";
    }
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    return luminance > 0.58 ? "#111827" : "#ffffff";
  }

  global.MolecastAlertSummary = {
    currentScope: function () {
      return currentScope;
    },
    init,
    lastSummary: function () {
      return lastSummary;
    },
    refresh,
    setScope,
  };
})(window);
