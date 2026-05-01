(function () {
  const state = {
    activeLocation: null,
    status: null,
    isOpen: false,
    isSaving: false,
    isLookingUpZip: false,
  };

  const fieldNames = [
    "label",
    "name",
    "latitude",
    "longitude",
    "city",
    "county",
    "state",
    "zip_code",
    "default_zoom",
  ];

  function getConfig() {
    window.MOLECAST_CONFIG = window.MOLECAST_CONFIG || {};
    return window.MOLECAST_CONFIG;
  }

  function getElement(id) {
    return document.getElementById(id);
  }

  function getField(name) {
    return getElement(`location-${name.replace("_", "-")}`);
  }

  function formatLocation(location) {
    if (!location) {
      return "Unavailable";
    }
    return location.label || location.name || [location.city, location.state].filter(Boolean).join(", ") || "Unnamed location";
  }

  function metadataText(location, status) {
    const statusValue = status && status.nws_metadata_status;
    if (statusValue === "current" || location?.nws_points_updated_at) {
      return "NWS metadata: current";
    }
    return "NWS metadata: unavailable; using point fallback";
  }

  function setMessage(text, type) {
    const message = getElement("location-editor-message");
    if (!message) {
      return;
    }
    message.textContent = text || "";
    message.dataset.state = type || "";
  }

  function setPanelOpen(isOpen) {
    state.isOpen = isOpen;
    const panel = getElement("location-editor-panel");
    const button = getElement("location-editor-toggle");
    if (panel) {
      panel.hidden = !isOpen;
    }
    if (button) {
      button.setAttribute("aria-expanded", String(isOpen));
      button.textContent = isOpen ? "Close editor" : "Edit location";
    }
    if (isOpen) {
      populateForm(state.activeLocation);
      getField("label")?.focus();
    }
  }

  function populateForm(location) {
    if (!location) {
      return;
    }
    fieldNames.forEach(function (name) {
      const field = getField(name);
      if (!field) {
        return;
      }
      const value = location[name];
      field.value = value === null || value === undefined ? "" : String(value);
    });
  }

  function updateDisplay() {
    const location = state.activeLocation;
    const display = getElement("active-location-display");
    const statusLine = getElement("location-metadata-status");
    if (display) {
      display.textContent = `Location: ${formatLocation(location)}`;
    }
    if (statusLine) {
      statusLine.textContent = metadataText(location, state.status);
    }
  }

  function parseNumberField(name) {
    const field = getField(name);
    const value = Number(field?.value);
    return Number.isFinite(value) ? value : NaN;
  }

  function collectPayload() {
    const latitude = parseNumberField("latitude");
    const longitude = parseNumberField("longitude");
    const defaultZoom = parseNumberField("default_zoom");
    const errors = [];

    if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
      errors.push("Latitude must be between -90 and 90.");
    }
    if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
      errors.push("Longitude must be between -180 and 180.");
    }
    if (!Number.isFinite(defaultZoom) || defaultZoom < 3 || defaultZoom > 14) {
      errors.push("Default zoom must be between 3 and 14.");
    }
    if (errors.length > 0) {
      return { errors };
    }

    const payload = {
      latitude: latitude,
      longitude: longitude,
      default_zoom: defaultZoom,
    };

    ["label", "name", "city", "county", "state", "zip_code"].forEach(function (name) {
      const value = getField(name)?.value.trim();
      if (value) {
        payload[name] = name === "state" ? value.toUpperCase() : value;
      }
    });

    return { payload };
  }

  function buildZipLocation(lookup) {
    const label = `${lookup.city}, ${lookup.state} ${lookup.zip_code}`.trim();
    return {
      label: label,
      name: label,
      city: lookup.city,
      county: lookup.county,
      state: lookup.state,
      zip_code: lookup.zip_code,
      latitude: lookup.latitude,
      longitude: lookup.longitude,
      default_zoom: lookup.default_zoom || 9,
    };
  }

  async function fetchJson(url, options) {
    const response = await window.fetch(url, options);
    let body = null;
    try {
      body = await response.json();
    } catch (_error) {
      body = null;
    }
    if (!response.ok) {
      const detail = body && (body.detail || body.message);
      throw new Error(typeof detail === "string" ? detail : `Request failed with ${response.status}.`);
    }
    return body;
  }

  function updateConfig(location) {
    const config = getConfig();
    config.activeLocation = location;
    config.map = config.map || {};
    config.map.center = {
      latitude: location.latitude,
      longitude: location.longitude,
    };
    config.map.zoom = location.default_zoom || config.map.zoom || 9;
  }

  function moveMap(location) {
    const map = window.MOLECAST_MAP;
    if (!map || typeof map.jumpTo !== "function") {
      return;
    }
    map.jumpTo({
      center: [location.longitude, location.latitude],
      zoom: location.default_zoom || 9,
      bearing: 0,
      pitch: 0,
    });
  }

  async function refreshAlerts() {
    if (window.MOLECAST_APP && typeof window.MOLECAST_APP.refreshAlerts === "function") {
      await window.MOLECAST_APP.refreshAlerts();
    }
  }

  async function lookupZipCode() {
    if (state.isLookingUpZip) {
      return;
    }

    const zipField = getField("zip_code");
    const zipCode = zipField?.value.trim();
    if (!zipCode) {
      setMessage("Enter a ZIP code before lookup.", "error");
      zipField?.focus();
      return;
    }

    const lookupButton = getElement("location-zip-lookup");
    state.isLookingUpZip = true;
    if (lookupButton) {
      lookupButton.disabled = true;
    }
    setMessage("Looking up ZIP code...", "pending");

    try {
      const lookup = await fetchJson(`/api/location/lookup/${encodeURIComponent(zipCode)}`);
      populateForm(buildZipLocation(lookup));
      setMessage("ZIP lookup populated the editor. Review and save to apply.", "success");
      getField("label")?.focus();
    } catch (error) {
      setMessage(error.message || "ZIP lookup failed.", "error");
      zipField?.focus();
    } finally {
      state.isLookingUpZip = false;
      if (lookupButton) {
        lookupButton.disabled = false;
      }
    }
  }

  async function refresh() {
    const status = await fetchJson("/api/location/status");
    state.status = status;
    state.activeLocation = status.active_location;
    updateConfig(state.activeLocation);
    updateDisplay();
    populateForm(state.activeLocation);
    return state.activeLocation;
  }

  async function saveLocation(event) {
    event.preventDefault();
    if (state.isSaving) {
      return;
    }

    const result = collectPayload();
    if (result.errors) {
      setMessage(result.errors.join(" "), "error");
      return;
    }

    const saveButton = getElement("location-editor-save");
    state.isSaving = true;
    if (saveButton) {
      saveButton.disabled = true;
    }
    setMessage("Saving location...", "pending");

    try {
      const location = await fetchJson("/api/location/active", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(result.payload),
      });
      state.activeLocation = location;
      state.status = {
        active_location: location,
        nws_metadata_status: location.nws_points_updated_at ? "current" : "missing",
      };
      updateConfig(location);
      updateDisplay();
      populateForm(location);
      moveMap(location);
      await refreshAlerts();
      setMessage("Location saved.", "success");
    } catch (error) {
      setMessage(error.message || "Location could not be saved.", "error");
      populateForm(state.activeLocation);
    } finally {
      state.isSaving = false;
      if (saveButton) {
        saveButton.disabled = false;
      }
    }
  }

  function bindEvents() {
    getElement("location-editor-toggle")?.addEventListener("click", function () {
      setPanelOpen(!state.isOpen);
    });
    getElement("location-editor-cancel")?.addEventListener("click", function () {
      setMessage("", "");
      populateForm(state.activeLocation);
      setPanelOpen(false);
    });
    getElement("location-zip-lookup")?.addEventListener("click", lookupZipCode);
    getElement("location-editor-form")?.addEventListener("submit", saveLocation);
  }

  async function initialize() {
    state.activeLocation = getConfig().activeLocation || null;
    updateDisplay();
    populateForm(state.activeLocation);
    bindEvents();

    try {
      await refresh();
    } catch (_error) {
      updateDisplay();
      setMessage("Location status is unavailable.", "error");
    }
  }

  window.MOLECAST_LOCATION_EDITOR = {
    refresh: refresh,
    lookupZipCode: lookupZipCode,
    getActiveLocation: function () {
      return state.activeLocation;
    },
  };

  document.addEventListener("DOMContentLoaded", initialize);
})();
