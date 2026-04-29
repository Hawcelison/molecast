(function (global) {
  const STORAGE_KEY = "molecast.alertUiSettings.v1";
  const DEFAULT_SETTINGS = Object.freeze({
    alertAudioEnabled: false,
    testAudioEnabled: false,
    flashingDisabled: false,
    silencedAlertIds: [],
    acknowledgedAlertIds: [],
  });

  const reducedMotionQuery = global.matchMedia
    ? global.matchMedia("(prefers-reduced-motion: reduce)")
    : null;

  function loadSettings() {
    try {
      const raw = global.localStorage ? global.localStorage.getItem(STORAGE_KEY) : null;
      const parsed = raw ? JSON.parse(raw) : {};
      return normalizeSettings(parsed);
    } catch (_error) {
      return normalizeSettings({});
    }
  }

  let currentSettings = loadSettings();

  function normalizeSettings(value) {
    const settings = value && typeof value === "object" ? value : {};
    return {
      alertAudioEnabled: Boolean(settings.alertAudioEnabled),
      testAudioEnabled: Boolean(settings.testAudioEnabled),
      flashingDisabled: Boolean(settings.flashingDisabled),
      silencedAlertIds: normalizeIdArray(settings.silencedAlertIds),
      acknowledgedAlertIds: normalizeIdArray(settings.acknowledgedAlertIds),
    };
  }

  function normalizeIdArray(value) {
    return Array.isArray(value)
      ? [...new Set(value.filter(function (item) {
        return typeof item === "string" && item.trim();
      }))]
      : [];
  }

  function saveSettings() {
    if (!global.localStorage) {
      return;
    }
    global.localStorage.setItem(STORAGE_KEY, JSON.stringify(currentSettings));
  }

  function getSettings() {
    return {
      ...currentSettings,
      silencedAlertIds: currentSettings.silencedAlertIds.slice(),
      acknowledgedAlertIds: currentSettings.acknowledgedAlertIds.slice(),
    };
  }

  function updateSettings(patch) {
    currentSettings = normalizeSettings({ ...currentSettings, ...(patch || {}) });
    saveSettings();
    return getSettings();
  }

  function setAlertAudioEnabled(enabled) {
    return updateSettings({ alertAudioEnabled: Boolean(enabled) });
  }

  function setTestAudioEnabled(enabled) {
    return updateSettings({ testAudioEnabled: Boolean(enabled) });
  }

  function setFlashingDisabled(disabled) {
    return updateSettings({ flashingDisabled: Boolean(disabled) });
  }

  function hasId(collectionName, alertId) {
    return Boolean(alertId && currentSettings[collectionName].includes(alertId));
  }

  function addId(collectionName, alertId) {
    if (!alertId || hasId(collectionName, alertId)) {
      return getSettings();
    }
    return updateSettings({
      [collectionName]: currentSettings[collectionName].concat(alertId),
    });
  }

  function removeId(collectionName, alertId) {
    if (!alertId) {
      return getSettings();
    }
    return updateSettings({
      [collectionName]: currentSettings[collectionName].filter(function (id) {
        return id !== alertId;
      }),
    });
  }

  function silenceAlert(alertId) {
    return addId("silencedAlertIds", alertId);
  }

  function unsilenceAlert(alertId) {
    return removeId("silencedAlertIds", alertId);
  }

  function acknowledgeAlert(alertId) {
    return addId("acknowledgedAlertIds", alertId);
  }

  function unacknowledgeAlert(alertId) {
    return removeId("acknowledgedAlertIds", alertId);
  }

  function isAlertSilenced(alertId) {
    return hasId("silencedAlertIds", alertId);
  }

  function isAlertAcknowledged(alertId) {
    return hasId("acknowledgedAlertIds", alertId);
  }

  function prefersReducedMotion() {
    return Boolean(reducedMotionQuery && reducedMotionQuery.matches);
  }

  global.MolecastSettingsStore = {
    DEFAULT_SETTINGS,
    acknowledgeAlert,
    getSettings,
    isAlertAcknowledged,
    isAlertSilenced,
    prefersReducedMotion,
    setAlertAudioEnabled,
    setFlashingDisabled,
    setTestAudioEnabled,
    silenceAlert,
    unacknowledgeAlert,
    unsilenceAlert,
    updateSettings,
  };
})(window);
