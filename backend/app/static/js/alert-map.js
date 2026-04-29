(function () {
  const SOURCE_ID = "molecast-alerts-source";
  const FILL_LAYER_ID = "molecast-alerts-fill";
  const LINE_LAYER_ID = "molecast-alerts-line";
  const SELECTED_LINE_LAYER_ID = "molecast-alerts-selected-line";
  const DEFAULT_ALERT_COLOR = "#3399FF";
  const MAX_MAP_INIT_RETRIES = 100;
  const MAP_INIT_RETRY_DELAY_MS = 100;
  const FOCUS_PADDING = { top: 64, right: 48, bottom: 48, left: 48 };
  const FOCUS_MAX_ZOOM = 12;

  const state = {
    alerts: [],
    selectedAlertId: null,
    initialized: false,
    pendingRender: false,
    mapInitRetries: 0,
  };

  function getMap() {
    return window.MOLECAST_MAP;
  }

  function isStyleReady(map) {
    return Boolean(map && typeof map.isStyleLoaded === "function" && map.isStyleLoaded());
  }

  function canonicalId(alert, index) {
    if (window.MolecastAlertBanners && window.MolecastAlertBanners.canonicalId) {
      return window.MolecastAlertBanners.canonicalId(alert, index || 0);
    }
    return getString(alert && (alert.canonical_id || alert.canonicalId || alert.id), `alert-${index || 0}`);
  }

  function getString(value, fallback) {
    return typeof value === "string" && value.trim() ? value.trim() : fallback;
  }

  function alertColor(alert) {
    if (alert && typeof alert.color_hex === "string" && /^#[0-9a-fA-F]{6}$/.test(alert.color_hex)) {
      return alert.color_hex;
    }
    return DEFAULT_ALERT_COLOR;
  }

  function validGeometry(geometry) {
    return Boolean(
      geometry &&
        typeof geometry === "object" &&
        (geometry.type === "Polygon" || geometry.type === "MultiPolygon") &&
        Array.isArray(geometry.coordinates)
    );
  }

  function alertFeature(alert, index) {
    const geometry = alert && alert.geometry;
    if (!validGeometry(geometry)) {
      return null;
    }

    const alertId = canonicalId(alert, index);
    return {
      type: "Feature",
      id: alertId,
      properties: {
        alertId: alertId,
        color: alertColor(alert),
        selected: alertId === state.selectedAlertId,
        event: getString(alert.event || alert.title, "Weather Alert"),
      },
      geometry: geometry,
    };
  }

  function featureCollection() {
    return {
      type: "FeatureCollection",
      features: state.alerts.map(alertFeature).filter(Boolean),
    };
  }

  function ensureInitialized() {
    const map = getMap();
    if (!map) {
      retryInitialize();
      return false;
    }

    if (!isStyleReady(map)) {
      if (!state.initialized) {
        map.once("load", function () {
          ensureInitialized();
          flushRender();
        });
      }
      return false;
    }

    if (!map.getSource(SOURCE_ID)) {
      map.addSource(SOURCE_ID, {
        type: "geojson",
        data: featureCollection(),
      });
    }

    addLayers(map);
    state.initialized = true;
    reassertLayerOrder();
    return true;
  }

  function retryInitialize() {
    if (state.mapInitRetries >= MAX_MAP_INIT_RETRIES) {
      return;
    }
    state.mapInitRetries += 1;
    window.setTimeout(function () {
      ensureInitialized();
      flushRender();
    }, MAP_INIT_RETRY_DELAY_MS);
  }

  function addLayers(map) {
    if (!map.getLayer(FILL_LAYER_ID)) {
      map.addLayer({
        id: FILL_LAYER_ID,
        type: "fill",
        source: SOURCE_ID,
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": ["case", ["==", ["get", "selected"], true], 0.3, 0.12],
        },
      });
    }

    if (!map.getLayer(LINE_LAYER_ID)) {
      map.addLayer({
        id: LINE_LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        paint: {
          "line-color": ["get", "color"],
          "line-opacity": ["case", ["==", ["get", "selected"], true], 1, 0.45],
          "line-width": ["case", ["==", ["get", "selected"], true], 2.5, 1.5],
        },
      });
    }

    if (!map.getLayer(SELECTED_LINE_LAYER_ID)) {
      map.addLayer({
        id: SELECTED_LINE_LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        filter: ["==", ["get", "selected"], true],
        paint: {
          "line-color": ["get", "color"],
          "line-opacity": 1,
          "line-width": 4,
        },
      });
    }
  }

  function reassertLayerOrder() {
    const map = getMap();
    if (!map) {
      return;
    }

    [FILL_LAYER_ID, LINE_LAYER_ID, SELECTED_LINE_LAYER_ID].forEach(function (layerId) {
      if (map.getLayer(layerId)) {
        map.moveLayer(layerId);
      }
    });
  }

  function flushRender() {
    if (!state.pendingRender || !ensureInitialized()) {
      return;
    }

    const map = getMap();
    const source = map.getSource(SOURCE_ID);
    if (source && typeof source.setData === "function") {
      source.setData(featureCollection());
    }
    state.pendingRender = false;
    reassertLayerOrder();
  }

  function renderAlerts(alerts) {
    state.alerts = Array.isArray(alerts) ? alerts.filter(isAlertObject) : [];

    if (state.selectedAlertId && !state.alerts.some(function (alert, index) {
      return canonicalId(alert, index) === state.selectedAlertId;
    })) {
      state.selectedAlertId = null;
    }

    state.pendingRender = true;
    flushRender();
  }

  function isAlertObject(alert) {
    return alert && typeof alert === "object" && !Array.isArray(alert);
  }

  function focusAlert(alertOrId) {
    const selectedAlert = typeof alertOrId === "string"
      ? findAlertById(alertOrId)
      : alertOrId;
    if (!isAlertObject(selectedAlert)) {
      return;
    }

    state.selectedAlertId = canonicalId(selectedAlert, state.alerts.indexOf(selectedAlert));
    state.pendingRender = true;
    flushRender();

    const bounds = boundsFromAlert(selectedAlert);
    const map = getMap();
    if (!bounds || !map || typeof map.fitBounds !== "function") {
      return;
    }

    map.fitBounds(
      [
        [bounds.west, bounds.south],
        [bounds.east, bounds.north],
      ],
      {
        padding: FOCUS_PADDING,
        maxZoom: FOCUS_MAX_ZOOM,
        bearing: 0,
        pitch: 0,
        duration: prefersReducedMotion() ? 0 : 450,
      }
    );
  }

  function findAlertById(alertId) {
    return state.alerts.find(function (alert, index) {
      return canonicalId(alert, index) === alertId;
    }) || null;
  }

  function boundsFromAlert(alert) {
    const serverBounds = normalizeBounds(alert.geometry_bounds || alert.geometryBounds);
    if (serverBounds) {
      return serverBounds;
    }
    return boundsFromGeometry(alert.geometry);
  }

  function normalizeBounds(bounds) {
    if (!bounds || typeof bounds !== "object") {
      return null;
    }
    const west = Number(bounds.west);
    const south = Number(bounds.south);
    const east = Number(bounds.east);
    const north = Number(bounds.north);
    if (![west, south, east, north].every(Number.isFinite)) {
      return null;
    }
    return { west: west, south: south, east: east, north: north };
  }

  function boundsFromGeometry(geometry) {
    if (!validGeometry(geometry)) {
      return null;
    }

    const positions = [];
    collectPositions(geometry.coordinates, positions);
    if (positions.length === 0) {
      return null;
    }

    const longitudes = positions.map(function (position) {
      return position[0];
    });
    const latitudes = positions.map(function (position) {
      return position[1];
    });
    return {
      west: Math.min.apply(null, longitudes),
      south: Math.min.apply(null, latitudes),
      east: Math.max.apply(null, longitudes),
      north: Math.max.apply(null, latitudes),
    };
  }

  function collectPositions(value, positions) {
    if (!Array.isArray(value)) {
      return;
    }
    if (isPosition(value)) {
      positions.push([Number(value[0]), Number(value[1])]);
      return;
    }
    value.forEach(function (item) {
      collectPositions(item, positions);
    });
  }

  function isPosition(value) {
    return Array.isArray(value) &&
      value.length >= 2 &&
      Number.isFinite(Number(value[0])) &&
      Number.isFinite(Number(value[1]));
  }

  function clearSelection() {
    state.selectedAlertId = null;
    state.pendingRender = true;
    flushRender();
  }

  function prefersReducedMotion() {
    return Boolean(
      window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  document.addEventListener("molecast:alert-selected", function (event) {
    const detail = event.detail || {};
    focusAlert(detail.alert || detail.alertId);
  });

  window.addEventListener("molecast:radar-layers-updated", function () {
    window.setTimeout(reassertLayerOrder, 0);
  });

  window.MOLECAST_ALERT_MAP = {
    renderAlerts: renderAlerts,
    focusAlert: focusAlert,
    clearSelection: clearSelection,
  };

  document.addEventListener("DOMContentLoaded", ensureInitialized);
})();
