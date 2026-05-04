(function (global) {
  const ALERTS_ENDPOINT = "/api/alerts/active";
  const ALERT_SUMMARY_ENDPOINT = "/api/alerts/summary";
  const DEFAULT_REFRESH_SECONDS = 60;

  async function fetchActiveAlerts() {
    const response = await global.fetch(ALERTS_ENDPOINT);
    if (!response.ok) {
      throw new Error(`Alerts request failed: ${response.status}`);
    }
    const payload = await response.json();
    return {
      alerts: Array.isArray(payload && payload.alerts) ? payload.alerts : [],
      refreshIntervalSeconds: Number(payload && payload.refresh_interval_seconds) || DEFAULT_REFRESH_SECONDS,
      payload,
    };
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
    fetchActiveAlerts,
    fetchAlertSummary,
  };
})(window);
