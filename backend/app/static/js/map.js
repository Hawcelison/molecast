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
        config.map.containerId &&
        config.map.center
    );
  }

  function initializeMap() {
    const config = getMapConfig();
    const mapContainer = document.getElementById(config.map && config.map.containerId);

    if (!mapContainer || !canInitializeMap(config)) {
      return;
    }

    const center = config.map.center;

    window.mapboxgl.accessToken = config.mapbox.token;
    window.MOLECAST_MAP = new window.mapboxgl.Map({
      container: config.map.containerId,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [center.longitude, center.latitude],
      projection: "mercator",
      zoom: config.map.zoom,
    });
  }

  document.addEventListener("DOMContentLoaded", initializeMap);
})();
