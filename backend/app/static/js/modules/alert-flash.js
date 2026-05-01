(function (global) {
  function stop() {}

  function start() {
    stop();
  }

  global.MolecastAlertFlash = {
    start,
    stop,
  };
})(window);
