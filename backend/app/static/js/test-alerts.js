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
  const defaultGeometryColor = "#3399FF";
  const geometrySourceId = "test-alert-editor-geometry";
  const geometryFillLayerId = "test-alert-editor-geometry-fill";
  const geometryLineLayerId = "test-alert-editor-geometry-line";

  let payload = null;
  let selectedIndex = -1;
  let sortState = { key: "", direction: "asc" };
  let geometryMap = null;
  let geometryMarker = null;
  let geometryMapClickFallbackWired = false;
  let geometryMapLoaded = false;

  function byId(id) {
    return document.getElementById(id);
  }

  function setStatus(message) {
    byId("test-alert-status").textContent = message;
  }

  function setGeometryStatus(message) {
    byId("geometry-map-status").textContent = message;
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
      throw new Error(`${label} must be UTC ISO format ending in Z, like 2026-04-27T16:28:53Z.`);
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
      throw new Error("Geometry Polygon must include at least four [longitude, latitude] positions.");
    }
    ring.forEach(function (position) {
      if (!Array.isArray(position) || position.length < 2) {
        throw new Error("Geometry positions must be [longitude, latitude].");
      }
      const lon = Number(position[0]);
      const lat = Number(position[1]);
      if (!Number.isFinite(lon) || lon < -180 || lon > 180 || !Number.isFinite(lat) || lat < -90 || lat > 90) {
        throw new Error("Geometry coordinates must be valid longitude/latitude values.");
      }
    });
    const first = ring[0];
    const last = ring[ring.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      throw new Error("Geometry Polygon ring must be closed.");
    }
    return geometry;
  }

  function validatePayloadBeforeSave() {
    if (!payload || typeof payload !== "object" || !Array.isArray(payload.alerts)) {
      throw new Error("Payload must include an alerts array.");
    }
    payload.alerts.forEach(function (alert, index) {
      if (!alert || typeof alert !== "object" || Array.isArray(alert)) {
        throw new Error(`Alert at index ${index} must be an object.`);
      }
      if (!alert.id || typeof alert.id !== "string") {
        throw new Error(`Alert at index ${index} must include id.`);
      }
      if (!alert.event || typeof alert.event !== "string") {
        throw new Error(`Alert ${alert.id} must include event.`);
      }
      if (typeof alert.enabled !== "boolean") {
        throw new Error(`Alert ${alert.id} enabled must be true or false.`);
      }
      const effectiveAt = parseUtcRequired(alert.effective || "", `Alert ${alert.id} effective`);
      const expiresAt = parseUtcRequired(alert.expires || "", `Alert ${alert.id} expires`);
      if (expiresAt <= effectiveAt) {
        throw new Error(`Alert ${alert.id} expires must be after effective.`);
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
      if (!alert.areaDesc || typeof alert.areaDesc !== "string" || !alert.areaDesc.trim()) {
        throw new Error(`Alert ${alert.id} areaDesc must not be blank.`);
      }
      validateGeometry(alert.geometry ?? null);
      if (alert.parameters !== null && alert.parameters !== undefined && (typeof alert.parameters !== "object" || Array.isArray(alert.parameters))) {
        throw new Error(`Alert ${alert.id} parameters must be an object or empty.`);
      }
      alert.source = alert.source || "test";
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

  function getEventColor(event) {
    const map = {
      "Tornado Warning": "#FF0000",
      "Tornado Watch": "#FFFF00",
      "Severe Thunderstorm Warning": "#FFA500",
      "Severe Thunderstorm Watch": "#DB7093",
      "Flash Flood Warning": "#00FF00",
      "Flood Warning": "#00FF00",
      "Winter Storm Warning": "#FF69B4",
      "Blizzard Warning": "#00FFFF",
      "Ice Storm Warning": "#FF00FF",
      "High Wind Warning": "#DAA520",
      "Heat Advisory": "#FF7F50",
      "Excessive Heat Warning": "#FF0000",
      "Dense Fog Advisory": "#708090",
      "Special Weather Statement": "#FFE4B5",
    };

    return map[event] || defaultGeometryColor;
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

  function renderTable() {
    const tbody = byId("test-alert-table");
    const alerts = currentAlerts();
    byId("test-alert-count").textContent = String(alerts.length);
    updateSortIndicators();

    if (!alerts.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 11;
      cell.textContent = "No test alerts found.";
      row.append(cell);
      tbody.replaceChildren(row);
      return;
    }

    tbody.replaceChildren(...sortedAlertEntries().map(function (entry) {
      const alert = entry.alert;
      const index = entry.index;
      const row = document.createElement("tr");
      if (index === selectedIndex) {
        row.className = "selected-row";
      }

      const enabled = document.createElement("input");
      enabled.type = "checkbox";
      enabled.checked = alert.enabled === true;
      enabled.addEventListener("change", function () {
        alert.enabled = enabled.checked;
        if (index === selectedIndex) {
          byId("field-enabled").checked = enabled.checked;
        }
      });

      const actionsCell = document.createElement("td");
      actionsCell.className = "table-actions";
      const actionsWrap = document.createElement("div");
      actionsWrap.className = "actions-wrap";
      [
        ["Edit", "", function () { selectAlert(index); }],
        ["Clone", "", function () { cloneAlert(index).catch(showError); }],
        ["Activate UTC", "primary-action", function () { activateAlertAtIndex(index).catch(showError); }],
        ["Expire", "", function () { expireAlertAtIndex(index).catch(showError); }],
        ["Delete", "danger-action", function () { deleteAlert(index).catch(showError); }],
      ].forEach(function (config) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = config[0];
        if (config[1]) {
          button.className = config[1];
        }
        button.addEventListener("click", config[2]);
        actionsWrap.append(button);
      });
      actionsCell.append(actionsWrap);

      [
        alert.id || "",
        alert.event || "",
        alert.source || "test",
        enabled,
        alert.severity || "",
        alert.urgency || "",
        alert.certainty || "",
        alert.areaDesc || "",
        makeTimeCell(alert.effective || ""),
        makeTimeCell(alert.expires || ""),
      ].forEach(function (value) {
        const cell = document.createElement("td");
        if (value instanceof Node) {
          cell.append(value);
        } else {
          cell.textContent = value;
        }
        row.append(cell);
      });
      row.append(actionsCell);
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
    if (!geometry || geometry.type !== "Polygon" || !Array.isArray(geometry.coordinates?.[0])) {
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
    byId("geometry-center-lat").value = ((Math.min(...lats) + Math.max(...lats)) / 2).toFixed(6);
    byId("geometry-center-lon").value = ((Math.min(...lons) + Math.max(...lons)) / 2).toFixed(6);
    if (geometryMarker) {
      geometryMarker.setLngLat([
        Number(byId("geometry-center-lon").value),
        Number(byId("geometry-center-lat").value),
      ]);
    }
  }

  function generateRectangleGeometry() {
    const lat = Number.parseFloat(byId("geometry-center-lat").value);
    const lon = Number.parseFloat(byId("geometry-center-lon").value);
    const halfWidth = Number.parseFloat(byId("geometry-half-width").value);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      throw new Error("Center latitude must be between -90 and 90.");
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      throw new Error("Center longitude must be between -180 and 180.");
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
    byId("field-geometry").value = prettyJson(geometry);
    setGeometryFriendlyFields(geometry);
    renderSelectedGeometryOnMap();
    return geometry;
  }

  function emptyGeometryFeatureCollection() {
    return { type: "FeatureCollection", features: [] };
  }

  function geometryFeatureCollection(geometry, eventName) {
    if (!geometry) {
      return emptyGeometryFeatureCollection();
    }
    return {
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        properties: {
          color: getEventColor(eventName),
          event: eventName || "",
        },
        geometry,
      }],
    };
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

  function renderGeometryOnMap(geometry, eventName, fitBounds) {
    const color = getEventColor(eventName);
    if (!geometryMap || !ensureGeometryLayers()) {
      return;
    }
    const collection = geometryFeatureCollection(geometry, eventName);
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

  function renderSelectedGeometryOnMap(fitBounds) {
    const eventName = byId("field-event")?.value || currentAlerts()[selectedIndex]?.event || "";
    renderGeometryOnMap(readCurrentGeometryForMap(), eventName, fitBounds !== false);
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
    if (geometryMap && moveMap) {
      geometryMap.setCenter([lon, lat]);
    }
  }

  function handleMapCenterClick(latitude, longitude) {
    setGeometryCenter(latitude, longitude, false);
    setGeometryStatus("Map click set center point. Generate rectangle geometry to update the alert polygon.");
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
    geometryMarker = new window.mapboxgl.Marker({ color: "#dc2626" })
      .setLngLat([target.longitude, target.latitude])
      .addTo(geometryMap);
    geometryMap.on("click", function (event) {
      handleMapCenterClick(event.lngLat.lat, event.lngLat.lng);
    });
    geometryMap.on("load", function () {
      geometryMapLoaded = true;
      renderSelectedGeometryOnMap(false);
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

  function selectAlert(index) {
    const alert = currentAlerts()[index];
    if (!alert) {
      return;
    }

    selectedIndex = index;
    alert.source = alert.source || "test";
    byId("field-enabled").checked = alert.enabled === true;
    fillSelect("field-event", eventValues, alert.event || "");
    ["id", "source", "severity", "urgency", "certainty", "headline", "description", "instruction", "areaDesc", "effective", "expires"].forEach(function (field) {
      byId(`field-${field}`).value = alert[field] || "";
    });
    byId("field-geometry").value = prettyJson(alert.geometry);
    byId("field-parameters").value = prettyJson(alert.parameters || {});
    renderParameterFields(alert.parameters || {});
    setGeometryFriendlyFields(alert.geometry);
    updateLocalTimes();
    renderTable();
    renderSelectedGeometryOnMap();
  }

  function readFormAlert() {
    const id = byId("field-id").value.trim();
    const event = byId("field-event").value.trim();
    if (!id) {
      throw new Error("Alert id is required.");
    }
    if (!event) {
      throw new Error("Event is required.");
    }
    const geometry = validateGeometry(parseJsonField("field-geometry", "Geometry"));
    const parameters = syncFriendlyParametersToRaw();
    const effective = validateUtc(byId("field-effective").value.trim(), "Effective");
    const expires = validateUtc(byId("field-expires").value.trim(), "Expires");
    if (!effective) {
      throw new Error("Effective is required.");
    }
    if (!expires) {
      throw new Error("Expires is required.");
    }
    if (new Date(expires) <= new Date(effective)) {
      throw new Error("Expires must be after effective.");
    }
    const areaDesc = byId("field-areaDesc").value.trim();
    if (!areaDesc) {
      throw new Error("NWS areaDesc / Counties must not be blank.");
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
    renderSelectedGeometryOnMap();
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
      throw new Error(data.detail || "Request failed.");
    }
    return data;
  }

  async function loadAlerts() {
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
    selectedIndex = payload.alerts.length ? 0 : -1;
    renderTable();
    if (selectedIndex >= 0) {
      selectAlert(selectedIndex);
    }
    await updateStatusPanel();
    setStatus(`Loaded ${new Date(data.loaded_at).toLocaleTimeString()}`);
  }

  async function saveAll(options) {
    const applyForm = !options || options.applyForm !== false;
    const keepSelectedId = options && options.keepSelectedId;
    if (!payload) {
      return null;
    }
    if (applyForm && selectedIndex >= 0) {
      applyFormToPayload();
    }
    validatePayloadBeforeSave();
    setStatus("Saving");
    const data = await fetchJson(API_URL, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setStatus(`Saved ${new Date(data.saved_at).toLocaleTimeString()} - active test alerts ${data.refresh.active_test_alert_count}`);
    await loadAlerts();
    if (keepSelectedId) {
      const nextIndex = currentAlerts().findIndex(function (alert) {
        return alert.id === keepSelectedId;
      });
      if (nextIndex >= 0) {
        selectAlert(nextIndex);
      }
    } else if (selectedIndex >= 0) {
      selectAlert(selectedIndex);
    }
    return data;
  }

  async function refreshActiveAlerts() {
    setStatus("Refreshing active alerts");
    const data = await fetchJson(REFRESH_URL, { method: "POST" });
    await updateStatusPanel();
    setStatus(`Refreshed - active test alerts ${data.active_test_alert_count}`);
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
    await saveAll({ applyForm: false });
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
    byId("reload-alerts").addEventListener("click", function () { loadAlerts().catch(showError); });
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
    byId("generate-geometry").addEventListener("click", async function () {
      try {
        const geometry = generateRectangleGeometry();
        const updated = applyFormToPayload();
        renderGeometryOnMap(geometry, updated.event, true);
        setStatus("Rectangle geometry generated and saving");
        await saveAll({ applyForm: false, keepSelectedId: updated.id });
        renderSelectedGeometryOnMap(false);
      } catch (error) {
        showError(error);
      }
    });
    byId("use-target-center").addEventListener("click", function () {
      try {
        useTargetCenter();
        setStatus("Center set from metadata target");
      } catch (error) {
        showError(error);
      }
    });
    byId("set-center-from-map").addEventListener("click", function () {
      setGeometryStatus("Click the map to set the center point.");
    });
    byId("field-effective").addEventListener("input", updateLocalTimes);
    byId("field-expires").addEventListener("input", updateLocalTimes);
    byId("field-event").addEventListener("change", function () {
      renderSelectedGeometryOnMap(false);
    });
    byId("field-geometry").addEventListener("input", function () {
      renderSelectedGeometryOnMap(false);
    });
    byId("disable-alert").addEventListener("click", function () { disableSelected().catch(showError); });
    byId("clone-alert").addEventListener("click", function () { cloneAlert(selectedIndex).catch(showError); });
    byId("delete-alert").addEventListener("click", function () { deleteAlert(selectedIndex).catch(showError); });
  }

  function showError(error) {
    setStatus(error.message || String(error));
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireEvents();
    loadAlerts().catch(showError);
  });
})();
