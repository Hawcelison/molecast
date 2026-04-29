(function (global) {
  const DEFAULT_ALERT_COLOR = "#3399FF";
  const HIGH_PRIORITY_THRESHOLD = 800;

  let expandedAlertIds = new Set();
  let previousCanonicalIds = new Set();
  let lastRenderedAlerts = [];

  function createElement(tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (text !== undefined && text !== null) {
      element.textContent = text;
    }
    return element;
  }

  function getString(value, fallback) {
    return typeof value === "string" && value.trim() ? value.trim() : fallback;
  }

  function validAlert(alert) {
    return alert && typeof alert === "object" && !Array.isArray(alert);
  }

  function canonicalId(alert, index) {
    return getString(
      alert && (alert.canonical_id || alert.canonicalId || alert.id),
      `${getString(alert && alert.event, "alert")}-${getString(alert && alert.expires, String(index))}`
    );
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

  function alertColor(alert) {
    if (alert && typeof alert.color_hex === "string" && /^#[0-9a-fA-F]{6}$/.test(alert.color_hex)) {
      return alert.color_hex;
    }
    // Temporary safety fallback for older API payloads without backend color fields.
    if (global.getAlertColor) {
      return global.getAlertColor(alert);
    }
    return DEFAULT_ALERT_COLOR;
  }

  function alertPriority(alert) {
    const value = Number(alert && (alert.priority ?? alert.priority_score));
    return Number.isFinite(value) ? value : 0;
  }

  function sortAlerts(alerts) {
    return alerts.slice().sort(function (left, right) {
      return alertPriority(right) - alertPriority(left);
    });
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

  function alertName(alert) {
    return getString(alert && alert.title, getString(alert && alert.event, "Weather Alert"));
  }

  function alertArea(alert) {
    return getString(
      alert && alert.subtitle,
      getString(alert && alert.areaDesc, getString(alert && alert.area, "Unknown Area"))
    );
  }

  function alertExpires(alert) {
    return formatAlertTime(alert && alert.expires) || getString(alert && alert.expires_in, "Unknown");
  }

  function compactText(alert) {
    return `${alertName(alert)} - ${alertArea(alert)} - Until ${alertExpires(alert)}`;
  }

  function detailText(alert, fieldName) {
    return getString(alert && alert[fieldName], "");
  }

  function instructionText(alert) {
    return detailText(alert, "instruction");
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

  function isAssertiveAlert(alert) {
    const severity = getString(alert && alert.severity, "").toLowerCase();
    const urgency = getString(alert && alert.urgency, "").toLowerCase();
    return (severity === "extreme" || severity === "severe") && urgency === "immediate";
  }

  function isHighPriority(alert) {
    return isAssertiveAlert(alert) || alertPriority(alert) >= HIGH_PRIORITY_THRESHOLD;
  }

  function isSevereOrExtreme(alert) {
    const severity = getString(alert && alert.severity, "").toLowerCase();
    return severity === "extreme" || severity === "severe";
  }

  function currentActionAlert(alerts) {
    return alerts.find(function (alert) {
      const id = canonicalId(alert);
      return isHighPriority(alert) &&
        !global.MolecastSettingsStore.isAlertAcknowledged(id);
    }) || alerts[0] || null;
  }

  function renderControls(alerts) {
    const container = document.getElementById("alert-controls");
    if (!container) {
      return;
    }

    const settings = global.MolecastSettingsStore.getSettings();
    const actionAlert = currentActionAlert(alerts);
    const actionAlertId = actionAlert ? canonicalId(actionAlert) : "";
    const isSilenced = actionAlertId && global.MolecastSettingsStore.isAlertSilenced(actionAlertId);
    const isAcknowledged = actionAlertId && global.MolecastSettingsStore.isAlertAcknowledged(actionAlertId);

    const audioLabel = makeCheckboxControl(
      "alert-audio-enabled",
      "Alert audio",
      settings.alertAudioEnabled,
      function (checked) {
        global.MolecastSettingsStore.setAlertAudioEnabled(checked);
        if (!checked) {
          global.MolecastAlertAudio.stop();
        } else {
          global.MolecastAlertAudio.unlockForSession();
          const alert = currentActionAlert(lastRenderedAlerts);
          if (alert) {
            global.MolecastAlertAudio.playForAlert(alert);
          }
        }
        renderControls(lastRenderedAlerts);
      }
    );
    const testAudioLabel = makeCheckboxControl(
      "test-audio-enabled",
      "Test audio",
      settings.testAudioEnabled,
      function (checked) {
        global.MolecastSettingsStore.setTestAudioEnabled(checked);
        if (checked && global.MolecastSettingsStore.getSettings().alertAudioEnabled) {
          global.MolecastAlertAudio.unlockForSession();
          const alert = currentActionAlert(lastRenderedAlerts);
          if (alert) {
            global.MolecastAlertAudio.playForAlert(alert);
          }
        }
        renderControls(lastRenderedAlerts);
      }
    );
    const flashingLabel = makeCheckboxControl(
      "alert-flashing-disabled",
      "Disable flashing",
      settings.flashingDisabled,
      function (checked) {
        global.MolecastSettingsStore.setFlashingDisabled(checked);
        if (checked) {
          global.MolecastAlertFlash.stop();
        }
        evaluateFlash(lastRenderedAlerts);
        renderControls(lastRenderedAlerts);
      }
    );

    const silenceButton = createElement("button", "alert-control-button", isSilenced ? "Unsilence active" : "Silence active");
    silenceButton.type = "button";
    silenceButton.disabled = !actionAlertId;
    silenceButton.addEventListener("click", function () {
      if (!actionAlertId) {
        return;
      }
      if (global.MolecastSettingsStore.isAlertSilenced(actionAlertId)) {
        global.MolecastSettingsStore.unsilenceAlert(actionAlertId);
      } else {
        global.MolecastSettingsStore.silenceAlert(actionAlertId);
        global.MolecastAlertAudio.stop();
      }
      evaluateFlash(lastRenderedAlerts);
      renderControls(lastRenderedAlerts);
    });

    const acknowledgeButton = createElement("button", "alert-control-button", isAcknowledged ? "Unacknowledge active" : "Acknowledge active");
    acknowledgeButton.type = "button";
    acknowledgeButton.disabled = !actionAlertId;
    acknowledgeButton.addEventListener("click", function () {
      if (!actionAlertId) {
        return;
      }
      if (global.MolecastSettingsStore.isAlertAcknowledged(actionAlertId)) {
        global.MolecastSettingsStore.unacknowledgeAlert(actionAlertId);
      } else {
        global.MolecastSettingsStore.acknowledgeAlert(actionAlertId);
        global.MolecastAlertAudio.stop();
      }
      evaluateFlash(lastRenderedAlerts);
      renderControls(lastRenderedAlerts);
    });

    container.replaceChildren(
      audioLabel,
      testAudioLabel,
      flashingLabel,
      silenceButton,
      acknowledgeButton
    );
  }

  function makeCheckboxControl(id, labelText, checked, onChange) {
    const label = createElement("label", "alert-control-toggle");
    const input = createElement("input");
    input.type = "checkbox";
    input.id = id;
    input.checked = Boolean(checked);
    input.addEventListener("change", function () {
      onChange(input.checked);
    });
    label.append(input, createElement("span", "", labelText));
    return label;
  }

  function renderEmpty(container) {
    expandedAlertIds.clear();
    previousCanonicalIds = new Set();
    lastRenderedAlerts = [];
    renderControls([]);
    container.replaceChildren();
    container.setAttribute("aria-live", "polite");
  }

  function renderAlertBanner(alert, index) {
    const id = canonicalId(alert, index);
    const color = alertColor(alert);
    const foregroundColor = textColorForHex(color);
    const expanded = expandedAlertIds.has(id);
    const detailsId = `alert-banner-details-${index}`;

    const item = createElement("article", "alert-banner");
    item.setAttribute("role", "listitem");
    item.setAttribute("tabindex", "0");
    item.setAttribute("aria-expanded", expanded ? "true" : "false");
    item.setAttribute("aria-controls", detailsId);
    item.style.setProperty("--alert-accent", color);
    item.style.setProperty("--alert-fg", foregroundColor);

    const compact = createElement("div", "alert-banner__compact");
    const icon = createElement("span", "alert-banner__icon", global.MolecastAlertIcons.iconForAlert(alert));
    icon.setAttribute("aria-hidden", "true");
    compact.append(icon, createElement("strong", "alert-banner__title", compactText(alert)));
    item.append(compact);

    const details = createElement("dl", "alert-banner__details");
    details.id = detailsId;
    appendDetail(details, "Headline", detailText(alert, "headline") || alertName(alert));
    appendDetail(details, "Description", detailText(alert, "description"));
    appendDetail(details, "Instruction", instructionText(alert));
    appendDetail(details, "Source", alert.source || "nws");
    appendDetail(details, "Severity", alert.severity);
    appendDetail(details, "Urgency", alert.urgency);
    appendDetail(details, "Certainty", alert.certainty);
    appendDetail(details, "Effective", formatDetailTime(alert.effective));
    appendDetail(details, "Expires", formatDetailTime(alert.expires));
    item.append(details);

    item.addEventListener("click", function () {
      toggle(id, item);
    });
    item.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle(id, item);
      }
    });

    return item;
  }

  function toggle(id, item) {
    if (expandedAlertIds.has(id)) {
      expandedAlertIds.delete(id);
      item.setAttribute("aria-expanded", "false");
      return;
    }

    expandedAlertIds.add(id);
    item.setAttribute("aria-expanded", "true");
  }

  function scrollToContainer(container) {
    if (
      global.MolecastSettingsStore &&
      global.MolecastSettingsStore.prefersReducedMotion()
    ) {
      return;
    }
    container.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  function render(container, alerts) {
    if (!container) {
      return [];
    }

    const usableAlerts = sortAlerts((Array.isArray(alerts) ? alerts : []).filter(validAlert));
    lastRenderedAlerts = usableAlerts;
    renderControls(usableAlerts);
    if (usableAlerts.length === 0) {
      renderEmpty(container);
      global.MolecastAlertFlash.stop();
      global.MolecastAlertAudio.stop();
      return [];
    }

    const currentIds = new Set(usableAlerts.map(canonicalId));
    const newAlertIds = Array.from(currentIds).filter(function (id) {
      return !previousCanonicalIds.has(id);
    });
    const newAlerts = usableAlerts.filter(function (alert, index) {
      return newAlertIds.includes(canonicalId(alert, index));
    });

    expandedAlertIds = new Set(
      Array.from(expandedAlertIds).filter(function (id) {
        return currentIds.has(id);
      })
    );

    newAlertIds.forEach(function (id) {
      expandedAlertIds.add(id);
    });

    container.setAttribute("aria-live", usableAlerts.some(isAssertiveAlert) ? "assertive" : "polite");
    container.replaceChildren(...usableAlerts.map(renderAlertBanner));

    if (newAlerts.length > 0) {
      scrollToContainer(container);
      const high = newAlerts.find(isHighPriority);
      if (high) {
        global.MolecastAlertAudio.playForAlert(high);
      }
    }

    evaluateFlash(usableAlerts);

    if (!usableAlerts.some(isHighPriority)) {
      global.MolecastAlertAudio.stop();
    }

    previousCanonicalIds = currentIds;
    return usableAlerts;
  }

  function reset(container) {
    if (container) {
      renderEmpty(container);
    }
    global.MolecastAlertFlash.stop();
    global.MolecastAlertAudio.stop();
  }

  function evaluateFlash(alerts) {
    const activeFlashAlert = alerts.find(function (alert) {
      const id = canonicalId(alert);
      return isSevereOrExtreme(alert) &&
        !global.MolecastSettingsStore.isAlertAcknowledged(id);
    });

    if (!activeFlashAlert) {
      global.MolecastAlertFlash.stop();
      return;
    }

    if (global.MolecastSettingsStore.getSettings().flashingDisabled) {
      global.MolecastAlertFlash.stop();
      return;
    }

    global.MolecastAlertFlash.start(alertColor(activeFlashAlert));
  }

  global.MolecastAlertBanners = {
    canonicalId,
    render,
    reset,
  };
})(window);
