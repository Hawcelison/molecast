(function () {
  const RADAR_SOURCE_PREFIX = "rainviewer-radar-source";
  const RADAR_LAYER_PREFIX = "rainviewer-radar-layer";
  const MAX_MAP_INIT_RETRIES = 100;
  const MAP_INIT_RETRY_DELAY_MS = 100;
  const DEFAULT_RADAR_MIN_ZOOM = 0;
  const DEFAULT_RADAR_MAX_ZOOM = 7;
  const DEFAULT_AUTO_ANIMATE = false;

  const state = {
    frames: [],
    currentFrameIndex: 0,
    visible: true,
    animationTimer: null,
    initialized: false,
    mapInitRetries: 0,
  };

  function getConfig() {
    return (window.MOLECAST_CONFIG && window.MOLECAST_CONFIG.radar) || {};
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

  function getFrameId(index) {
    return `${RADAR_LAYER_PREFIX}-${index}`;
  }

  function getSourceId(index) {
    return `${RADAR_SOURCE_PREFIX}-${index}`;
  }

  function getRadarMinZoom(config) {
    return Number.isFinite(config.minZoom) ? config.minZoom : DEFAULT_RADAR_MIN_ZOOM;
  }

  function getRadarMaxZoom(config) {
    return Number.isFinite(config.maxZoom) ? config.maxZoom : DEFAULT_RADAR_MAX_ZOOM;
  }

  function shouldAutoAnimate(config) {
    return typeof config.autoAnimate === "boolean" ? config.autoAnimate : DEFAULT_AUTO_ANIMATE;
  }

  function buildTileUrl(host, path) {
    return `${host}${path}/256/{z}/{x}/{y}/2/1_1.png`;
  }

  function getRadarFrames(metadata) {
    const radar = metadata.radar || {};
    return [...(radar.past || []), ...(radar.nowcast || [])];
  }

  function setLayerVisibility(map, layerId, visible) {
    if (map.getLayer(layerId)) {
      map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
    }
  }

  function showFrame(index) {
    const map = getMap();

    if (!map || state.frames.length === 0) {
      return;
    }

    state.currentFrameIndex = index % state.frames.length;

    state.frames.forEach(function (_frame, frameIndex) {
      const isActiveFrame = frameIndex === state.currentFrameIndex && state.visible;
      setLayerVisibility(map, getFrameId(frameIndex), isActiveFrame);
    });
  }

  function nextFrame() {
    if (state.frames.length === 0) {
      return;
    }

    showFrame((state.currentFrameIndex + 1) % state.frames.length);
  }

  function startAnimation() {
    const config = getConfig();

    stopAnimation();

    if (state.frames.length <= 1) {
      return;
    }

    state.animationTimer = window.setInterval(nextFrame, config.frameIntervalMs || 700);
  }

  function stopAnimation() {
    if (state.animationTimer) {
      window.clearInterval(state.animationTimer);
      state.animationTimer = null;
    }
  }

  function setVisible(visible) {
    state.visible = visible;
    showFrame(state.currentFrameIndex);
  }

  function toggle() {
    setVisible(!state.visible);
    return state.visible;
  }

  function addFramesToMap(map, metadata) {
    const config = getConfig();
    const frames = getRadarFrames(metadata).filter(function (frame) {
      return frame && typeof frame.path === "string" && frame.path;
    });

    if (!metadata || typeof metadata.host !== "string" || !metadata.host || frames.length === 0) {
      console.warn("Molecast radar: RainViewer metadata did not include usable frames.");
      return;
    }

    state.frames = frames;

    frames.forEach(function (frame, index) {
      const sourceId = getSourceId(index);
      const layerId = getFrameId(index);

      if (!map.getSource(sourceId)) {
        map.addSource(sourceId, {
          type: "raster",
          tiles: [buildTileUrl(metadata.host, frame.path)],
          tileSize: 256,
          minzoom: getRadarMinZoom(config),
          maxzoom: getRadarMaxZoom(config),
        });
      }

      if (!map.getLayer(layerId)) {
        map.addLayer({
          id: layerId,
          type: "raster",
          source: sourceId,
          minzoom: getRadarMinZoom(config),
          maxzoom: 24,
          layout: {
            visibility: "none",
          },
          paint: {
            "raster-opacity": config.opacity || 0.65,
          },
        });
      }

      if (window.MOLECAST_LAYER_ORDER) {
        window.MOLECAST_LAYER_ORDER.moveAboveCountyBoundaries(map, layerId);
      }
    });

    if (frames.length > 0) {
      showFrame(frames.length - 1);
      if (shouldAutoAnimate(config)) {
        startAnimation();
      }
    }
  }

  async function initializeRadar() {
    const map = getMap();
    const config = getConfig();

    if (!map || state.initialized || config.enabled === false || !config.apiUrl) {
      return;
    }

    state.initialized = true;

    try {
      const response = await window.fetch(config.apiUrl);
      if (!response.ok) {
        console.warn(`Molecast radar: RainViewer metadata request failed with ${response.status}.`);
        return;
      }

      const metadata = await response.json();
      addFramesToMap(map, metadata);
    } catch (error) {
      console.warn("Molecast radar: unable to initialize radar layer.", error);
      state.initialized = false;
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
      initializeRadar();
      return;
    }

    map.once("load", initializeRadar);
  }

  window.MOLECAST_RADAR = {
    next: nextFrame,
    setVisible: setVisible,
    start: startAnimation,
    stop: stopAnimation,
    toggle: toggle,
  };

  document.addEventListener("DOMContentLoaded", initializeWhenMapReady);
})();
