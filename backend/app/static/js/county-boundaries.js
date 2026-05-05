(function () {
  const SOURCE_ID = "molecast-county-boundaries";
  const LAYER_ID = "molecast-county-boundaries-outline";
  const MAX_MAP_INIT_RETRIES = 100;
  const MAP_INIT_RETRY_DELAY_MS = 100;

  const state = {
    initialized: false,
    mapInitRetries: 0,
    visible: true,
  };

  function getConfig() {
    return (window.MOLECAST_CONFIG && window.MOLECAST_CONFIG.countyBoundaries) || {};
  }

  function getMap() {
    return window.MOLECAST_MAP;
  }

  function isMapboxEnabled() {
    return Boolean(
      window.MOLECAST_CONFIG &&
        window.MOLECAST_CONFIG.mapbox &&
        window.MOLECAST_CONFIG.mapbox.enabled
    );
  }

  function setVisible(visible) {
    const map = getMap();

    state.visible = visible;

    if (map && map.getLayer(LAYER_ID)) {
      map.setLayoutProperty(LAYER_ID, "visibility", visible ? "visible" : "none");
    }
  }

  function toggle() {
    setVisible(!state.visible);
    return state.visible;
  }

  function isVisible() {
    return state.visible;
  }

  function isAvailable() {
    const config = getConfig();
    return Boolean(config.enabled !== false && config.geoJsonUrl);
  }

  async function initializeCountyBoundaries() {
    const map = getMap();
    const config = getConfig();

    if (!map || state.initialized || config.enabled === false || !config.geoJsonUrl) {
      return;
    }

    state.initialized = true;

    if (!map.getSource(SOURCE_ID)) {
      map.addSource(SOURCE_ID, {
        type: "geojson",
        data: config.geoJsonUrl,
      });
    }

    if (!map.getLayer(LAYER_ID)) {
      const layerDefinition = {
        id: LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        layout: {
          visibility: state.visible ? "visible" : "none",
        },
        paint: {
          "line-color": config.lineColor || "#cbd5e1",
          "line-opacity": config.lineOpacity || 0.45,
          "line-width": config.lineWidth || 1,
        },
      };

      if (window.MOLECAST_LAYER_ORDER) {
        window.MOLECAST_LAYER_ORDER.addBelowRadar(map, layerDefinition);
      } else {
        map.addLayer(layerDefinition);
      }
    }
  }

  function initializeWhenMapReady() {
    if (!isMapboxEnabled()) {
      return;
    }

    const map = getMap();

    if (!map) {
      if (state.mapInitRetries >= MAX_MAP_INIT_RETRIES) {
        return;
      }

      state.mapInitRetries += 1;
      window.setTimeout(initializeWhenMapReady, MAP_INIT_RETRY_DELAY_MS);
      return;
    }

    state.mapInitRetries = 0;

    if (map.loaded()) {
      initializeCountyBoundaries();
      return;
    }

    map.once("load", initializeCountyBoundaries);
  }

  window.MOLECAST_COUNTY_BOUNDARIES = {
    isAvailable: isAvailable,
    isVisible: isVisible,
    setVisible: setVisible,
    toggle: toggle,
  };

  document.addEventListener("DOMContentLoaded", initializeWhenMapReady);
})();
