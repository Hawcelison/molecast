(function () {
  const API_URL = "/api/test-alerts";
  const REFRESH_URL = "/api/test-alerts/refresh";
  const STATUS_URL = "/api/test-alerts/status";
  const severityValues = ["Extreme", "Severe", "Moderate", "Minor", "Unknown"];
  const urgencyValues = ["Immediate", "Expected", "Future", "Past", "Unknown"];
  const certaintyValues = ["Observed", "Likely", "Possible", "Unlikely", "Unknown"];
  const commonParameterKeys = [
    "tornadoDetection",
    "testCenter",
    "zipCode",
    "windGust",
    "hailSize",
    "radarIndicated",
    "thunderstormDamageThreat",
    "tornadoDamageThreat",
    "flashFloodDamageThreat",
    "snowAmount",
    "iceAccumulation",
  ];
  const eventValues = [
    "Administrative Message", "Avalanche Watch", "Avalanche Warning", "Blizzard Warning",
    "Child Abduction Emergency", "Civil Danger Warning", "Civil Emergency Message",
    "Coastal Flood Advisory", "Coastal Flood Statement", "Coastal Flood Watch",
    "Coastal Flood Warning", "Dense Fog Advisory", "Dense Smoke Advisory", "Dust Advisory",
    "Dust Storm Warning", "Earthquake Warning", "Evacuation Immediate",
    "Excessive Heat Outlook", "Excessive Heat Watch", "Excessive Heat Warning",
    "Extreme Cold Watch", "Extreme Cold Warning", "Extreme Fire Danger",
    "Extreme Wind Warning", "Fire Warning", "Fire Weather Watch", "Flash Flood Statement",
    "Flash Flood Watch", "Flash Flood Warning", "Flood Advisory", "Flood Statement",
    "Flood Watch", "Flood Warning", "Freeze Watch", "Freeze Warning", "Frost Advisory",
    "Gale Watch", "Gale Warning", "Hard Freeze Watch", "Hard Freeze Warning",
    "Hazardous Materials Warning", "Hazardous Seas Watch", "Hazardous Seas Warning",
    "Heat Advisory", "Heavy Freezing Spray Watch", "Heavy Freezing Spray Warning",
    "High Surf Advisory", "High Surf Warning", "High Wind Watch", "High Wind Warning",
    "Hurricane Force Wind Watch", "Hurricane Force Wind Warning", "Hurricane Local Statement",
    "Hurricane Watch", "Hurricane Warning", "Ice Storm Warning", "Lake Effect Snow Advisory",
    "Lake Effect Snow Watch", "Lake Effect Snow Warning", "Lake Wind Advisory",
    "Law Enforcement Warning", "Local Area Emergency", "Marine Weather Statement",
    "Nuclear Power Plant Warning", "Radiological Hazard Warning", "Red Flag Warning",
    "Rip Current Statement", "Severe Thunderstorm Watch", "Severe Thunderstorm Warning",
    "Severe Weather Statement", "Shelter In Place Warning", "Small Craft Advisory",
    "Snow Squall Warning", "Special Marine Warning", "Special Weather Statement",
    "Storm Surge Watch", "Storm Surge Warning", "Storm Watch", "Storm Warning",
    "Test Message", "Tornado Watch", "Tornado Warning", "Tropical Storm Local Statement",
    "Tropical Storm Watch", "Tropical Storm Warning", "Tsunami Advisory", "Tsunami Watch",
    "Tsunami Warning", "Typhoon Watch", "Typhoon Warning", "Volcano Warning",
    "Wind Advisory", "Winter Storm Watch", "Winter Storm Warning", "Winter Weather Advisory",
  ];
  const utcPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
  const sortValueTypes = {
    id: "string",
    event: "string",
    source: "string",
    enabled: "boolean",
    severity: "string",
    urgency: "string",
    certainty: "string",
    areaDesc: "string",
    effective: "date",
    expires: "date",
  };
  const defaultGeometryColor = window.NWS_DEFAULT_ALERT_COLOR;
  const geometrySourceId = "test-alert-editor-geometry";
  const geometryFillLayerId = "test-alert-editor-geometry-fill";
  const geometryLineLayerId = "test-alert-editor-geometry-line";

  let payload = null;
  let selectedIndex = -1;
  let sortState = { key: "", direction: "asc" };
  let geometryMap = null;
  let geometryMarker = null;
  let geometryVertexMarkers = [];
  let geometryMapClickFallbackWired = false;
  let geometryMapLoaded = false;
  let geometryMode = "rectangle";
  let geometryDrawPoints = [];
  let geometryEditEnabled = false;
  let suppressGeometryFieldInput = false;

  function byId(id) {
    return document.getElementById(id);
  }

  function setStatus(message) {
    byId("test-alert-status").textContent = message;
  }

  function setGeometryStatus(message) {
    byId("geometry-map-status").textContent = message;
  }

  function setEditorMessage(message, type) {
    const element = byId("editor-form-message");
    if (!element) {
      return;
    }
    element.textContent = message || "";
    element.classList.remove(
      "is-visible",
      "editor-form-message--error",
      "editor-form-message--success",
      "editor-form-message--warning",
    );
    if (!message) {
      return;
    }
    element.classList.add("is-visible", `editor-form-message--${type || "error"}`);
  }

  function formatUtc(date) {
    return date.toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  function formatLocal(value) {
    if (!value || !utcPattern.test(value)) {
      return "Local: -";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "Local: invalid UTC";
    }
    return `Local: ${date.toLocaleString()}`;
  }

  function updateLocalTimes() {
    byId("field-effective-local").textContent = formatLocal(byId("field-effective").value.trim());
    byId("field-expires-local").textContent = formatLocal(byId("field-expires").value.trim());
  }

  function prettyJson(value) {
    if (value === undefined || value === null) {
      return "";
    }
    return JSON.stringify(value, null, 2);
  }

  function parseJsonField(id, label) {
    const raw = byId(id).value.trim();
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (error) {
      throw new Error(`${label} JSON is invalid: ${error.message}`);
    }
  }

  function validateUtc(value, label) {
    if (!value) {
      return value;
    }
    if (!utcPattern.test(value) || Number.isNaN(new Date(value).getTime())) {
      throw new Error(`Invalid timestamp: ${label} must be UTC ISO format ending in Z.`);
    }
    return value;
  }

  function parseUtcRequired(value, label) {
    const utcValue = validateUtc(value, label);
    if (!utcValue) {
      throw new Error(`${label} is required.`);
    }
    return new Date(utcValue);
  }

  function validateGeometry(geometry) {
    if (geometry === null) {
      return geometry;
    }
    if (!geometry || typeof geometry !== "object" || Array.isArray(geometry)) {
      throw new Error("Geometry must be a JSON object or empty.");
    }
    if (geometry.type !== "Polygon" || !Array.isArray(geometry.coordinates)) {
      throw new Error("Geometry must be a GeoJSON Polygon object.");
    }
    const ring = geometry.coordinates[0];
    if (!Array.isArray(ring) || ring.length < 4) {
      throw new Error("Invalid geometry: polygon needs at least 3 points.");
    }
    ring.forEach(function (position) {
      if (!Array.isArray(position) || position.length < 2) {
        throw new Error("Geometry positions must be [longitude, latitude].");
      }
      const lon = Number(position[0]);
      const lat = Number(position[1]);
      if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
        throw new Error("Invalid longitude.");
      }
      if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
        throw new Error("Invalid latitude.");
      }
    });
    const first = ring[0];
    const last = ring[ring.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      throw new Error("Geometry Polygon ring must be closed.");
    }
    const uniquePoints = new Set(ring.slice(0, -1).map(function (position) {
      return `${Number(position[0])},${Number(position[1])}`;
    }));
    if (uniquePoints.size < 3) {
      throw new Error("Invalid geometry: polygon needs at least 3 points.");
    }
    return geometry;
  }

  function validateGeometryForUi(geometry) {
    try {
      validateGeometry(geometry);
      setGeometryStatus("Geometry is valid.");
      return true;
    } catch (error) {
      setGeometryStatus(error.message || "Invalid geometry.");
      return false;
    }
  }

  function validatePayloadBeforeSave() {
    if (!payload || typeof payload !== "object" || !Array.isArray(payload.alerts)) {
      throw new Error("Payload must include an alerts array.");
    }
    payload.alerts.forEach(function (alert, index) {
      if (!alert || typeof alert !== "object" || Array.isArray(alert)) {
        throw new Error(`Alert at index ${index} must be an object.`);
      }
      alert.source = alert.source || "test";
      if (!alert.id || typeof alert.id !== "string" || !alert.id.trim()) {
        throw new Error("Missing required field: id");
      }
      if (!alert.event || typeof alert.event !== "string" || !alert.event.trim()) {
        throw new Error("Missing required field: event");
      }
      if (typeof alert.enabled !== "boolean") {
        throw new Error(`Alert ${alert.id} enabled must be true or false.`);
      }
      const effectiveAt = parseUtcRequired(alert.effective || "", `Alert ${alert.id} effective`);
      const expiresAt = parseUtcRequired(alert.expires || "", `Alert ${alert.id} expires`);
      if (expiresAt <= effectiveAt && !(alert.enabled === false && expiresAt <= new Date())) {
        throw new Error("Invalid timestamp: expires must be after effective.");
      }
      if (!severityValues.includes(alert.severity)) {
        throw new Error(`Alert ${alert.id} severity must be a supported value.`);
      }
      if (!urgencyValues.includes(alert.urgency)) {
        throw new Error(`Alert ${alert.id} urgency must be a supported value.`);
      }
      if (!certaintyValues.includes(alert.certainty)) {
        throw new Error(`Alert ${alert.id} certainty must be a supported value.`);
      }
      validateGeometry(alert.geometry ?? null);
      if (alert.parameters !== null && alert.parameters !== undefined && (typeof alert.parameters !== "object" || Array.isArray(alert.parameters))) {
        throw new Error(`Alert ${alert.id} parameters must be an object or empty.`);
      }
    });
  }

  function fillSelect(id, values, currentValue) {
    const select = byId(id);
    const uniqueValues = [...new Set(values.filter(Boolean))].sort();
    select.replaceChildren(new Option("", ""));
    uniqueValues.forEach(function (value) {
      select.append(new Option(value, value));
    });
    if (currentValue && !uniqueValues.includes(currentValue)) {
      select.append(new Option(currentValue, currentValue));
    }
    if (currentValue !== undefined) {
      select.value = currentValue || "";
    }
  }

  function cloneValue(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function currentAlerts() {
    if (!payload || !Array.isArray(payload.alerts)) {
      return [];
    }
    return payload.alerts;
  }

  function makeEmptyAlert() {
    const now = new Date();
    const nowMs = now.getTime();
    return {
      enabled: false,
      id: `test-alert-${formatUtc(now).replace(/[^0-9]/g, "")}`,
      source: "test",
      event: "Test Message",
      severity: "Unknown",
      urgency: "Unknown",
      certainty: "Unknown",
      headline: "",
      description: "",
      instruction: "",
      areaDesc: "Kalamazoo",
      effective: formatUtc(new Date(nowMs - 60 * 60 * 1000)),
      expires: formatUtc(new Date(nowMs + 2 * 60 * 60 * 1000)),
      geometry: null,
      parameters: {},
    };
  }

  function ensurePayloadReady() {
    if (!payload || typeof payload !== "object") {
      payload = { metadata: {}, alerts: [] };
    }
    if (!payload.metadata || typeof payload.metadata !== "object") {
      payload.metadata = {};
    }
    if (!Array.isArray(payload.alerts)) {
      payload.alerts = [];
    }
  }

  function setActiveWindow(alert) {
    const now = Date.now();
    alert.enabled = true;
    alert.effective = formatUtc(new Date(now - 60 * 60 * 1000));
    alert.expires = formatUtc(new Date(now + 2 * 60 * 60 * 1000));
    alert.source = alert.source || "test";
  }

  function expireAlert(alert) {
    alert.enabled = false;
    alert.expires = formatUtc(new Date(Date.now() - 60 * 1000));
    alert.source = alert.source || "test";
  }

  function selectedAlertId() {
    return selectedIndex >= 0 && currentAlerts()[selectedIndex] ? currentAlerts()[selectedIndex].id : null;
  }

  function currentFormAlertId() {
    return byId("field-id")?.value.trim() || null;
  }

  function captureScrollState() {
    return {
      left: window.scrollX || 0,
      top: window.scrollY || 0,
    };
  }

  function restoreScrollState(scrollState) {
    if (!scrollState) {
      return;
    }
    window.requestAnimationFrame(function () {
      window.scrollTo(scrollState.left, scrollState.top);
    });
  }

  function findAlertIndexById(id) {
    if (!id) {
      return -1;
    }
    return currentAlerts().findIndex(function (alert) {
      return alert && alert.id === id;
    });
  }

  function nearestAlertIndex(index) {
    const alerts = currentAlerts();
    if (!alerts.length) {
      return -1;
    }
    const numericIndex = Number.isFinite(index) ? index : 0;
    return Math.min(Math.max(numericIndex, 0), alerts.length - 1);
  }

  function clearSelectedAlertForm() {
    selectedIndex = -1;
    byId("field-enabled").checked = false;
    fillSelect("field-event", eventValues, "");
    ["id", "source", "severity", "urgency", "certainty", "headline", "description", "instruction", "areaDesc", "effective", "expires"].forEach(function (field) {
      byId(`field-${field}`).value = "";
    });
    byId("field-geometry").value = "";
    byId("field-parameters").value = "{}";
    renderParameterFields({});
    geometryDrawPoints = [];
    geometryEditEnabled = false;
    updateLocalTimes();
    renderSelectedGeometryOnMap(null, false);
  }

  function restoreSelectedAlert(selectionState) {
    const state = selectionState || {};
    const preferredIds = [state.preferredId, state.previousId].filter(Boolean);
    let nextIndex = -1;

    preferredIds.some(function (id) {
      nextIndex = findAlertIndexById(id);
      return nextIndex >= 0;
    });

    if (nextIndex < 0) {
      nextIndex = nearestAlertIndex(state.fallbackIndex);
    }

    if (nextIndex >= 0) {
      // Save/reload must hydrate the form from the reloaded payload item, not from index 0 or stale form state.
      selectAlert(nextIndex);
    } else {
      clearSelectedAlertForm();
      renderTable();
    }
  }

  function sortedAlertEntries() {
    const entries = currentAlerts().map(function (alert, index) {
      return { alert, index };
    });
    if (!sortState.key) {
      return entries;
    }
    const valueType = sortValueTypes[sortState.key] || "string";
    const direction = sortState.direction === "desc" ? -1 : 1;
    entries.sort(function (left, right) {
      const leftValue = sortableValue(left.alert, sortState.key, valueType);
      const rightValue = sortableValue(right.alert, sortState.key, valueType);
      if (leftValue < rightValue) {
        return -1 * direction;
      }
      if (leftValue > rightValue) {
        return 1 * direction;
      }
      return left.index - right.index;
    });
    return entries;
  }

  function sortableValue(alert, key, valueType) {
    if (valueType === "boolean") {
      return alert[key] === true ? 1 : 0;
    }
    if (valueType === "date") {
      const time = new Date(alert[key] || "").getTime();
      return Number.isNaN(time) ? 0 : time;
    }
    return String(alert[key] || "").toLowerCase();
  }

  function updateSortIndicators() {
    document.querySelectorAll("[data-sort-indicator]").forEach(function (indicator) {
      const key = indicator.dataset.sortIndicator;
      indicator.textContent = key === sortState.key ? (sortState.direction === "asc" ? "▲" : "▼") : "";
    });
    document.querySelectorAll("[data-sort-key]").forEach(function (button) {
      const active = button.dataset.sortKey === sortState.key;
      button.classList.toggle("sort-header--active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function makeTimeCell(value) {
    const wrapper = document.createElement("div");
    wrapper.className = "time-stack";
    [
      ["UTC", value || ""],
      ["Local", formatLocal(value || "").replace(/^Local: /, "")],
    ].forEach(function (row) {
      const label = document.createElement("span");
      label.className = "time-stack__label";
      label.textContent = `${row[0]}:`;
      const text = document.createElement("span");
      text.className = "time-stack__value";
      text.textContent = row[1] || "-";
      wrapper.append(label, text);
    });
    return wrapper;
  }

  function makeBadge(text, modifier, backgroundColor) {
    const badge = document.createElement("span");
    badge.className = `test-alert-badge ${modifier || ""}`.trim();
    badge.textContent = text || "-";
    if (backgroundColor) {
      badge.style.backgroundColor = backgroundColor;
    }
    return badge;
  }

  function makeMetaItem(label, value) {
    const item = document.createElement("div");
    item.className = "test-alert-meta__item";
    const labelEl = document.createElement("span");
    labelEl.className = "test-alert-meta__label";
    labelEl.textContent = `${label}:`;
    const valueEl = document.createElement("span");
    valueEl.className = "test-alert-meta__value";
    valueEl.textContent = value || "-";
    item.append(labelEl, valueEl);
    return item;
  }

  function renderTable() {
    const list = byId("test-alert-table");
    const alerts = currentAlerts();
    byId("test-alert-count").textContent = String(alerts.length);
    updateSortIndicators();

    if (!alerts.length) {
      const empty = document.createElement("p");
      empty.className = "alert-empty";
      empty.textContent = "No test alerts found.";
      list.replaceChildren(empty);
      return;
    }

    list.replaceChildren(...sortedAlertEntries().map(function (entry) {
      const alert = entry.alert;
      const index = entry.index;
      const row = document.createElement("article");
      row.className = "test-alert-card";
      row.style.setProperty("--event-color", getAlertColor(alert));
      if (index === selectedIndex) {
        row.classList.add("selected-row");
      }

      const enabled = document.createElement("input");
      enabled.type = "checkbox";
      enabled.checked = alert.enabled === true;
      enabled.setAttribute("aria-label", `Enable ${alert.event || alert.id || "test alert"}`);
      enabled.addEventListener("change", function () {
        alert.enabled = enabled.checked;
        if (index === selectedIndex) {
          byId("field-enabled").checked = enabled.checked;
        }
      });

      const actionsWrap = document.createElement("div");
      actionsWrap.className = "actions-wrap";
      [
        [
          ["Edit", "", function () { selectAlert(index); }],
          ["Clone", "", function () { cloneAlert(index).catch(showError); }],
        ],
        [
          ["Activate", "primary-action", function () { activateAlertAtIndex(index).catch(showError); }],
          ["Expire", "", function () { expireAlertAtIndex(index).catch(showError); }],
        ],
        [
          ["Delete", "danger-action", function () { deleteAlert(index).catch(showError); }],
        ],
      ].forEach(function (group) {
        const groupEl = document.createElement("div");
        groupEl.className = "actions-wrap__group";
        group.forEach(function (config) {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = config[0];
          if (config[1]) {
            button.className = config[1];
          }
          button.addEventListener("click", config[2]);
          groupEl.append(button);
        });
        actionsWrap.append(groupEl);
      });

      const topLine = document.createElement("div");
      topLine.className = "test-alert-card__topline";
      const titleWrap = document.createElement("div");
      titleWrap.className = "test-alert-card__title-wrap";
      const title = document.createElement("h3");
      title.className = "test-alert-card__title";
      title.textContent = alert.event || "Untitled alert";
      titleWrap.append(title);
      const badges = document.createElement("div");
      badges.className = "test-alert-card__badges";
      badges.append(makeBadge(alert.severity || "Unknown", "", getAlertColor({ severity: alert.severity })));
      const enabledWrap = document.createElement("label");
      enabledWrap.className = "test-alert-card__enabled";
      const enabledText = document.createElement("span");
      enabledText.textContent = "Enabled";
      enabledWrap.append(enabled, enabledText);
      topLine.append(titleWrap, badges, enabledWrap);

      const idLine = document.createElement("div");
      idLine.className = "test-alert-card__id";
      const idLabel = document.createElement("span");
      idLabel.textContent = "ID:";
      const idValue = document.createElement("code");
      idValue.textContent = alert.id || "-";
      idValue.title = alert.id || "";
      idLine.append(idLabel, idValue);

      const meta = document.createElement("div");
      meta.className = "test-alert-meta";
      meta.append(
        makeMetaItem("Area", alert.areaDesc || ""),
        makeMetaItem("Urgency", alert.urgency || ""),
        makeMetaItem("Certainty", alert.certainty || "")
      );

      const times = document.createElement("div");
      times.className = "test-alert-times";
      [
        ["Effective", alert.effective || ""],
        ["Expires", alert.expires || ""],
      ].forEach(function (config) {
        const timeGroup = document.createElement("div");
        timeGroup.className = "test-alert-time-group";
        const label = document.createElement("span");
        label.className = "test-alert-time-group__label";
        label.textContent = `${config[0]}:`;
        timeGroup.append(label, makeTimeCell(config[1]));
        times.append(timeGroup);
      });

      row.append(topLine, idLine, meta, times, actionsWrap);
      return row;
    }));
  }

  function getParameterObjectFromRaw() {
    const parsed = parseJsonField("field-parameters", "Parameters");
    if (parsed === null) {
      return {};
    }
    if (typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Parameters JSON must be an object.");
    }
    return parsed;
  }

  function renderParameterFields(parameters) {
    const container = byId("parameter-fields");
    container.replaceChildren(...commonParameterKeys.map(function (key) {
      const label = document.createElement("label");
      label.textContent = key;
      const input = document.createElement("input");
      input.id = `param-${key}`;
      input.dataset.parameterKey = key;
      input.value = Array.isArray(parameters?.[key]) ? parameters[key].join(", ") : "";
      label.append(input);
      return label;
    }));
  }

  function syncFriendlyParametersToRaw() {
    const parameters = getParameterObjectFromRaw();
    commonParameterKeys.forEach(function (key) {
      const input = byId(`param-${key}`);
      if (!input) {
        return;
      }
      const value = input.value.trim();
      if (value) {
        parameters[key] = [value];
      } else {
        delete parameters[key];
      }
    });
    byId("field-parameters").value = prettyJson(parameters);
    return parameters;
  }

  function setGeometryFriendlyFields(geometry) {
    byId("geometry-center-lat").value = "";
    byId("geometry-center-lon").value = "";
    byId("geometry-shape-type").value = "rectangle";
    if (!geometry || geometry.type !== "Polygon" || !Array.isArray(geometry.coordinates?.[0])) {
      updateGeometryMarkerLabel();
      return;
    }
    const ring = geometry.coordinates[0].filter(function (coord) {
      return Array.isArray(coord) && coord.length >= 2;
    });
    if (!ring.length) {
      return;
    }
    const lons = ring.map(function (coord) { return Number(coord[0]); }).filter(Number.isFinite);
    const lats = ring.map(function (coord) { return Number(coord[1]); }).filter(Number.isFinite);
    if (!lons.length || !lats.length) {
      return;
    }
    if (!isRectangleGeometry(geometry)) {
      byId("geometry-shape-type").value = "polygon";
    }
    byId("geometry-center-lat").value = ((Math.min(...lats) + Math.max(...lats)) / 2).toFixed(6);
    byId("geometry-center-lon").value = ((Math.min(...lons) + Math.max(...lons)) / 2).toFixed(6);
    if (geometryMarker) {
      geometryMarker.setLngLat([
        Number(byId("geometry-center-lon").value),
        Number(byId("geometry-center-lat").value),
      ]);
    }
    updateGeometryMarkerLabel();
  }

  function isRectangleGeometry(geometry) {
    const ring = geometry?.coordinates?.[0];
    return geometry?.type === "Polygon" && Array.isArray(ring) && ring.length === 5;
  }

  function getClosedRing(points) {
    if (!Array.isArray(points) || points.length < 3) {
      return null;
    }
    const ring = points.map(function (point) {
      return [Number(point[0].toFixed(6)), Number(point[1].toFixed(6))];
    });
    const first = ring[0];
    const last = ring[ring.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      ring.push([first[0], first[1]]);
    }
    return ring;
  }

  function polygonFromPoints(points) {
    const ring = getClosedRing(points);
    if (!ring) {
      throw new Error("Polygon must include at least three points.");
    }
    const geometry = {
      type: "Polygon",
      coordinates: [ring],
    };
    validateGeometry(geometry);
    return geometry;
  }

  function buildRectangleGeometry() {
    const lat = Number.parseFloat(byId("geometry-center-lat").value);
    const lon = Number.parseFloat(byId("geometry-center-lon").value);
    const halfWidth = Number.parseFloat(byId("geometry-half-width").value);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      throw new Error("Invalid latitude.");
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      throw new Error("Invalid longitude.");
    }
    if (!Number.isFinite(halfWidth) || halfWidth <= 0) {
      throw new Error("Half-width miles must be greater than 0.");
    }

    const latDelta = halfWidth / 69;
    const lonDelta = halfWidth / (Math.max(Math.cos(lat * Math.PI / 180), 0.01) * 69);
    const west = Number((lon - lonDelta).toFixed(6));
    const east = Number((lon + lonDelta).toFixed(6));
    const south = Number((lat - latDelta).toFixed(6));
    const north = Number((lat + latDelta).toFixed(6));
    const geometry = {
      type: "Polygon",
      coordinates: [[[west, north], [east, north], [east, south], [west, south], [west, north]]],
    };
    return geometry;
  }

  function setGeometryField(geometry, statusMessage) {
    suppressGeometryFieldInput = true;
    byId("field-geometry").value = prettyJson(geometry);
    suppressGeometryFieldInput = false;
  }

  function commitGeometryState(geometry, statusMessage, options) {
    const shouldSyncMarkers = !options || options.syncMarkers !== false;
    validateGeometry(geometry);
    setGeometryField(geometry, statusMessage);
    if (payload && Array.isArray(payload.alerts) && selectedIndex >= 0 && payload.alerts[selectedIndex]) {
      payload.alerts[selectedIndex].geometry = geometry;
    }
    if (!geometry) {
      geometryDrawPoints = [];
      geometryEditEnabled = false;
      byId("edit-polygon").classList.remove("is-active");
    }
    renderSelectedGeometryOnMap(geometry, false);
    if (shouldSyncMarkers) {
      syncVertexMarkers(geometry);
    }
    if (geometry && validateGeometryForUi(geometry) && statusMessage) {
      setGeometryStatus(statusMessage);
      setEditorMessage("Geometry updated", "success");
    }
  }

  function updateRectanglePreview() {
    if (byId("geometry-shape-type").value !== "rectangle" || geometryMode !== "rectangle") {
      return;
    }
    try {
      commitGeometryState(buildRectangleGeometry(), "Rectangle preview updated.");
    } catch (error) {
      const message = error.message || "Invalid rectangle geometry.";
      setGeometryStatus(message);
      setEditorMessage(message, "error");
    }
  }

  function validateGeometryControlsBeforeSave() {
    if (byId("geometry-shape-type").value === "rectangle" || geometryMode === "rectangle") {
      const hasRectangleInput = ["geometry-center-lat", "geometry-center-lon"].some(function (id) {
        return byId(id).value.trim();
      });
      if (hasRectangleInput) {
        buildRectangleGeometry();
      }
    }
  }

  function emptyGeometryFeatureCollection() {
    return { type: "FeatureCollection", features: [] };
  }

  function geometryFeatureCollection(geometry, alert) {
    if (!geometry) {
      return emptyGeometryFeatureCollection();
    }
    return {
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        properties: {
          color: getAlertColor(alert),
          event: alert?.event || "",
        },
        geometry,
      }],
    };
  }

  function updateGeometryMarkerLabel() {
    if (!geometryMarker) {
      return;
    }
    const lat = Number.parseFloat(byId("geometry-center-lat").value);
    const lon = Number.parseFloat(byId("geometry-center-lon").value);
    const markerEl = geometryMarker.getElement();
    const label = markerEl.querySelector(".geometry-center-marker__label");
    if (!label) {
      return;
    }
    label.textContent = Number.isFinite(lat) && Number.isFinite(lon)
      ? `${lat.toFixed(5)}, ${lon.toFixed(5)}`
      : "No center";
  }

  function makeCenterMarkerElement() {
    const marker = document.createElement("div");
    marker.className = "geometry-center-marker";
    const dot = document.createElement("span");
    dot.className = "geometry-center-marker__dot";
    const label = document.createElement("span");
    label.className = "geometry-center-marker__label";
    marker.append(dot, label);
    return marker;
  }

  function clearVertexMarkers() {
    geometryVertexMarkers.forEach(function (marker) {
      marker.remove();
    });
    geometryVertexMarkers = [];
  }

  function getEditablePolygonPoints(geometry) {
    const ring = geometry?.coordinates?.[0];
    if (!Array.isArray(ring) || ring.length < 4) {
      return [];
    }
    return ring.slice(0, -1).map(function (coord) {
      return [Number(coord[0]), Number(coord[1])];
    }).filter(function (coord) {
      return Number.isFinite(coord[0]) && Number.isFinite(coord[1]);
    });
  }

  function makeVertexMarkerElement(index) {
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = "geometry-vertex-marker";
    marker.textContent = String(index + 1);
    marker.setAttribute("aria-label", `Polygon point ${index + 1}`);
    return marker;
  }

  function syncVertexMarkers(geometry) {
    clearVertexMarkers();
    if (!geometryMap || !window.mapboxgl || (!geometryEditEnabled && geometryMode !== "draw")) {
      return;
    }
    const points = geometryMode === "draw" ? geometryDrawPoints : getEditablePolygonPoints(geometry);
    points.forEach(function (point, index) {
      const marker = new window.mapboxgl.Marker({
        element: makeVertexMarkerElement(index),
        draggable: geometryEditEnabled,
      }).setLngLat(point).addTo(geometryMap);
      if (geometryEditEnabled) {
        marker.on("drag", function () {
          const lngLat = marker.getLngLat();
          const nextPoints = getEditablePolygonPoints(readCurrentGeometryForMap());
          nextPoints[index] = [lngLat.lng, lngLat.lat];
          try {
            const nextGeometry = polygonFromPoints(nextPoints);
            commitGeometryState(nextGeometry, "", { syncMarkers: false });
            validateGeometryForUi(nextGeometry);
          } catch (error) {
            setGeometryStatus(error.message || "Invalid polygon.");
          }
        });
        marker.on("dragend", function () {
          syncVertexMarkers(readCurrentGeometryForMap());
        });
      }
      geometryVertexMarkers.push(marker);
    });
  }

  function ensureGeometryLayers() {
    if (!geometryMap || !geometryMapLoaded) {
      return false;
    }
    if (!geometryMap.getSource(geometrySourceId)) {
      geometryMap.addSource(geometrySourceId, {
        type: "geojson",
        data: emptyGeometryFeatureCollection(),
      });
    }
    if (!geometryMap.getLayer(geometryFillLayerId)) {
      geometryMap.addLayer({
        id: geometryFillLayerId,
        type: "fill",
        source: geometrySourceId,
        paint: {
          "fill-color": ["coalesce", ["get", "color"], defaultGeometryColor],
          "fill-opacity": 0.36,
        },
      });
    }
    if (!geometryMap.getLayer(geometryLineLayerId)) {
      geometryMap.addLayer({
        id: geometryLineLayerId,
        type: "line",
        source: geometrySourceId,
        paint: {
          "line-color": ["coalesce", ["get", "color"], defaultGeometryColor],
          "line-width": 4,
        },
      });
    }
    return true;
  }

  function fitMapToPolygon(geometry) {
    if (!geometryMap || !geometry || !Array.isArray(geometry.coordinates?.[0]) || !window.mapboxgl) {
      return;
    }
    const coords = geometry.coordinates[0].filter(function (coord) {
      return Array.isArray(coord) && coord.length >= 2;
    });
    if (!coords.length) {
      return;
    }
    const bounds = coords.reduce(function (currentBounds, coord) {
      return currentBounds.extend(coord);
    }, new window.mapboxgl.LngLatBounds(coords[0], coords[0]));
    geometryMap.fitBounds(bounds, { padding: 48, maxZoom: 13, duration: 250 });
  }

  function renderGeometryOnMap(geometry, alert, fitBounds) {
    const color = getAlertColor(alert);
    if (!geometryMap || !ensureGeometryLayers()) {
      return;
    }
    const collection = geometryFeatureCollection(geometry, alert);
    geometryMap.getSource(geometrySourceId).setData(collection);
    if (fitBounds && geometry) {
      fitMapToPolygon(geometry);
    }
    setGeometryStatus(geometry ? `Geometry rendered on map using ${color}.` : "No geometry to render.");
  }

  function readCurrentGeometryForMap() {
    const raw = byId("field-geometry")?.value.trim();
    if (!raw) {
      return null;
    }
    try {
      return validateGeometry(JSON.parse(raw));
    } catch (error) {
      setGeometryStatus(error.message || "Invalid geometry.");
      return null;
    }
  }

  function renderSelectedGeometryOnMap(geometry, fitBounds) {
    const selectedAlert = currentAlerts()[selectedIndex] || {};
    const alert = {
      event: byId("field-event")?.value || selectedAlert.event || "",
      severity: byId("field-severity")?.value || selectedAlert.severity || "",
    };
    renderGeometryOnMap(geometry, alert, fitBounds !== false);
  }

  function getTargetCenter() {
    const target = payload && payload.metadata && payload.metadata.target ? payload.metadata.target : {};
    const latitude = Number(target.latitude);
    const longitude = Number(target.longitude);
    if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
      return {
        latitude,
        longitude,
        zip: target.zip || target.postal_code || "49002",
      };
    }
    return { latitude: 42.2012, longitude: -85.58, zip: "49002" };
  }

  function useTargetCenter() {
    const target = getTargetCenter();
    byId("geometry-zip").value = target.zip || "";
    setGeometryCenter(target.latitude, target.longitude, true);
    updateRectanglePreview();
    setGeometryStatus("ZIP lookup not available yet; using metadata target coordinates.");
  }

  function setGeometryCenter(latitude, longitude, moveMap) {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      throw new Error("Center latitude must be between -90 and 90.");
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      throw new Error("Center longitude must be between -180 and 180.");
    }
    byId("geometry-center-lat").value = lat.toFixed(6);
    byId("geometry-center-lon").value = lon.toFixed(6);
    if (geometryMarker) {
      geometryMarker.setLngLat([lon, lat]);
    }
    updateGeometryMarkerLabel();
    if (geometryMap && moveMap) {
      geometryMap.setCenter([lon, lat]);
    }
  }

  function handleMapCenterClick(latitude, longitude) {
    if (geometryMode === "draw") {
      addPolygonPoint(longitude, latitude);
      return;
    }
    setGeometryCenter(latitude, longitude, false);
    updateRectanglePreview();
    setGeometryStatus("Map click set center point and updated the rectangle.");
  }

  function addPolygonPoint(longitude, latitude) {
    const lon = Number(longitude);
    const lat = Number(latitude);
    if (!Number.isFinite(lon) || lon < -180 || lon > 180 || !Number.isFinite(lat) || lat < -90 || lat > 90) {
      setGeometryStatus("Polygon point must be valid longitude/latitude.");
      return;
    }
    geometryDrawPoints.push([lon, lat]);
    if (geometryDrawPoints.length < 3) {
      syncVertexMarkers(null);
      setGeometryStatus(`Polygon needs ${3 - geometryDrawPoints.length} more point${geometryDrawPoints.length === 2 ? "" : "s"}.`);
      return;
    }
    try {
      const geometry = polygonFromPoints(geometryDrawPoints);
      commitGeometryState(geometry, "Polygon drawing updated.");
    } catch (error) {
      setGeometryStatus(error.message || "Invalid polygon.");
    }
  }

  function initializeGeometryMap() {
    const config = window.MOLECAST_TEST_ALERT_CONFIG || {};
    const mapboxConfig = config.mapbox || {};
    const mapEl = byId("geometry-map");
    if (!mapEl || geometryMap) {
      return;
    }
    const target = getTargetCenter();
    byId("geometry-zip").value = target.zip || "";
    if (!geometryMapClickFallbackWired) {
      document.addEventListener("click", function (event) {
        if (geometryMap) {
          return;
        }
        const currentMapEl = byId("geometry-map");
        if (!currentMapEl || !currentMapEl.contains(event.target)) {
          return;
        }
        setCenterFromMapElementClick(event, getTargetCenter());
      }, true);
      geometryMapClickFallbackWired = true;
    }
    if (!window.mapboxgl || !mapboxConfig.enabled || !mapboxConfig.token) {
      mapEl.textContent = "Map unavailable. Mapbox is not configured, but latitude/longitude fields still work.";
      setGeometryStatus("Map unavailable; using metadata target coordinates.");
      setGeometryCenter(target.latitude, target.longitude, false);
      return;
    }
    window.mapboxgl.accessToken = mapboxConfig.token;
    geometryMap = new window.mapboxgl.Map({
      container: "geometry-map",
      style: "mapbox://styles/mapbox/streets-v12",
      center: [target.longitude, target.latitude],
      zoom: 10,
      minZoom: 5,
      maxZoom: 16,
    });
    geometryMarker = new window.mapboxgl.Marker({ element: makeCenterMarkerElement(), anchor: "bottom" })
      .setLngLat([target.longitude, target.latitude])
      .addTo(geometryMap);
    geometryMap.on("click", function (event) {
      handleMapCenterClick(event.lngLat.lat, event.lngLat.lng);
    });
    geometryMap.on("load", function () {
      geometryMapLoaded = true;
      renderSelectedGeometryOnMap(readCurrentGeometryForMap(), false);
    });
    geometryMap.on("error", function (event) {
      const message = event && event.error && event.error.message ? event.error.message : "Map error";
      setGeometryStatus(message);
    });
    setGeometryCenter(target.latitude, target.longitude, false);
  }

  function setCenterFromMapElementClick(event, fallbackCenter) {
    const mapEl = byId("geometry-map");
    const rect = mapEl.getBoundingClientRect();
    if (geometryMap && typeof geometryMap.unproject === "function") {
      const point = geometryMap.unproject([event.clientX - rect.left, event.clientY - rect.top]);
      handleMapCenterClick(point.lat, point.lng);
      return;
    }
    const xRatio = (event.clientX - rect.left) / rect.width - 0.5;
    const yRatio = (event.clientY - rect.top) / rect.height - 0.5;
    const baseLat = Number(byId("geometry-center-lat").value) || fallbackCenter.latitude;
    const baseLon = Number(byId("geometry-center-lon").value) || fallbackCenter.longitude;
    const lat = baseLat - yRatio * 0.1;
    const lon = baseLon + xRatio * 0.1;
    handleMapCenterClick(lat, lon);
  }

  function setGeometryMode(nextMode) {
    geometryMode = nextMode;
    byId("geometry-shape-type").value = nextMode === "draw" ? "polygon" : nextMode;
    byId("geometry-half-width").disabled = nextMode !== "rectangle";
    byId("draw-polygon").classList.toggle("is-active", nextMode === "draw");
    byId("edit-polygon").classList.toggle("is-active", geometryEditEnabled);
    if (nextMode !== "draw") {
      geometryDrawPoints = [];
    }
    syncVertexMarkers(readCurrentGeometryForMap());
  }

  function startPolygonDrawing() {
    geometryEditEnabled = false;
    geometryDrawPoints = [];
    setGeometryMode("draw");
    commitGeometryState(null);
    setGeometryStatus("Draw polygon: click at least three points on the map.");
  }

  function togglePolygonEditing() {
    const geometry = readCurrentGeometryForMap();
    if (!geometry) {
      geometryEditEnabled = false;
      setGeometryMode("polygon");
      setGeometryStatus("Draw or load a polygon before editing.");
      return;
    }
    if (!validateGeometryForUi(geometry)) {
      return;
    }
    geometryEditEnabled = !geometryEditEnabled;
    setGeometryMode("polygon");
    setGeometryStatus(geometryEditEnabled ? "Edit polygon: drag numbered points to adjust the shape." : "Polygon edit mode off.");
  }

  function clearGeometry() {
    setGeometryMode("rectangle");
    commitGeometryState(null);
    setGeometryStatus("Geometry cleared.");
  }

  function selectAlert(index) {
    const alert = currentAlerts()[index];
    if (!alert) {
      return;
    }

    selectedIndex = index;
    renderSelectedAlertForm(alert);
    renderTable();
    renderSelectedGeometryOnMap(alert.geometry);
  }

  function renderSelectedAlertForm(alert) {
    alert.source = alert.source || "test";
    byId("field-enabled").checked = alert.enabled === true;
    fillSelect("field-event", eventValues, alert.event || "");
    ["id", "source", "severity", "urgency", "certainty", "headline", "description", "instruction", "areaDesc", "effective", "expires"].forEach(function (field) {
      byId(`field-${field}`).value = alert[field] || "";
    });
    byId("field-geometry").value = prettyJson(alert.geometry);
    byId("field-parameters").value = prettyJson(alert.parameters || {});
    renderParameterFields(alert.parameters || {});
    geometryDrawPoints = [];
    geometryEditEnabled = false;
    setGeometryFriendlyFields(alert.geometry);
    geometryMode = byId("geometry-shape-type").value;
    byId("geometry-half-width").disabled = geometryMode !== "rectangle";
    byId("draw-polygon").classList.remove("is-active");
    byId("edit-polygon").classList.remove("is-active");
    updateLocalTimes();
  }

  function readFormAlert() {
    const id = byId("field-id").value.trim();
    const event = byId("field-event").value.trim();
    if (!id) {
      throw new Error("Missing required field: id");
    }
    if (!event) {
      throw new Error("Missing required field: event");
    }
    validateGeometryControlsBeforeSave();
    const geometry = validateGeometry(parseJsonField("field-geometry", "Geometry"));
    const parameters = syncFriendlyParametersToRaw();
    const effective = validateUtc(byId("field-effective").value.trim(), "Effective");
    const expires = validateUtc(byId("field-expires").value.trim(), "Expires");
    if (!effective) {
      throw new Error("Missing required field: effective");
    }
    if (!expires) {
      throw new Error("Missing required field: expires");
    }
    if (new Date(expires) <= new Date(effective) && byId("field-enabled").checked) {
      throw new Error("Invalid timestamp: expires must be after effective.");
    }
    const areaDesc = byId("field-areaDesc").value.trim();
    if (!areaDesc) {
      setEditorMessage("Warning: areaDesc is blank; active alert matching may fall back to defaults.", "warning");
    }
    return {
      enabled: byId("field-enabled").checked,
      id,
      source: byId("field-source").value.trim() || "test",
      event,
      severity: byId("field-severity").value,
      urgency: byId("field-urgency").value,
      certainty: byId("field-certainty").value,
      headline: byId("field-headline").value,
      description: byId("field-description").value,
      instruction: byId("field-instruction").value,
      areaDesc,
      effective,
      expires,
      geometry,
      parameters,
    };
  }

  function applyFormToPayload() {
    if (selectedIndex < 0) {
      throw new Error("Select an alert first.");
    }
    const updated = readFormAlert();
    const duplicate = currentAlerts().find(function (alert, index) {
      return index !== selectedIndex && alert.id === updated.id;
    });
    if (duplicate) {
      throw new Error(`Duplicate alert id: ${updated.id}`);
    }
    currentAlerts()[selectedIndex] = updated;
    renderTable();
    renderSelectedGeometryOnMap(updated.geometry);
    return updated;
  }

  async function updateStatusPanel(statusData) {
    const data = statusData || await fetchJson(STATUS_URL);
    byId("test-alert-file").textContent = data.test_file || "";
    byId("test-alert-count").textContent = String(data.test_total ?? 0);
    byId("test-alert-enabled-count").textContent = String(data.test_enabled ?? 0);
    byId("test-alert-active-count").textContent = String(data.test_active ?? 0);
    byId("nws-alert-active-count").textContent = String(data.nws_active ?? 0);
    byId("total-alert-active-count").textContent = String(data.total_active ?? 0);
    byId("alert-source-breakdown").textContent = `test: ${data.sources?.test ?? 0}, nws: ${data.sources?.nws ?? 0}`;
    byId("test-alert-last-loaded").textContent = data.last_loaded ? new Date(data.last_loaded).toLocaleString() : "Never";
    byId("test-alert-last-saved").textContent = data.last_saved ? new Date(data.last_saved).toLocaleString() : "Unknown";
    byId("active-alert-refreshed").textContent = data.active_refreshed_at ? new Date(data.active_refreshed_at).toLocaleString() : "Unknown";
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map(function (item) { return item.msg || JSON.stringify(item); }).join("; ")
        : data.detail;
      throw new Error(detail || "Request failed.");
    }
    return data;
  }

  async function loadAlerts(options) {
    const scrollState = options && options.preserveScroll ? captureScrollState() : null;
    const selectionState = {
      preferredId: options && options.keepSelectedId,
      previousId: options && options.previousSelectedId,
      fallbackIndex: options && Number.isFinite(options.fallbackIndex) ? options.fallbackIndex : selectedIndex,
    };
    setStatus("Loading");
    const data = await fetchJson(API_URL);
    payload = data.payload;
    ensurePayloadReady();
    payload.alerts.forEach(function (alert) {
      if (alert && typeof alert === "object") {
        alert.source = alert.source || "test";
        alert.enabled = alert.enabled === true;
      }
    });
    initializeGeometryMap();
    restoreSelectedAlert(selectionState);
    await updateStatusPanel();
    setStatus(`Loaded ${new Date(data.loaded_at).toLocaleTimeString()}`);
    restoreScrollState(scrollState);
  }

  async function saveAll(options) {
    const applyForm = !options || options.applyForm !== false;
    if (!payload) {
      return null;
    }
    const formSelectedId = currentFormAlertId();
    const previousSelectedId = selectedAlertId();
    const previousSelectedIndex = selectedIndex;
    const scrollState = captureScrollState();
    setEditorMessage("", "success");
    let savedAlert = null;
    if (applyForm && selectedIndex >= 0) {
      savedAlert = applyFormToPayload();
    }
    const keepSelectedId = options && options.keepSelectedId ? options.keepSelectedId : savedAlert?.id || formSelectedId || previousSelectedId;
    const fallbackIndex = options && Number.isFinite(options.fallbackIndex) ? options.fallbackIndex : previousSelectedIndex;
    validatePayloadBeforeSave();
    setStatus("Saving");
    const data = await fetchJson(API_URL, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setStatus(`Saved ${new Date(data.saved_at).toLocaleTimeString()} - active test alerts ${data.refresh.active_test_alert_count}`);
    setEditorMessage("Saved successfully", "success");
    await loadAlerts({
      keepSelectedId,
      previousSelectedId: formSelectedId || previousSelectedId,
      fallbackIndex,
      preserveScroll: false,
    });
    restoreScrollState(scrollState);
    return data;
  }

  async function refreshActiveAlerts() {
    setStatus("Refreshing active alerts");
    const data = await fetchJson(REFRESH_URL, { method: "POST" });
    await updateStatusPanel();
    setStatus("Active alerts refreshed");
    setEditorMessage("Active alerts refreshed", "success");
  }

  async function addAlert() {
    ensurePayloadReady();
    payload.alerts.push(makeEmptyAlert());
    selectedIndex = payload.alerts.length - 1;
    const addedId = payload.alerts[selectedIndex].id;
    await saveAll({ applyForm: false, keepSelectedId: addedId });
  }

  async function cloneAlert(index) {
    const source = currentAlerts()[index];
    if (!source) {
      return;
    }
    const cloned = cloneValue(source);
    cloned.enabled = false;
    cloned.source = cloned.source || "test";
    cloned.id = `${source.id || "test-alert"}-copy`;
    let suffix = 2;
    while (currentAlerts().some(function (alert) { return alert.id === cloned.id; })) {
      cloned.id = `${source.id || "test-alert"}-copy-${suffix}`;
      suffix += 1;
    }
    payload.alerts.splice(index + 1, 0, cloned);
    selectedIndex = index + 1;
    await saveAll({ applyForm: false, keepSelectedId: cloned.id });
  }

  async function deleteAlert(index) {
    const alert = currentAlerts()[index];
    if (!alert || !window.confirm(`Delete ${alert.id}?`)) {
      return;
    }
    payload.alerts.splice(index, 1);
    selectedIndex = Math.min(index, payload.alerts.length - 1);
    await saveAll({ applyForm: false, fallbackIndex: index });
  }

  async function disableSelected() {
    if (selectedIndex < 0) {
      return;
    }
    byId("field-enabled").checked = false;
    applyFormToPayload();
    await saveAll({ applyForm: false, keepSelectedId: currentAlerts()[selectedIndex]?.id });
  }

  async function disableAll() {
    currentAlerts().forEach(function (alert) {
      alert.enabled = false;
      alert.source = alert.source || "test";
    });
    if (selectedIndex >= 0) {
      byId("field-enabled").checked = false;
    }
    await saveAll({ applyForm: false, keepSelectedId: currentAlerts()[selectedIndex]?.id });
  }

  async function enableAll() {
    const confirmed = window.confirm("Enable all test alerts and update their UTC effective/expires windows to active now? Effective will be set to 1 hour before current UTC and expires will be set to 2 hours after current UTC.");
    if (!confirmed) {
      return;
    }
    currentAlerts().forEach(setActiveWindow);
    await saveAll({ applyForm: false, keepSelectedId: currentAlerts()[selectedIndex]?.id });
  }

  async function activateAlertAtIndex(index) {
    if (!currentAlerts()[index]) {
      return;
    }
    if (selectedIndex >= 0) {
      applyFormToPayload();
    }
    setActiveWindow(currentAlerts()[index]);
    selectedIndex = index;
    await saveAll({ applyForm: false, keepSelectedId: currentAlerts()[index].id });
  }

  async function expireAlertAtIndex(index) {
    if (!currentAlerts()[index]) {
      return;
    }
    if (selectedIndex >= 0) {
      applyFormToPayload();
    }
    expireAlert(currentAlerts()[index]);
    selectedIndex = index;
    await saveAll({ applyForm: false, keepSelectedId: currentAlerts()[index].id });
  }

  async function setActiveNow() {
    const before = Number.parseInt(byId("before-hours").value, 10) || 1;
    const after = Number.parseInt(byId("after-hours").value, 10) || 2;
    const now = Date.now();
    byId("field-enabled").checked = true;
    byId("field-effective").value = formatUtc(new Date(now - before * 60 * 60 * 1000));
    byId("field-expires").value = formatUtc(new Date(now + after * 60 * 60 * 1000));
    updateLocalTimes();
    applyFormToPayload();
    await saveAll({ applyForm: false, keepSelectedId: currentAlerts()[selectedIndex]?.id });
  }

  function wireEvents() {
    fillSelect("field-severity", severityValues);
    fillSelect("field-urgency", urgencyValues);
    fillSelect("field-certainty", certaintyValues);
    fillSelect("field-event", eventValues);
    byId("reload-alerts").addEventListener("click", function () {
      loadAlerts({
        keepSelectedId: selectedAlertId(),
        fallbackIndex: selectedIndex,
        preserveScroll: true,
      }).catch(showError);
    });
    document.querySelectorAll("[data-sort-key]").forEach(function (button) {
      button.addEventListener("click", function () {
        const key = button.dataset.sortKey;
        if (sortState.key === key) {
          sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
        } else {
          sortState = { key, direction: "asc" };
        }
        renderTable();
      });
    });
    byId("add-alert").addEventListener("click", function () { addAlert().catch(showError); });
    byId("enable-all-alerts").addEventListener("click", function () { enableAll().catch(showError); });
    byId("disable-all-alerts").addEventListener("click", function () { disableAll().catch(showError); });
    byId("save-all-alerts").addEventListener("click", function () { saveAll().catch(showError); });
    byId("refresh-active-alerts").addEventListener("click", function () { refreshActiveAlerts().catch(showError); });
    byId("test-alert-form").addEventListener("submit", function (event) {
      event.preventDefault();
      saveAll().catch(showError);
    });
    byId("set-active-now").addEventListener("click", function () {
      setActiveNow().catch(showError);
    });
    byId("use-target-center").addEventListener("click", function () {
      try {
        useTargetCenter();
        setStatus("Center set from metadata target");
      } catch (error) {
        showError(error);
      }
    });
    byId("draw-polygon").addEventListener("click", startPolygonDrawing);
    byId("edit-polygon").addEventListener("click", togglePolygonEditing);
    byId("clear-geometry").addEventListener("click", clearGeometry);
    byId("geometry-shape-type").addEventListener("change", function () {
      geometryEditEnabled = false;
      setGeometryMode(byId("geometry-shape-type").value);
      if (geometryMode === "rectangle") {
        updateRectanglePreview();
      } else {
        setGeometryStatus("Polygon mode selected. Use Draw Polygon or Edit Polygon.");
      }
    });
    ["geometry-center-lat", "geometry-center-lon", "geometry-half-width"].forEach(function (id) {
      byId(id).addEventListener("input", function () {
        updateGeometryMarkerLabel();
        updateRectanglePreview();
      });
    });
    byId("field-effective").addEventListener("input", updateLocalTimes);
    byId("field-expires").addEventListener("input", updateLocalTimes);
    byId("field-event").addEventListener("change", function () {
      renderSelectedGeometryOnMap(readCurrentGeometryForMap(), false);
    });
    byId("field-severity").addEventListener("change", function () {
      renderSelectedGeometryOnMap(readCurrentGeometryForMap(), false);
    });
    byId("field-geometry").addEventListener("input", function () {
      if (suppressGeometryFieldInput) {
        return;
      }
      geometryDrawPoints = [];
      geometryEditEnabled = false;
      const raw = byId("field-geometry")?.value.trim();
      if (!raw) {
        commitGeometryState(null);
        return;
      }
      const geometry = readCurrentGeometryForMap();
      if (geometry) {
        commitGeometryState(geometry);
        setGeometryFriendlyFields(geometry);
        setGeometryMode(isRectangleGeometry(geometry) ? "rectangle" : "polygon");
        validateGeometryForUi(geometry);
      }
    });
    byId("disable-alert").addEventListener("click", function () { disableSelected().catch(showError); });
    byId("clone-alert").addEventListener("click", function () { cloneAlert(selectedIndex).catch(showError); });
    byId("delete-alert").addEventListener("click", function () { deleteAlert(selectedIndex).catch(showError); });
  }

  function showError(error) {
    const message = error.message || String(error);
    setStatus(message);
    setEditorMessage(message, "error");
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireEvents();
    loadAlerts().catch(showError);
  });
})();
