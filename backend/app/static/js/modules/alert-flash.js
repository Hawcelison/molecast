(function (global) {
  let flashInterval = null;
  let activeColor = "";

  function prefersReducedMotion() {
    return Boolean(
      global.MolecastSettingsStore &&
      global.MolecastSettingsStore.prefersReducedMotion()
    );
  }

  function flashingDisabled() {
    return Boolean(
      global.MolecastSettingsStore &&
      global.MolecastSettingsStore.getSettings().flashingDisabled
    );
  }

  function start(color) {
    if (prefersReducedMotion() || flashingDisabled()) {
      stop();
      return;
    }
    if (flashInterval && activeColor === color) {
      return;
    }
    stop();

    let visible = false;
    activeColor = color;
    flashInterval = global.setInterval(function () {
      document.body.style.backgroundColor = visible ? "" : color;
      visible = !visible;
    }, 2000);
  }

  function stop() {
    if (flashInterval) {
      global.clearInterval(flashInterval);
      flashInterval = null;
    }
    document.body.style.backgroundColor = "";
    activeColor = "";
  }

  global.MolecastAlertFlash = {
    start,
    stop,
  };
})(window);
