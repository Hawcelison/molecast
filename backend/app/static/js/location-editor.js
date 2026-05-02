(function () {
  const state = {
    activeLocation: null,
    status: null,
    isOpen: false,
    isSaving: false,
    isLookingUpZip: false,
    searchTimer: null,
    searchRequestId: 0,
    searchAbortController: null,
    searchResults: [],
    highlightedSearchIndex: -1,
    previewRequestId: 0,
    previewAbortController: null,
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

  function getSearchInput() {
    return getElement("location-search");
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

  function setSearchStatus(text, type) {
    const status = getElement("location-search-status");
    if (!status) {
      return;
    }
    status.textContent = text || "";
    status.dataset.state = type || "";
  }

  function setSearchExpanded(isExpanded) {
    const input = getSearchInput();
    if (input) {
      input.setAttribute("aria-expanded", String(isExpanded));
      if (!isExpanded) {
        input.removeAttribute("aria-activedescendant");
      }
    }
  }

  function clearSearchTimer() {
    if (state.searchTimer) {
      window.clearTimeout(state.searchTimer);
      state.searchTimer = null;
    }
  }

  function abortPendingSearch() {
    if (state.searchAbortController) {
      state.searchAbortController.abort();
      state.searchAbortController = null;
    }
  }

  function abortPendingPreview() {
    if (state.previewAbortController) {
      state.previewAbortController.abort();
      state.previewAbortController = null;
    }
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
      setSearchStatus("Select a location, then review and save.", "");
      getSearchInput()?.focus();
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

  function buildSuggestionLocation(suggestion) {
    const city = suggestion.city || "";
    const stateCode = suggestion.state || "";
    const zipCode = suggestion.zip || "";
    const cityState = [city, stateCode].filter(Boolean).join(", ");
    const label = suggestion.kind === "zip" && zipCode
      ? `${cityState} ${zipCode}`.trim()
      : cityState || suggestion.label || "Selected location";

    return {
      label: label,
      name: label,
      city: city,
      county: suggestion.county || "",
      state: stateCode,
      zip_code: zipCode,
      latitude: suggestion.latitude,
      longitude: suggestion.longitude,
      default_zoom: suggestion.default_zoom || parseNumberField("default_zoom") || 9,
    };
  }

  function readableToken(value) {
    return String(value || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, function (letter) {
        return letter.toUpperCase();
      });
  }

  function suggestionSecondaryText(suggestion) {
    const parts = [];
    const county = suggestion.county || "";
    if (suggestion.kind) {
      parts.push(readableToken(suggestion.kind));
    }
    if (suggestion.accuracy) {
      parts.push(readableToken(suggestion.accuracy));
    }
    if (county) {
      parts.push(county.toLowerCase().endsWith(" county") ? county : `${county} County`);
    }
    return parts.join(" - ");
  }

  function updateHighlightedSuggestion() {
    const input = getSearchInput();
    const options = Array.from(getElement("location-search-results")?.querySelectorAll("[role='option']") || []);
    options.forEach(function (option, index) {
      const isHighlighted = index === state.highlightedSearchIndex;
      option.classList.toggle("is-highlighted", isHighlighted);
      option.setAttribute("aria-selected", String(isHighlighted));
      if (isHighlighted && input) {
        input.setAttribute("aria-activedescendant", option.id);
      }
    });
    if (state.highlightedSearchIndex < 0 && input) {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function clearSuggestions() {
    const results = getElement("location-search-results");
    state.searchResults = [];
    state.highlightedSearchIndex = -1;
    if (results) {
      results.replaceChildren();
      results.hidden = true;
    }
    setSearchExpanded(false);
  }

  function valueOrUnavailable(value) {
    if (value === null || value === undefined || value === "") {
      return "Unavailable";
    }
    return String(value);
  }

  function setNwsPreview(content, type) {
    const preview = getElement("location-nws-preview");
    if (!preview) {
      return;
    }
    preview.replaceChildren();
    preview.dataset.state = type || "";
    if (!content) {
      preview.hidden = true;
      return;
    }
    preview.hidden = false;
    if (typeof content === "string") {
      preview.textContent = content;
      return;
    }
    preview.append(content);
  }

  function clearNwsPreview() {
    state.previewRequestId += 1;
    abortPendingPreview();
    setNwsPreview(null, "");
  }

  function renderNwsPreview(previewPayload) {
    const wrapper = document.createElement("div");
    const title = document.createElement("div");
    title.className = "location-editor__nws-preview-title";
    title.textContent = `NWS Office: ${valueOrUnavailable(previewPayload.nws_office_code)} / ${valueOrUnavailable(previewPayload.nws_office_name)}`;

    const grid = document.createElement("div");
    grid.className = "location-editor__nws-preview-grid";

    [
      ["Grid", `${valueOrUnavailable(previewPayload.nws_office)} ${valueOrUnavailable(previewPayload.nws_grid_x)},${valueOrUnavailable(previewPayload.nws_grid_y)}`],
      ["Forecast zone", valueOrUnavailable(previewPayload.forecast_zone)],
      ["County zone", valueOrUnavailable(previewPayload.county_zone)],
      ["Timezone", valueOrUnavailable(previewPayload.timezone)],
    ].forEach(function ([label, value]) {
      const row = document.createElement("div");
      row.textContent = `${label}: ${value}`;
      grid.append(row);
    });

    wrapper.append(title, grid);
    setNwsPreview(wrapper, "ok");
  }

  function renderSuggestions(suggestions) {
    const results = getElement("location-search-results");
    if (!results) {
      return;
    }

    results.replaceChildren();
    state.searchResults = suggestions;
    state.highlightedSearchIndex = suggestions.length > 0 ? 0 : -1;

    suggestions.forEach(function (suggestion, index) {
      const option = document.createElement("button");
      option.id = `location-search-option-${index}`;
      option.className = "location-editor__suggestion";
      option.type = "button";
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", "false");
      option.addEventListener("click", function () {
        selectSuggestion(index);
      });

      const primary = document.createElement("span");
      primary.className = "location-editor__suggestion-primary";
      primary.textContent = suggestion.label || "Unnamed location";

      const secondary = document.createElement("span");
      secondary.className = "location-editor__suggestion-secondary";
      secondary.textContent = suggestionSecondaryText(suggestion);

      option.append(primary, secondary);
      results.append(option);
    });

    results.hidden = suggestions.length === 0;
    setSearchExpanded(suggestions.length > 0);
    updateHighlightedSuggestion();
  }

  function setSelectedSuggestionPreview(suggestion) {
    const preview = getElement("location-selected-suggestion");
    if (!preview) {
      return;
    }
    if (!suggestion) {
      preview.hidden = true;
      preview.textContent = "";
      return;
    }
    const secondary = suggestionSecondaryText(suggestion);
    preview.textContent = secondary
      ? `Selected: ${suggestion.label} (${secondary})`
      : `Selected: ${suggestion.label}`;
    preview.hidden = false;
  }

  function selectSuggestion(index) {
    const suggestion = state.searchResults[index];
    if (!suggestion) {
      return;
    }

    populateForm(buildSuggestionLocation(suggestion));
    const input = getSearchInput();
    if (input) {
      input.value = suggestion.label || "";
    }
    clearSuggestions();
    setSelectedSuggestionPreview(suggestion);
    requestNwsPreview(suggestion.latitude, suggestion.longitude);
    setSearchStatus("Select a location, then review and save.", "success");
    setMessage("Search populated the editor. Review and save to apply.", "success");
    getField("label")?.focus();
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

  async function searchLocations(query, requestId) {
    abortPendingSearch();
    state.searchAbortController = new AbortController();
    setSearchStatus("Searching locations...", "pending");

    try {
      const payload = await fetchJson(
        `/api/location/search?q=${encodeURIComponent(query)}&limit=8&type=zip,city`,
        { signal: state.searchAbortController.signal },
      );
      if (requestId !== state.searchRequestId) {
        return;
      }
      const suggestions = Array.isArray(payload?.results) ? payload.results : [];
      if (suggestions.length === 0) {
        clearSuggestions();
        setSearchStatus("No matching locations found", "empty");
        return;
      }
      renderSuggestions(suggestions);
      setSearchStatus("Select a location, then review and save.", "");
    } catch (error) {
      if (error.name === "AbortError" || requestId !== state.searchRequestId) {
        return;
      }
      clearSuggestions();
      setSearchStatus(error.message || "Location search failed.", "error");
    } finally {
      if (requestId === state.searchRequestId) {
        state.searchAbortController = null;
      }
    }
  }

  function queueLocationSearch() {
    clearSearchTimer();
    abortPendingSearch();
    state.searchRequestId += 1;
    const requestId = state.searchRequestId;
    const query = getSearchInput()?.value.trim() || "";

    setSelectedSuggestionPreview(null);
    clearNwsPreview();
    if (query.length < 2) {
      clearSuggestions();
      setSearchStatus("Type at least 2 characters to search ZIP or city.", "");
      return;
    }

    state.searchTimer = window.setTimeout(function () {
      searchLocations(query, requestId);
    }, 300);
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

  async function requestNwsPreview(latitude, longitude) {
    if (!Number.isFinite(Number(latitude)) || !Number.isFinite(Number(longitude))) {
      setNwsPreview("NWS preview unavailable for this selection.", "warning");
      return;
    }

    abortPendingPreview();
    state.previewRequestId += 1;
    const requestId = state.previewRequestId;
    state.previewAbortController = new AbortController();
    setNwsPreview("NWS preview: checking selected point...", "pending");

    try {
      const preview = await fetchJson("/api/location/points/preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          latitude: Number(latitude),
          longitude: Number(longitude),
        }),
        signal: state.previewAbortController.signal,
      });
      if (requestId !== state.previewRequestId) {
        return;
      }
      renderNwsPreview(preview);
    } catch (error) {
      if (error.name === "AbortError" || requestId !== state.previewRequestId) {
        return;
      }
      setNwsPreview(`NWS preview unavailable: ${error.message || "selected point could not be checked."}`, "warning");
    } finally {
      if (requestId === state.previewRequestId) {
        state.previewAbortController = null;
      }
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
      clearSuggestions();
      setSelectedSuggestionPreview(null);
      clearNwsPreview();
      setSearchStatus("Select a location, then review and save.", "");
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
      clearSearchTimer();
      abortPendingSearch();
      clearNwsPreview();
      clearSuggestions();
      setSelectedSuggestionPreview(null);
      if (getSearchInput()) {
        getSearchInput().value = "";
      }
      setSearchStatus("Select a location, then review and save.", "");
      populateForm(state.activeLocation);
      setPanelOpen(false);
    });
    getElement("location-zip-lookup")?.addEventListener("click", lookupZipCode);
    getElement("location-editor-form")?.addEventListener("submit", saveLocation);
    getSearchInput()?.addEventListener("input", queueLocationSearch);
    getSearchInput()?.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        if (state.searchResults.length > 0) {
          event.preventDefault();
          state.highlightedSearchIndex = Math.min(
            state.highlightedSearchIndex + 1,
            state.searchResults.length - 1,
          );
          updateHighlightedSuggestion();
        }
      } else if (event.key === "ArrowUp") {
        if (state.searchResults.length > 0) {
          event.preventDefault();
          state.highlightedSearchIndex = Math.max(state.highlightedSearchIndex - 1, 0);
          updateHighlightedSuggestion();
        }
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (state.highlightedSearchIndex >= 0) {
          selectSuggestion(state.highlightedSearchIndex);
        }
      } else if (event.key === "Escape") {
        event.preventDefault();
        clearSearchTimer();
        abortPendingSearch();
        clearSuggestions();
        setSearchStatus("Select a location, then review and save.", "");
      }
    });
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
    searchLocations: function () {
      queueLocationSearch();
    },
    getActiveLocation: function () {
      return state.activeLocation;
    },
  };

  document.addEventListener("DOMContentLoaded", initialize);
})();
