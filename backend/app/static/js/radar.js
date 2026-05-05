(function () {
  const RADAR_SOURCE_PREFIX = "rainviewer-radar-source";
  const RADAR_LAYER_PREFIX = "rainviewer-radar-layer";
  const MAX_MAP_INIT_RETRIES = 100;
  const MAP_INIT_RETRY_DELAY_MS = 100;
  const DEFAULT_RADAR_MIN_ZOOM = 0;
  const DEFAULT_RADAR_MAX_ZOOM = 7;
  const DEFAULT_AUTO_ANIMATE = false;
  const DEFAULT_PROVIDER = "rainviewer";
  const DEFAULT_AUTO_REFRESH_ENABLED = true;
  const DEFAULT_AUTO_REFRESH_SECONDS = 60;
  const DEFAULT_STALE_AFTER_SECONDS = 900;

  const state = {
    frames: [],
    frameKeys: [],
    currentFrameIndex: 0,
    visible: true,
    animationTimer: null,
    refreshTimer: null,
    refreshInFlight: false,
    initialized: false,
    mapInitRetries: 0,
    activeProviderId: DEFAULT_PROVIDER,
    lastRefreshStartedAt: null,
    lastRefreshCompletedAt: null,
  };

  const providers = {
    rainviewer: {
      id: "rainviewer",
      sourcePrefix: RADAR_SOURCE_PREFIX,
      layerPrefix: RADAR_LAYER_PREFIX,
      metadataUrl: function (config) {
        return config.apiUrl;
      },
      frames: function (metadata) {
        const radar = metadata.radar || {};
        return [...(radar.past || []), ...(radar.nowcast || [])].filter(function (frame) {
          return frame && typeof frame.path === "string" && frame.path;
        });
      },
      frameKey: function (frame) {
        return `${frame.time || ""}:${frame.path}`;
      },
      frameTimestamp: function (frame) {
        return Number.isFinite(Number(frame.time)) ? Number(frame.time) * 1000 : null;
      },
      tileUrl: function (metadata, frame) {
        return `${metadata.host}${frame.path}/256/{z}/{x}/{y}/2/1_1.png`;
      },
      isUsableMetadata: function (metadata, frames) {
        return Boolean(
          metadata &&
            typeof metadata.host === "string" &&
            metadata.host &&
            frames.length > 0
        );
      },
    },
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

  function getProvider(config) {
    const providerId = config.provider || DEFAULT_PROVIDER;
    return providers[providerId] || providers[DEFAULT_PROVIDER];
  }

  function getFrameId(provider, index) {
    return `${provider.layerPrefix}-${index}`;
  }

  function getSourceId(provider, index) {
    return `${provider.sourcePrefix}-${index}`;
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

  function getRefreshIntervalMs(config) {
    const seconds = Number(config.autoRefreshSeconds);
    const safeSeconds = Number.isFinite(seconds) && seconds > 0 ? seconds : DEFAULT_AUTO_REFRESH_SECONDS;
    return safeSeconds * 1000;
  }

  function getStaleAfterMs(config) {
    const seconds = Number(config.staleAfterSeconds);
    const safeSeconds = Number.isFinite(seconds) && seconds > 0 ? seconds : DEFAULT_STALE_AFTER_SECONDS;
    return safeSeconds * 1000;
  }

  function isDebugEnabled(config) {
    return config.debug === true;
  }

  function debugLog(message, detail) {
    if (isDebugEnabled(getConfig())) {
      console.debug(`Molecast radar: ${message}`, detail || "");
    }
  }

  function getSettingsStore() {
    return window.MolecastSettingsStore || null;
  }

  function getAutoRefreshEnabled(config) {
    const settingsStore = getSettingsStore();
    if (settingsStore && typeof settingsStore.getSettings === "function") {
      const settings = settingsStore.getSettings();
      if (typeof settings.radarAutoRefreshEnabled === "boolean") {
        return settings.radarAutoRefreshEnabled;
      }
    }
    return typeof config.autoRefreshEnabled === "boolean"
      ? config.autoRefreshEnabled
      : DEFAULT_AUTO_REFRESH_ENABLED;
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
    const provider = providers[state.activeProviderId] || providers[DEFAULT_PROVIDER];

    state.frames.forEach(function (_frame, frameIndex) {
      const isActiveFrame = frameIndex === state.currentFrameIndex && state.visible;
      setLayerVisibility(map, getFrameId(provider, frameIndex), isActiveFrame);
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

  function isVisible() {
    return state.visible;
  }

  function toggle() {
    setVisible(!state.visible);
    return state.visible;
  }

  function frameKeys(provider, frames) {
    return frames.map(function (frame) {
      return provider.frameKey(frame);
    });
  }

  function sameFrameSet(nextFrameKeys) {
    return nextFrameKeys.length === state.frameKeys.length &&
      nextFrameKeys.every(function (key, index) {
        return key === state.frameKeys[index];
      });
  }

  function removeLayerAndSource(map, provider, index) {
    const layerId = getFrameId(provider, index);
    const sourceId = getSourceId(provider, index);
    if (map.getLayer(layerId)) {
      map.removeLayer(layerId);
    }
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId);
    }
  }

  function updateRasterSource(map, sourceId, tiles) {
    const source = map.getSource(sourceId);
    if (!source) {
      return false;
    }
    if (typeof source.setTiles === "function") {
      source.setTiles(tiles);
      return true;
    }
    return false;
  }

  function removeExtraFrames(map, provider, frameCount) {
    for (let index = frameCount; index < state.frames.length; index += 1) {
      removeLayerAndSource(map, provider, index);
    }
  }

  function latestFrameTimestamp(provider, frames) {
    return frames.reduce(function (latest, frame) {
      const timestamp = provider.frameTimestamp(frame);
      return timestamp && timestamp > latest ? timestamp : latest;
    }, 0);
  }

  function detectStaleFrames(provider, frames, config) {
    const latestTimestamp = latestFrameTimestamp(provider, frames);
    if (!latestTimestamp) {
      return false;
    }
    const ageMs = Date.now() - latestTimestamp;
    const isStale = ageMs > getStaleAfterMs(config);
    if (isStale) {
      debugLog("stale frames detected", {
        latestFrame: new Date(latestTimestamp).toISOString(),
        ageSeconds: Math.round(ageMs / 1000),
      });
    }
    return isStale;
  }

  function logFrameTimestamps(provider, frames) {
    debugLog("frame timestamps", frames.map(function (frame) {
      const timestamp = provider.frameTimestamp(frame);
      return timestamp ? new Date(timestamp).toISOString() : null;
    }).filter(Boolean));
  }

  function addFramesToMap(map, metadata, provider) {
    const config = getConfig();
    const frames = provider.frames(metadata);

    if (!provider.isUsableMetadata(metadata, frames)) {
      console.warn(`Molecast radar: ${provider.id} metadata did not include usable frames.`);
      return;
    }

    const nextFrameKeys = frameKeys(provider, frames);
    if (sameFrameSet(nextFrameKeys)) {
      detectStaleFrames(provider, frames, config);
      debugLog("refresh returned unchanged frames", { provider: provider.id, frameCount: frames.length });
      return;
    }

    removeExtraFrames(map, provider, frames.length);

    const previousFrameCount = state.frames.length;
    const nextVisibleFrame = previousFrameCount > 0
      ? Math.min(frames.length - 1, state.currentFrameIndex)
      : frames.length - 1;
    state.frames = frames;
    state.frameKeys = nextFrameKeys;
    state.activeProviderId = provider.id;

    frames.forEach(function (frame, index) {
      const sourceId = getSourceId(provider, index);
      const layerId = getFrameId(provider, index);
      const tiles = [provider.tileUrl(metadata, frame)];

      if (!map.getSource(sourceId)) {
        map.addSource(sourceId, {
          type: "raster",
          tiles: tiles,
          tileSize: 256,
          minzoom: getRadarMinZoom(config),
          maxzoom: getRadarMaxZoom(config),
        });
      } else if (!updateRasterSource(map, sourceId, tiles)) {
        removeLayerAndSource(map, provider, index);
        map.addSource(sourceId, {
          type: "raster",
          tiles: tiles,
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

    logFrameTimestamps(provider, frames);
    const stale = detectStaleFrames(provider, frames, config);

    window.dispatchEvent(new CustomEvent("molecast:radar-layers-updated", {
      detail: {
        provider: provider.id,
        frameCount: frames.length,
        previousFrameCount,
        stale,
      },
    }));

    if (frames.length > 0) {
      showFrame(nextVisibleFrame);
      if (shouldAutoAnimate(config)) {
        startAnimation();
      }
    }
  }

  async function loadRadar(reason) {
    const map = getMap();
    const config = getConfig();
    const provider = getProvider(config);
    const metadataUrl = provider.metadataUrl(config);

    if (!map || config.enabled === false || !metadataUrl || state.refreshInFlight) {
      return;
    }

    state.refreshInFlight = true;
    state.lastRefreshStartedAt = Date.now();
    debugLog("refresh started", { reason, provider: provider.id, startedAt: new Date(state.lastRefreshStartedAt).toISOString() });

    try {
      const response = await window.fetch(metadataUrl, { cache: "no-store" });
      if (!response.ok) {
        console.warn(`Molecast radar: ${provider.id} metadata request failed with ${response.status}.`);
        return;
      }

      const metadata = await response.json();
      addFramesToMap(map, metadata, provider);
      state.lastRefreshCompletedAt = Date.now();
      debugLog("refresh completed", {
        reason,
        provider: provider.id,
        elapsedMs: state.lastRefreshCompletedAt - state.lastRefreshStartedAt,
      });
    } catch (error) {
      console.warn("Molecast radar: unable to initialize radar layer.", error);
    } finally {
      state.refreshInFlight = false;
    }
  }

  function stopAutoRefresh() {
    if (state.refreshTimer) {
      window.clearInterval(state.refreshTimer);
      state.refreshTimer = null;
    }
  }

  function startAutoRefresh() {
    const config = getConfig();

    stopAutoRefresh();

    if (config.enabled === false || !getAutoRefreshEnabled(config)) {
      return;
    }

    state.refreshTimer = window.setInterval(function () {
      loadRadar("auto-refresh");
    }, getRefreshIntervalMs(config));
  }

  function setAutoRefreshEnabled(enabled) {
    const settingsStore = getSettingsStore();
    if (settingsStore && typeof settingsStore.updateSettings === "function") {
      settingsStore.updateSettings({ radarAutoRefreshEnabled: Boolean(enabled) });
    }
    syncAutoRefreshControl();
    if (enabled) {
      startAutoRefresh();
      loadRadar("auto-refresh-enabled");
    } else {
      stopAutoRefresh();
    }
    return Boolean(enabled);
  }

  function syncAutoRefreshControl() {
    const control = document.getElementById("radar-auto-refresh-toggle");
    if (!control) {
      return;
    }
    const enabled = getAutoRefreshEnabled(getConfig());
    control.checked = enabled;
    control.setAttribute("aria-checked", enabled ? "true" : "false");
  }

  function wireControls() {
    const control = document.getElementById("radar-auto-refresh-toggle");
    if (!control) {
      return;
    }
    syncAutoRefreshControl();
    control.addEventListener("change", function () {
      setAutoRefreshEnabled(control.checked);
    });
  }

  async function initializeRadar() {
    const config = getConfig();

    if (state.initialized || config.enabled === false) {
      return;
    }

    state.initialized = true;
    syncAutoRefreshControl();
    await loadRadar("initial");
    startAutoRefresh();
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
    providers: providers,
    refresh: function () { return loadRadar("manual"); },
    next: nextFrame,
    setVisible: setVisible,
    isVisible: isVisible,
    setAutoRefreshEnabled: setAutoRefreshEnabled,
    start: startAnimation,
    stop: stopAnimation,
    startAutoRefresh: startAutoRefresh,
    stopAutoRefresh: stopAutoRefresh,
    toggle: toggle,
  };

  document.addEventListener("DOMContentLoaded", function () {
    wireControls();
    initializeWhenMapReady();
  });
  window.addEventListener("beforeunload", function () {
    stopAnimation();
    stopAutoRefresh();
  });
})();
