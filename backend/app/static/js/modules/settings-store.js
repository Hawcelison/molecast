(function (global) {
  const STORAGE_KEY = "molecast.alertUiSettings.v1";
  const DEFAULT_SETTINGS = Object.freeze({
    alertAudioEnabled: false,
    testAudioEnabled: false,
    flashingDisabled: false,
    silencedAlertIds: [],
    acknowledgedAlertIds: [],
    readAlertIds: [],
  });
  const MAX_READ_ALERT_IDS = 200;

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
      readAlertIds: normalizeIdArray(settings.readAlertIds).slice(-MAX_READ_ALERT_IDS),
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
      readAlertIds: currentSettings.readAlertIds.slice(),
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

  function markAlertRead(alertId) {
    return addId("readAlertIds", alertId);
  }

  function markAlertsRead(alertIds) {
    const ids = normalizeIdArray(alertIds).slice(-MAX_READ_ALERT_IDS);
    if (ids.length === 0) {
      return getSettings();
    }
    return updateSettings({
      readAlertIds: normalizeIdArray(currentSettings.readAlertIds.concat(ids)).slice(-MAX_READ_ALERT_IDS),
    });
  }

  function syncReadAlertIds(activeAlertIds) {
    const activeIds = new Set(normalizeIdArray(activeAlertIds));
    return updateSettings({
      readAlertIds: currentSettings.readAlertIds.filter(function (id) {
        return activeIds.has(id);
      }).slice(-MAX_READ_ALERT_IDS),
    });
  }

  function isAlertSilenced(alertId) {
    return hasId("silencedAlertIds", alertId);
  }

  function isAlertAcknowledged(alertId) {
    return hasId("acknowledgedAlertIds", alertId);
  }

  function isAlertRead(alertId) {
    return hasId("readAlertIds", alertId);
  }

  function prefersReducedMotion() {
    return Boolean(reducedMotionQuery && reducedMotionQuery.matches);
  }

  global.MolecastSettingsStore = {
    DEFAULT_SETTINGS,
    acknowledgeAlert,
    getSettings,
    isAlertAcknowledged,
    isAlertRead,
    isAlertSilenced,
    markAlertRead,
    markAlertsRead,
    prefersReducedMotion,
    setAlertAudioEnabled,
    setFlashingDisabled,
    setTestAudioEnabled,
    silenceAlert,
    syncReadAlertIds,
    unacknowledgeAlert,
    unsilenceAlert,
    updateSettings,
  };
})(window);
