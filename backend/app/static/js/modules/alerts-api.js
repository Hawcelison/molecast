(function (global) {
  const ALERTS_ENDPOINT = "/api/alerts/active";
  const ALERT_SUMMARY_ENDPOINT = "/api/alerts/summary";
  const DEFAULT_REFRESH_SECONDS = 60;
  const ACTIVE_ALERT_REQUEST_TIMEOUT_MS = 30000;

  async function fetchActiveAlerts() {
    const controller = typeof global.AbortController === "function"
      ? new global.AbortController()
      : null;
    const timeoutId = controller
      ? global.setTimeout(function () {
        controller.abort();
      }, ACTIVE_ALERT_REQUEST_TIMEOUT_MS)
      : null;

    try {
      const response = await global.fetch(ALERTS_ENDPOINT, {
        cache: "no-store",
        signal: controller ? controller.signal : undefined,
      });
      if (!response.ok) {
        throw new Error(`Alerts request failed: ${response.status}`);
      }
      const payload = await response.json();
      return {
        alerts: Array.isArray(payload && payload.alerts) ? payload.alerts : [],
        refreshIntervalSeconds: Number(payload && payload.refresh_interval_seconds) || DEFAULT_REFRESH_SECONDS,
        payload,
      };
    } catch (error) {
      if (error && error.name === "AbortError") {
        throw new Error("Active alerts request timed out");
      }
      throw error;
    } finally {
      if (timeoutId) {
        global.clearTimeout(timeoutId);
      }
    }
  }

  async function fetchAlertSummary(scope) {
    const normalizedScope = scope === "saved" ? "saved" : "active";
    const response = await global.fetch(`${ALERT_SUMMARY_ENDPOINT}?scope=${encodeURIComponent(normalizedScope)}`);
    if (!response.ok) {
      throw new Error(`Alert summary request failed: ${response.status}`);
    }
    return response.json();
  }

  global.MolecastAlertsApi = {
    DEFAULT_REFRESH_SECONDS,
    ACTIVE_ALERT_REQUEST_TIMEOUT_MS,
    fetchActiveAlerts,
    fetchAlertSummary,
  };
})(window);
