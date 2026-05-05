(function (global) {
  const SCOPES = {
    active: "Active Location",
    saved: "All Saved Locations",
  };
  const DETAILS_PANEL_ID = "alert-summary-details-panel";
  const FILTERS = [
    ["all", "All"],
    ["warning", "Warnings"],
    ["watch", "Watches"],
    ["advisory", "Advisories"],
    ["test", "TEST"],
    ["nws", "NWS"],
  ];

  let currentScope = "active";
  let detailsOpen = false;
  let detailsFilter = "all";
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
    if (currentScope !== "saved") {
      detailsOpen = false;
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
    const controls = createElement("div", "alert-summary__controls");
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

    controls.append(selector);
    if (currentScope === "saved") {
      controls.append(renderDetailsToggle());
    }

    header.append(label, controls);
    return header;
  }

  async function setScope(scope) {
    currentScope = scope === "saved" ? "saved" : "active";
    if (currentScope !== "saved") {
      detailsOpen = false;
    }
    setStoredScope(currentScope);
    renderLoading();
    await refresh();
  }

  function renderDetailsToggle() {
    const button = createElement(
      "button",
      "alert-summary__details-toggle",
      detailsOpen ? "Hide saved alert details" : "View saved alert details"
    );
    button.type = "button";
    button.setAttribute("aria-expanded", String(detailsOpen));
    button.setAttribute("aria-controls", DETAILS_PANEL_ID);
    button.addEventListener("click", function () {
      detailsOpen = !detailsOpen;
      if (lastSummary) {
        renderSummary(lastSummary);
      }
    });
    return button;
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

    const children = [renderHeader(), body];
    if (currentScope === "saved" && detailsOpen) {
      children.push(renderDetailsPanel(summary));
    }
    root.replaceChildren(...children);
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

  function renderDetailsPanel(summary) {
    const panel = createElement("section", "alert-summary__details");
    panel.id = DETAILS_PANEL_ID;
    panel.setAttribute("aria-label", "Saved alert details");

    panel.append(
      createElement(
        "p",
        "alert-summary__details-intro",
        "All Saved Locations counts alerts matched against saved locations. Active-location banners remain separate."
      )
    );

    if (summary?.partial) {
      panel.append(renderPartialDetails(summary));
    }

    const total = Number(summary?.total) || 0;
    const refs = Array.isArray(summary?.alert_refs) ? summary.alert_refs : null;
    if (total === 0) {
      panel.append(createElement("p", "alert-summary__details-empty", "No saved-location alerts are included in this counter."));
      return panel;
    }
    if (!refs || refs.length === 0) {
      panel.append(createElement("p", "alert-summary__details-empty", "Saved alert details are unavailable for this summary."));
      return panel;
    }

    panel.append(renderFilterChips());
    const groupedAlerts = buildGroupedAlerts(refs);
    const filteredGroups = filterLocationGroups(groupedAlerts);
    if (filteredGroups.length === 0) {
      panel.append(createElement("p", "alert-summary__details-empty", "No alerts match this filter."));
      return panel;
    }
    panel.append(renderLocationGroups(filteredGroups));
    return panel;
  }

  function renderFilterChips() {
    const controls = createElement("div", "alert-summary__filter-chips");
    controls.setAttribute("aria-label", "Saved alert details filters");
    FILTERS.forEach(function ([value, label]) {
      const button = createElement("button", "alert-summary__filter-chip", label);
      button.type = "button";
      button.dataset.filter = value;
      button.setAttribute("aria-pressed", String(detailsFilter === value));
      if (detailsFilter === value) {
        button.classList.add("is-selected");
      }
      button.addEventListener("click", function () {
        detailsFilter = value;
        if (lastSummary) {
          renderSummary(lastSummary);
        }
      });
      controls.append(button);
    });
    return controls;
  }

  function renderPartialDetails(summary) {
    const warning = createElement("div", "alert-summary__details-warning");
    warning.append(createElement("strong", "", "Partial data"));
    const errors = Array.isArray(summary?.errors) ? summary.errors.filter(isReadableText).slice(0, 3) : [];
    if (errors.length > 0) {
      const list = createElement("ul", "alert-summary__details-errors");
      errors.forEach(function (error) {
        list.append(createElement("li", "", error));
      });
      warning.append(list);
    } else {
      warning.append(createElement("span", "", "Some saved locations could not be checked."));
    }
    return warning;
  }

  function renderLocationGroups(groups) {
    const list = createElement("div", "alert-summary__location-groups");
    groups.forEach(function (group) {
      list.append(renderLocationGroup(group));
    });
    return list;
  }

  function renderLocationGroup(group) {
    const item = createElement("article", "alert-summary__location-group");
    const header = createElement("div", "alert-summary__location-header");
    const title = createElement("div", "alert-summary__location-title");
    title.append(
      createElement("strong", "", locationLabel(group.location)),
      createElement("span", "alert-summary__location-detail", locationDetails(group.location) || "Saved location")
    );
    const count = group.alerts.length;
    header.append(title, createElement("span", "alert-summary__location-count", `${count} ${count === 1 ? "alert" : "alerts"}`));

    const alerts = createElement("div", "alert-summary__location-alerts");
    group.alerts.forEach(function (entry) {
      alerts.append(renderGroupedAlert(entry));
    });
    item.append(header, alerts);
    return item;
  }

  function renderGroupedAlert(entry) {
    const alertRef = entry.alert;
    const item = createElement("div", "alert-summary__detail-alert");
    const color = validHex(alertRef?.color_hex) ? alertRef.color_hex : "#64748b";
    item.style.setProperty("--detail-alert-color", color);

    const header = createElement("div", "alert-summary__detail-alert-header");
    const marker = createElement("span", "alert-summary__detail-marker");
    marker.setAttribute("aria-label", "Alert severity color");
    marker.setAttribute("role", "img");

    const title = createElement("div", "alert-summary__detail-title");
    const titleLine = createElement("div", "alert-summary__detail-title-line");
    titleLine.append(sourceBadge(alertRef?.source), createElement("strong", "", alertRef?.event || alertRef?.id || "Alert"));
    title.append(titleLine, renderGroupedAlertMeta(alertRef, entry.location));

    header.append(marker, title);
    item.append(header);
    return item;
  }

  function renderAlertMeta(alertRef) {
    const meta = createElement("div", "alert-summary__detail-meta");
    meta.append(createElement("span", "", categoryLabel(alertRef?.event)));
    const priority = Number(alertRef?.priority_score ?? alertRef?.priority);
    if (Number.isFinite(priority)) {
      meta.append(createElement("span", "", `Priority ${priority}`));
    }
    const count = Number(alertRef?.affected_location_count);
    if (Number.isFinite(count)) {
      meta.append(createElement("span", "", `${count} affected ${count === 1 ? "location" : "locations"}`));
    }
    return meta;
  }

  function renderAffectedLocations(alertRef) {
    const locations = Array.isArray(alertRef?.affected_locations) ? alertRef.affected_locations : [];
    const wrap = createElement("div", "alert-summary__affected");
    if (locations.length === 0) {
      wrap.append(createElement("p", "alert-summary__affected-empty", "No affected saved-location details available."));
      return wrap;
    }
    const list = createElement("ul", "alert-summary__affected-list");
    locations.forEach(function (location) {
      const row = createElement("li", "alert-summary__affected-item");
      const main = createElement("span", "alert-summary__affected-main", locationLabel(location));
      const detail = locationDetails(location);
      row.append(main);
      if (detail) {
        row.append(createElement("span", "alert-summary__affected-detail", detail));
      }
      if (location?.match_type) {
        row.append(createElement("span", "alert-summary__match-type", `Match: ${formatMatchType(location.match_type)}`));
      }
      list.append(row);
    });
    wrap.append(list);
    return wrap;
  }

  function buildGroupedAlerts(alertRefs) {
    const groups = new Map();
    alertRefs.forEach(function (alertRef) {
      const locations = Array.isArray(alertRef?.affected_locations) ? alertRef.affected_locations : [];
      locations.forEach(function (location) {
        const key = String(location?.id ?? locationLabel(location));
        if (!groups.has(key)) {
          groups.set(key, {
            location,
            alerts: [],
          });
        }
        groups.get(key).alerts.push({ alert: alertRef, location });
      });
    });
    return Array.from(groups.values())
      .map(function (group) {
        return {
          location: group.location,
          alerts: group.alerts.sort(alertEntrySortKey),
        };
      })
      .sort(locationGroupSortKey);
  }

  function filterLocationGroups(groups) {
    return groups
      .map(function (group) {
        return {
          location: group.location,
          alerts: group.alerts.filter(function (entry) {
            return matchesFilter(entry.alert);
          }),
        };
      })
      .filter(function (group) {
        return group.alerts.length > 0;
      });
  }

  function matchesFilter(alertRef) {
    if (detailsFilter === "all") {
      return true;
    }
    if (detailsFilter === "test") {
      return isTestSource(alertRef?.source);
    }
    if (detailsFilter === "nws") {
      return !isTestSource(alertRef?.source);
    }
    return categoryKey(alertRef?.event) === detailsFilter;
  }

  function renderGroupedAlertMeta(alertRef, location) {
    const meta = createElement("div", "alert-summary__detail-meta");
    meta.append(createElement("span", "", categoryLabel(alertRef?.event)));
    if (location?.match_type) {
      meta.append(createElement("span", "alert-summary__match-type", `Match: ${formatMatchType(location.match_type)}`));
    }
    if (isHighestAlert(alertRef)) {
      meta.append(createElement("span", "alert-summary__highest-flag", "Highest"));
    }
    const priority = Number(alertRef?.priority_score ?? alertRef?.priority);
    if (Number.isFinite(priority)) {
      meta.append(createElement("span", "", `P${priority}`));
    }
    return meta;
  }

  function sourceBadge(source) {
    const isTest = isTestSource(source);
    const label = isTest ? "TEST" : "NWS";
    const badge = createElement("span", `alert-summary__source-badge alert-summary__source-badge--${isTest ? "test" : "nws"}`, label);
    return badge;
  }

  function isTestSource(source) {
    const normalized = String(source || "").toLowerCase();
    return normalized === "test" || normalized === "molecast_test";
  }

  function categoryLabel(event) {
    const category = categoryKey(event);
    if (category === "warning") {
      return "Warning";
    }
    if (category === "watch") {
      return "Watch";
    }
    if (category === "advisory") {
      return "Advisory";
    }
    return "Other";
  }

  function categoryKey(event) {
    const text = String(event || "").toLowerCase();
    if (text.includes("warning")) {
      return "warning";
    }
    if (text.includes("watch")) {
      return "watch";
    }
    if (text.includes("advisory")) {
      return "advisory";
    }
    return "other";
  }

  function locationLabel(location) {
    return location?.label || location?.name || [location?.city, location?.state].filter(Boolean).join(", ") || "Saved location";
  }

  function locationDetails(location) {
    const locality = [location?.city, location?.state].filter(Boolean).join(", ");
    const parts = [];
    if (location?.zip_code) {
      parts.push(location.zip_code);
    }
    if (locality) {
      parts.push(locality);
    }
    if (location?.county) {
      parts.push(location.county);
    }
    return parts.join(" | ");
  }

  function formatMatchType(matchType) {
    return String(matchType || "").replace(/_/g, " ");
  }

  function isReadableText(value) {
    return typeof value === "string" && value.trim() && value.length < 220;
  }

  function isHighestAlert(alertRef) {
    const highest = lastSummary?.highest_alert;
    return Boolean(highest && alertRef && highest.id === alertRef.id && String(highest.source || "") === String(alertRef.source || ""));
  }

  function alertEntrySortKey(a, b) {
    const priorityDiff = Number(b.alert?.priority_score ?? b.alert?.priority ?? 0) - Number(a.alert?.priority_score ?? a.alert?.priority ?? 0);
    if (priorityDiff !== 0) {
      return priorityDiff;
    }
    return String(a.alert?.event || a.alert?.id || "").localeCompare(String(b.alert?.event || b.alert?.id || ""));
  }

  function locationGroupSortKey(a, b) {
    const alertCountDiff = b.alerts.length - a.alerts.length;
    if (alertCountDiff !== 0) {
      return alertCountDiff;
    }
    return locationLabel(a.location).localeCompare(locationLabel(b.location));
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
