(function () {
  function getMapConfig() {
    return window.MOLECAST_CONFIG || {};
  }

  function canInitializeMap(config) {
    return Boolean(
      window.mapboxgl &&
        config.mapbox &&
        config.mapbox.enabled &&
        config.mapbox.token &&
        config.map &&
        config.map.containerId
    );
  }

  function initializeMap() {
    const config = getMapConfig();
    const mapContainer = document.getElementById(config.map && config.map.containerId);

    if (!mapContainer || !canInitializeMap(config)) {
      return;
    }

    const activeLocation = config.activeLocation || {};
    const center = config.map.center || {
      latitude: activeLocation.latitude || 42.2012,
      longitude: activeLocation.longitude || -85.58,
    };
    const zoom = Number.isFinite(Number(config.map.zoom)) ? Number(config.map.zoom) : 9;

    window.mapboxgl.accessToken = config.mapbox.token;
    window.MOLECAST_MAP = new window.mapboxgl.Map({
      container: config.map.containerId,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [center.longitude, center.latitude],
      projection: "mercator",
      zoom: zoom,
      bearing: 0,
      pitch: 0,
    });
  }

  document.addEventListener("DOMContentLoaded", initializeMap);
})();
