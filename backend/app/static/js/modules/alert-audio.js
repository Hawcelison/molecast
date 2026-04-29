(function (global) {
  const TEST_SOURCES = new Set(["test", "molecast_test"]);
  const FUTURE_TEST_SOURCES = new Set(["test", "molecast_test", "ipaws_future"]);
  const PROFILE_SOUNDS = Object.freeze({
    air_raid: "/static/sounds/airraid.mp3",
    ebs_purge: "/static/sounds/default.mp3",
    standard_alert: "/static/sounds/default.mp3",
    tornado_siren: "/static/sounds/tornado.mp3",
  });

  let activeAudio = null;
  let loopTimer = null;
  let activeAlertId = null;
  let activeProfile = null;
  let playCount = 0;
  let windowStartedAt = 0;
  let sessionAudioUnlocked = false;

  function getString(value, fallback) {
    return typeof value === "string" && value.trim() ? value.trim() : fallback;
  }

  function source(alert) {
    return getString(alert && alert.source, "nws");
  }

  function isTestSource(alert) {
    return TEST_SOURCES.has(source(alert));
  }

  function isFutureTestSource(alert) {
    return FUTURE_TEST_SOURCES.has(source(alert));
  }

  function canonicalId(alert, index) {
    if (global.MolecastAlertBanners && global.MolecastAlertBanners.canonicalId) {
      return global.MolecastAlertBanners.canonicalId(alert, index || 0);
    }
    return getString(alert && (alert.canonical_id || alert.canonicalId || alert.id), "");
  }

  function profileForAlert(alert) {
    const event = getString(alert && alert.event, "");
    const requested = getString(alert && (alert.sound_profile || alert.default_sound), "");
    if (requested && PROFILE_SOUNDS[requested] && profileAllowed(requested, alert)) {
      return requested;
    }
    if (event === "Tornado Warning") {
      return "tornado_siren";
    }
    if (
      event === "Blizzard Warning" ||
      event === "Hurricane Warning" ||
      event === "Extreme Wind Warning" ||
      event === "Tropical Storm Warning" ||
      event === "Storm Surge Warning"
    ) {
      return "standard_alert";
    }
    if (
      isFutureTestSource(alert) &&
      (event === "Civil Emergency Message" || event === "Civil Danger Warning" || event.includes("Civil"))
    ) {
      return "air_raid";
    }
    if (
      isFutureTestSource(alert) &&
      (event === "Presidential Alert" || event.includes("National"))
    ) {
      return "ebs_purge";
    }
    return "";
  }

  function profileAllowed(profile, alert) {
    if ((profile === "air_raid" || profile === "ebs_purge") && !isFutureTestSource(alert)) {
      return false;
    }
    return true;
  }

  function canPlayAlert(alert) {
    const settings = global.MolecastSettingsStore.getSettings();
    const alertId = canonicalId(alert);
    if (!settings.alertAudioEnabled) {
      return false;
    }
    if (!sessionAudioUnlocked) {
      return false;
    }
    if (isTestSource(alert) && !settings.testAudioEnabled) {
      return false;
    }
    if (global.MolecastSettingsStore.isAlertSilenced(alertId)) {
      return false;
    }
    if (global.MolecastSettingsStore.isAlertAcknowledged(alertId)) {
      return false;
    }
    return Boolean(profileForAlert(alert));
  }

  function resetRateWindowIfNeeded() {
    const now = Date.now();
    if (!windowStartedAt || now - windowStartedAt >= 60000) {
      windowStartedAt = now;
      playCount = 0;
    }
  }

  function playCurrentAudio() {
    resetRateWindowIfNeeded();
    if (!activeAudio || playCount >= 2) {
      return;
    }
    playCount += 1;
    activeAudio.currentTime = 0;
    activeAudio.play().catch(function () {});
  }

  function startLoop() {
    if (loopTimer) {
      return;
    }
    loopTimer = global.setInterval(playCurrentAudio, 30000);
  }

  function playForAlert(alert) {
    if (!canPlayAlert(alert)) {
      return false;
    }

    const alertId = canonicalId(alert);
    const profile = profileForAlert(alert);
    if (activeAlertId === alertId && activeProfile === profile && activeAudio) {
      startLoop();
      return true;
    }

    stop();
    activeAlertId = alertId;
    activeProfile = profile;
    activeAudio = new Audio(PROFILE_SOUNDS[profile]);
    windowStartedAt = 0;
    playCurrentAudio();
    startLoop();
    return true;
  }

  function stop() {
    if (loopTimer) {
      global.clearInterval(loopTimer);
      loopTimer = null;
    }
    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }
    activeAlertId = null;
    activeProfile = null;
    playCount = 0;
    windowStartedAt = 0;
    return true;
  }

  function unlockForSession() {
    sessionAudioUnlocked = true;
  }

  global.MolecastAlertAudio = {
    canPlayAlert,
    profileForAlert,
    unlockForSession,
    playForAlert,
    stop,
  };
})(window);
