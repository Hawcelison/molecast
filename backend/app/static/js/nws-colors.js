(function (global) {
  const DEFAULT_ALERT_COLOR = "#3399FF";

  const NWS_EVENT_COLORS = Object.freeze({
    "Tornado Warning": "#FF0000",
    "Severe Thunderstorm Warning": "#FFA500",
    "Tornado Watch": "#FFFF00",
    "Severe Thunderstorm Watch": "#DB7093",
    "Flash Flood Warning": "#00FF00",
    "Flood Warning": "#00FF00",
    "Blizzard Warning": "#00FFFF",
    "Ice Storm Warning": "#FF00FF",
    "High Wind Warning": "#DAA520",
    "Heat Advisory": "#FF7F50",
    "Excessive Heat Warning": "#FF0000",
    "Dense Fog Advisory": "#708090",
    "Special Weather Statement": "#FFE4B5",
  });

  const NWS_SEVERITY_COLORS = Object.freeze({
    Extreme: "#FF0000",
    Severe: "#FFA500",
    Moderate: "#FFFF00",
    Minor: "#00FF00",
    Unknown: DEFAULT_ALERT_COLOR,
  });

  function getAlertColor(alert) {
    if (!alert) {
      return DEFAULT_ALERT_COLOR;
    }

    if (alert.event && NWS_EVENT_COLORS[alert.event]) {
      return NWS_EVENT_COLORS[alert.event];
    }

    if (alert.severity && NWS_SEVERITY_COLORS[alert.severity]) {
      return NWS_SEVERITY_COLORS[alert.severity];
    }

    return DEFAULT_ALERT_COLOR;
  }

  function convertHexToRGBA(hexColor, alpha) {
    const normalized = String(hexColor || "").replace("#", "");
    const opacity = Number.isFinite(Number(alpha)) ? Math.min(Math.max(Number(alpha), 0), 1) : 0.3;
    if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
      return `rgba(51, 153, 255, ${opacity})`;
    }

    const red = Number.parseInt(normalized.slice(0, 2), 16);
    const green = Number.parseInt(normalized.slice(2, 4), 16);
    const blue = Number.parseInt(normalized.slice(4, 6), 16);
    return `rgba(${red}, ${green}, ${blue}, ${opacity})`;
  }

  function getAlertColorWithOpacity(alert, alpha = 0.3) {
    return convertHexToRGBA(getAlertColor(alert), alpha);
  }

  global.NWS_EVENT_COLORS = NWS_EVENT_COLORS;
  global.NWS_SEVERITY_COLORS = NWS_SEVERITY_COLORS;
  global.NWS_DEFAULT_ALERT_COLOR = DEFAULT_ALERT_COLOR;
  global.getAlertColor = getAlertColor;
  global.convertHexToRGBA = convertHexToRGBA;
  global.getAlertColorWithOpacity = getAlertColorWithOpacity;
})(typeof window !== "undefined" ? window : globalThis);
