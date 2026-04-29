(function (global) {
  const ALERTS_ENDPOINT = "/api/alerts/active";
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

  global.MolecastAlertsApi = {
    DEFAULT_REFRESH_SECONDS,
    fetchActiveAlerts,
  };
})(window);

