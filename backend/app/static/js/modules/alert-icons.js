(function (global) {
  const EVENT_ICONS = Object.freeze({
    "Tornado Warning": "🌪",
    "Tornado Watch": "🌪",
    "Severe Thunderstorm Warning": "⛈",
    "Severe Thunderstorm Watch": "⛈",
    "Flash Flood Warning": "🌊",
    "Flood Warning": "🌊",
    "Blizzard Warning": "❄",
    "Winter Storm Warning": "❄",
    "Ice Storm Warning": "❄",
    "High Wind Warning": "💨",
    "Extreme Wind Warning": "💨",
    "Heat Advisory": "☀",
    "Excessive Heat Warning": "☀",
    "Dense Fog Advisory": "≋",
    "Special Weather Statement": "ℹ",
    "Snow Squall Warning": "❄",
    "Hurricane Warning": "🌀",
    "Tropical Storm Warning": "🌀",
    "Storm Surge Warning": "🌊",
    "Red Flag Warning": "🔥",
    "Fire Weather Watch": "🔥",
    "Winter Weather Advisory": "❄",
  });

  const NAMED_ICONS = Object.freeze({
    "alert-circle": "!",
    "cloud-fog": "≋",
    "cloud-lightning": "⛈",
    flame: "🔥",
    hurricane: "🌀",
    info: "ℹ",
    snowflake: "❄",
    thermometer: "☀",
    "thermometer-sun": "☀",
    tornado: "🌪",
    waves: "🌊",
    wind: "💨",
  });

  function iconForAlert(alert) {
    if (!alert) {
      return "!";
    }
    if (alert.icon && NAMED_ICONS[alert.icon]) {
      return NAMED_ICONS[alert.icon];
    }
    if (alert.icon && typeof alert.icon === "string" && alert.icon.length <= 3) {
      return alert.icon;
    }
    if (alert.event && EVENT_ICONS[alert.event]) {
      return EVENT_ICONS[alert.event];
    }
    return "!";
  }

  global.MolecastAlertIcons = {
    iconForAlert,
  };
})(window);

