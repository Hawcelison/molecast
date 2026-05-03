(function () {
  const state = {
    activeLocation: null,
    status: null,
    isOpen: false,
    isSaving: false,
    isLookingUpZip: false,
    searchTimer: null,
    searchSlowTimer: null,
    searchRequestId: 0,
    searchAbortController: null,
    searchResults: [],
    highlightedSearchIndex: -1,
    previewTimer: null,
    previewRequestId: 0,
    activeMarker: null,
    activeMarkerRetryTimer: null,
    activeMarkerRetryCount: 0,
    previewMarker: null,
    previewMarkerRetryTimer: null,
    previewMarkerRetryCount: 0,
    isPlacingPin: false,
    mapPlacementClickHandler: null,
    mapPlacementKeyHandler: null,
    mapPlacementMap: null,
  };

  const PREVIEW_ONLY_TEXT = "Preview only — click Save to make this active.";
  const DRAG_PREVIEW_TEXT = "Drag the preview pin to refine.";

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

  function setPreviewPinStatus(text, type) {
    const status = getElement("location-preview-pin-status");
    if (!status) {
      return;
    }
    status.textContent = text || "";
    status.dataset.state = type || "";
    status.hidden = !text;
  }

  function previewPinStatusText(prefix) {
    return [prefix, PREVIEW_ONLY_TEXT, DRAG_PREVIEW_TEXT].filter(Boolean).join(" ");
  }

  function setPlacePinButtonActive(isActive) {
    const button = getElement("location-place-pin");
    if (!button) {
      return;
    }
    button.textContent = isActive ? "Cancel pick" : "Pick from map";
    button.setAttribute("aria-pressed", String(isActive));
    button.dataset.active = isActive ? "true" : "false";
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

  function clearSearchSlowTimer() {
    if (state.searchSlowTimer) {
      window.clearTimeout(state.searchSlowTimer);
      state.searchSlowTimer = null;
    }
  }

  function abortPendingSearch() {
    if (state.searchAbortController) {
      state.searchAbortController.abort();
      state.searchAbortController = null;
    }
  }

  function abortPendingPreview() {
    if (state.previewTimer) {
      window.clearTimeout(state.previewTimer);
      state.previewTimer = null;
    }
    state.previewRequestId += 1;
  }

  function clearPreviewMarker() {
    if (state.previewMarkerRetryTimer) {
      window.clearTimeout(state.previewMarkerRetryTimer);
      state.previewMarkerRetryTimer = null;
    }
    state.previewMarkerRetryCount = 0;
    if (state.previewMarker) {
      state.previewMarker.remove();
      state.previewMarker = null;
    }
    setPreviewPinStatus("", "");
  }

  function clearActiveMarker() {
    if (state.activeMarkerRetryTimer) {
      window.clearTimeout(state.activeMarkerRetryTimer);
      state.activeMarkerRetryTimer = null;
    }
    state.activeMarkerRetryCount = 0;
    if (state.activeMarker) {
      state.activeMarker.remove();
      state.activeMarker = null;
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
    if (!isOpen) {
      stopMapPinPlacement({ preserveStatus: true });
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
    const zipCode = lookup.zip_code || lookup.zip || "";
    const label = `${lookup.city}, ${lookup.state} ${zipCode}`.trim();
    return {
      label: label,
      name: label,
      city: lookup.city,
      county: lookup.county,
      state: lookup.state,
      zip_code: zipCode,
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
    const label = suggestion.kind === "address"
      ? suggestion.label || [cityState, zipCode].filter(Boolean).join(" ").trim() || "Selected address"
      : suggestion.kind === "zip" && zipCode
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

  function suggestionKindLabel(suggestion) {
    if (suggestion.kind === "zip") {
      return "ZIP";
    }
    return readableToken(suggestion.kind);
  }

  function isAddressSearchLikely(query) {
    const value = String(query || "").trim();
    return value.length >= 6 && /\d+\s+\S+/.test(value) && /\d/.test(value) && /[A-Za-z]/.test(value);
  }

  function hasAddressSearchWarning(payload) {
    return Array.isArray(payload?.warnings) && payload.warnings.includes("address_search_unavailable");
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

  function setFieldValue(name, value) {
    const field = getField(name);
    if (!field || value === null || value === undefined || value === "") {
      return;
    }
    field.value = String(value);
  }

  function previewLocationLabel(previewPayload) {
    const cityState = [previewPayload.city, previewPayload.state].filter(Boolean).join(", ");
    return [cityState, previewPayload.zip_code].filter(Boolean).join(" ").trim();
  }

  function identityFieldsMatchActiveLocation() {
    const activeLocation = state.activeLocation || {};
    return ["label", "name"].every(function (name) {
      const fieldValue = getField(name)?.value.trim() || "";
      const activeValue = activeLocation[name] ? String(activeLocation[name]) : "";
      return !fieldValue || fieldValue === activeValue;
    });
  }

  function populateLocationFieldsFromPreview(previewPayload) {
    if (!previewPayload.city && !previewPayload.county && !previewPayload.state && !previewPayload.zip_code) {
      return false;
    }

    setFieldValue("city", previewPayload.city);
    setFieldValue("county", previewPayload.county);
    setFieldValue("state", previewPayload.state);
    setFieldValue("zip_code", previewPayload.zip_code);

    const label = previewLocationLabel(previewPayload);
    if (label && identityFieldsMatchActiveLocation()) {
      setFieldValue("label", label);
      setFieldValue("name", label);
    }
    return true;
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
    abortPendingPreview();
    setNwsPreview(null, "");
  }

  function makePreviewMarkerElement() {
    const marker = document.createElement("div");
    marker.className = "location-preview-marker molecast-preview-location-marker";
    marker.setAttribute("aria-label", "Preview Location - not saved yet");
    marker.setAttribute("role", "img");

    const dot = document.createElement("span");
    dot.className = "location-preview-marker__dot";
    marker.append(dot);
    return marker;
  }

  function makeActiveMarkerElement() {
    const marker = document.createElement("div");
    marker.className = "location-active-marker molecast-active-location-marker";
    marker.setAttribute("aria-label", "Active Location");
    marker.setAttribute("role", "img");

    const dot = document.createElement("span");
    dot.className = "location-active-marker__dot";

    const label = document.createElement("span");
    label.className = "location-active-marker__label";
    label.textContent = "Active Location";

    marker.append(dot, label);
    return marker;
  }

  function validCoordinate(latitude, longitude) {
    const lat = Number(latitude);
    const lon = Number(longitude);
    return Number.isFinite(lat) && lat >= -90 && lat <= 90 && Number.isFinite(lon) && lon >= -180 && lon <= 180;
  }

  function formatCoordinate(value) {
    return Number(value).toFixed(4);
  }

  function updateLatLonFields(latitude, longitude) {
    const latitudeField = getField("latitude");
    const longitudeField = getField("longitude");
    if (latitudeField) {
      latitudeField.value = formatCoordinate(latitude);
    }
    if (longitudeField) {
      longitudeField.value = formatCoordinate(longitude);
    }
  }

  function focusPreviewLocation(latitude, longitude) {
    const map = window.MOLECAST_MAP;
    if (!map || typeof map.easeTo !== "function") {
      return;
    }
    map.easeTo({
      center: [Number(longitude), Number(latitude)],
      zoom: parseNumberField("default_zoom") || 9,
      bearing: 0,
      pitch: 0,
      duration: 450,
    });
  }

  function applyPreviewCoordinate(latitude, longitude, options) {
    const previewOptions = options || {};
    updateLatLonFields(latitude, longitude);
    const markerPlaced = placePreviewMarker(latitude, longitude, {
      shouldFocus: previewOptions.shouldFocus !== false,
    });
    requestNwsPreview(latitude, longitude);
    if (markerPlaced) {
      setPreviewPinStatus(previewOptions.statusText || previewPinStatusText(), "success");
    }
    if (previewOptions.message) {
      setMessage(previewOptions.message, previewOptions.messageType || "success");
    }
  }

  function handlePreviewMarkerDragEnd() {
    if (!state.previewMarker || typeof state.previewMarker.getLngLat !== "function") {
      return;
    }
    const lngLat = state.previewMarker.getLngLat();
    applyPreviewCoordinate(lngLat.lat, lngLat.lng, {
      shouldFocus: false,
      statusText: previewPinStatusText(),
      message: "Preview pin moved. Review and save to apply.",
    });
  }

  function scheduleActiveMarkerRetry() {
    if (state.activeMarkerRetryTimer) {
      window.clearTimeout(state.activeMarkerRetryTimer);
      state.activeMarkerRetryTimer = null;
    }
    if (state.activeMarkerRetryCount >= 30) {
      return;
    }
    state.activeMarkerRetryCount += 1;
    state.activeMarkerRetryTimer = window.setTimeout(function () {
      state.activeMarkerRetryTimer = null;
      placeActiveMarker(state.activeLocation);
    }, 100);
  }

  function placeActiveMarker(location) {
    if (!location || !validCoordinate(location.latitude, location.longitude)) {
      clearActiveMarker();
      return;
    }

    const map = window.MOLECAST_MAP;
    if (!map || !window.mapboxgl || typeof window.mapboxgl.Marker !== "function") {
      scheduleActiveMarkerRetry();
      return;
    }

    state.activeMarkerRetryCount = 0;
    if (!state.activeMarker) {
      state.activeMarker = new window.mapboxgl.Marker({
        element: makeActiveMarkerElement(),
        anchor: "bottom",
        draggable: false,
        offset: [0, -4],
      });
    }

    state.activeMarker.setLngLat([Number(location.longitude), Number(location.latitude)]).addTo(map);
  }

  function schedulePreviewMarkerRetry(latitude, longitude) {
    if (state.previewMarkerRetryTimer) {
      window.clearTimeout(state.previewMarkerRetryTimer);
      state.previewMarkerRetryTimer = null;
    }
    if (state.previewMarkerRetryCount >= 30) {
      return;
    }
    state.previewMarkerRetryCount += 1;
    state.previewMarkerRetryTimer = window.setTimeout(function () {
      state.previewMarkerRetryTimer = null;
      placePreviewMarker(latitude, longitude, { shouldFocus: false });
    }, 100);
  }

  function placePreviewMarker(latitude, longitude, options) {
    const shouldFocus = !options || options.shouldFocus !== false;
    if (!validCoordinate(latitude, longitude)) {
      clearPreviewMarker();
      setPreviewPinStatus("Preview pin unavailable for this selection.", "warning");
      return false;
    }

    const map = window.MOLECAST_MAP;
    if (!map || !window.mapboxgl || typeof window.mapboxgl.Marker !== "function") {
      setPreviewPinStatus(`${PREVIEW_ONLY_TEXT} Waiting for the map.`, "pending");
      schedulePreviewMarkerRetry(latitude, longitude);
      return false;
    }

    state.previewMarkerRetryCount = 0;
    if (!state.previewMarker) {
      state.previewMarker = new window.mapboxgl.Marker({
        element: makePreviewMarkerElement(),
        anchor: "bottom",
        draggable: true,
      });
      state.previewMarker.on("dragend", handlePreviewMarkerDragEnd);
    }

    state.previewMarker.setLngLat([Number(longitude), Number(latitude)]).addTo(map);
    setPreviewPinStatus(previewPinStatusText(), "success");
    if (shouldFocus) {
      focusPreviewLocation(latitude, longitude);
    }
    return true;
  }

  function setMapPlacementCursor(map, cursor) {
    if (!map || typeof map.getCanvas !== "function") {
      return;
    }
    const canvas = map.getCanvas();
    if (canvas) {
      canvas.style.cursor = cursor || "";
    }
  }

  function stopMapPinPlacement(options) {
    const settings = options || {};
    const map = state.mapPlacementMap || window.MOLECAST_MAP;
    if (map && state.mapPlacementClickHandler && typeof map.off === "function") {
      map.off("click", state.mapPlacementClickHandler);
    }
    if (state.mapPlacementKeyHandler) {
      document.removeEventListener("keydown", state.mapPlacementKeyHandler);
    }

    setMapPlacementCursor(map, "");
    state.isPlacingPin = false;
    state.mapPlacementClickHandler = null;
    state.mapPlacementKeyHandler = null;
    state.mapPlacementMap = null;
    setPlacePinButtonActive(false);

    if (!settings.preserveStatus) {
      setPreviewPinStatus(settings.statusText || "", settings.statusType || "");
    }
  }

  function startMapPinPlacement() {
    if (state.isPlacingPin) {
      stopMapPinPlacement({
        statusText: state.previewMarker ? previewPinStatusText() : "",
        statusType: state.previewMarker ? "success" : "",
      });
      return;
    }

    const map = window.MOLECAST_MAP;
    if (!map || typeof map.on !== "function") {
      setPreviewPinStatus("Map is still loading. Try placing the pin again in a moment.", "pending");
      return;
    }

    stopMapPinPlacement({ preserveStatus: true });
    state.isPlacingPin = true;
    state.mapPlacementMap = map;
    state.mapPlacementClickHandler = function (event) {
      const lngLat = event && event.lngLat;
      if (!lngLat || !validCoordinate(lngLat.lat, lngLat.lng)) {
        return;
      }
      if (event.originalEvent) {
        event.originalEvent.preventDefault();
        event.originalEvent.stopPropagation();
      }
      applyPreviewCoordinate(lngLat.lat, lngLat.lng, {
        shouldFocus: false,
        statusText: previewPinStatusText(),
        message: "Preview pin placed. Review and save to apply.",
      });
      stopMapPinPlacement({ preserveStatus: true });
    };
    state.mapPlacementKeyHandler = function (event) {
      if (event.key !== "Escape") {
        return;
      }
      event.preventDefault();
      stopMapPinPlacement({
        statusText: state.previewMarker ? previewPinStatusText() : "",
        statusType: state.previewMarker ? "success" : "",
      });
    };

    map.on("click", state.mapPlacementClickHandler);
    document.addEventListener("keydown", state.mapPlacementKeyHandler);
    setMapPlacementCursor(map, "crosshair");
    setPlacePinButtonActive(true);
    setPreviewPinStatus(`Click the map to place the preview pin. ${PREVIEW_ONLY_TEXT}`, "pending");
  }

  function useMapCenterForPreview() {
    const map = window.MOLECAST_MAP;
    if (!map || typeof map.getCenter !== "function") {
      setPreviewPinStatus("Map is still loading. Try using map center again in a moment.", "pending");
      return;
    }
    const center = map.getCenter();
    if (!center || !validCoordinate(center.lat, center.lng)) {
      setPreviewPinStatus("Map center is unavailable.", "warning");
      return;
    }
    stopMapPinPlacement({ preserveStatus: true });
    applyPreviewCoordinate(center.lat, center.lng, {
      shouldFocus: false,
      statusText: previewPinStatusText(),
      message: "Map center selected. Review and save to apply.",
    });
  }

  function renderNwsPreview(previewPayload) {
    const wrapper = document.createElement("div");
    const title = document.createElement("div");
    title.className = "location-editor__nws-preview-title";
    title.textContent = "Selected point preview";

    const grid = document.createElement("div");
    grid.className = "location-editor__nws-preview-grid";

    [
      ["Coordinates", `${formatCoordinate(previewPayload.latitude)}, ${formatCoordinate(previewPayload.longitude)}`],
      ["Location", previewLocationLabel(previewPayload) || "Unavailable"],
      ["County", valueOrUnavailable(previewPayload.county)],
      ["NWS office", `${valueOrUnavailable(previewPayload.nws_office_code)} / ${valueOrUnavailable(previewPayload.nws_office_name)}`],
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

      const type = document.createElement("span");
      type.className = "location-editor__suggestion-type";
      type.textContent = suggestionKindLabel(suggestion);

      const label = document.createElement("span");
      label.className = "location-editor__suggestion-label";
      label.textContent = suggestion.label || "Unnamed location";
      primary.append(type, label);

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
    stopMapPinPlacement({ preserveStatus: true });
    applyPreviewCoordinate(suggestion.latitude, suggestion.longitude, {
      statusText: previewPinStatusText(),
    });
    setSearchStatus("Select a location, then review and save.", "success");
    setMessage("Search populated the editor. Preview only; review and save to apply.", "success");
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
    clearSearchSlowTimer();
    state.searchAbortController = new AbortController();
    const isAddressSearch = isAddressSearchLikely(query);
    setSearchStatus(isAddressSearch ? "Searching address provider..." : "Searching locations...", "pending");
    if (isAddressSearch) {
      state.searchSlowTimer = window.setTimeout(function () {
        if (requestId === state.searchRequestId) {
          setSearchStatus("Address search is taking longer than usual...", "pending");
        }
      }, 2500);
    }

    try {
      const payload = await fetchJson(
        `/api/location/search?q=${encodeURIComponent(query)}&limit=8&type=zip,city,address`,
        { signal: state.searchAbortController.signal },
      );
      if (requestId !== state.searchRequestId) {
        return;
      }
      clearSearchSlowTimer();
      const suggestions = Array.isArray(payload?.results) ? payload.results : [];
      if (suggestions.length === 0) {
        clearSuggestions();
        setSearchStatus(
          hasAddressSearchWarning(payload)
            ? "Address search is unavailable right now. ZIP and city search may still work."
            : "No matching locations found.",
          hasAddressSearchWarning(payload) ? "warning" : "empty",
        );
        return;
      }
      renderSuggestions(suggestions);
      setSearchStatus(
        hasAddressSearchWarning(payload)
          ? "Address search is unavailable right now. ZIP and city search may still work."
          : "Select a location, then review and save.",
        hasAddressSearchWarning(payload) ? "warning" : "",
      );
    } catch (error) {
      if (error.name === "AbortError" || requestId !== state.searchRequestId) {
        return;
      }
      clearSuggestions();
      setSearchStatus(error.message || "Location search failed.", "error");
    } finally {
      if (requestId === state.searchRequestId) {
        clearSearchSlowTimer();
        state.searchAbortController = null;
      }
    }
  }

  function queueLocationSearch() {
    clearSearchTimer();
    clearSearchSlowTimer();
    abortPendingSearch();
    state.searchRequestId += 1;
    const requestId = state.searchRequestId;
    const query = getSearchInput()?.value.trim() || "";

    stopMapPinPlacement({ preserveStatus: true });
    setSelectedSuggestionPreview(null);
    clearNwsPreview();
    clearPreviewMarker();
    if (query.length < 2) {
      clearSuggestions();
      setSearchStatus("Type at least 2 characters to search ZIP, city, or address.", "");
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

  function requestNwsPreview(latitude, longitude) {
    if (!Number.isFinite(Number(latitude)) || !Number.isFinite(Number(longitude))) {
      setNwsPreview("NWS preview unavailable for this selection.", "warning");
      return;
    }

    abortPendingPreview();
    const requestId = state.previewRequestId;
    setNwsPreview("NWS preview: checking selected point...", "pending");

    state.previewTimer = window.setTimeout(function () {
      state.previewTimer = null;
      fetchNwsPreview(latitude, longitude, requestId);
    }, 150);
  }

  async function fetchNwsPreview(latitude, longitude, requestId) {
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
      });
      if (requestId !== state.previewRequestId) {
        return;
      }
      renderNwsPreview(preview);
      if (populateLocationFieldsFromPreview(preview)) {
        setMessage("Preview populated location details. Review and save to apply.", "success");
      }
    } catch (error) {
      if (requestId !== state.previewRequestId) {
        return;
      }
      setNwsPreview(`NWS preview unavailable: ${error.message || "selected point could not be checked."}`, "warning");
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
      const lookup = await fetchJson(`/api/location/zip/${encodeURIComponent(zipCode)}`);
      const location = buildZipLocation(lookup);
      populateForm(location);
      clearSuggestions();
      setSelectedSuggestionPreview(null);
      stopMapPinPlacement({ preserveStatus: true });
      applyPreviewCoordinate(location.latitude, location.longitude, {
        statusText: previewPinStatusText(),
      });
      setSearchStatus("Select a location, then review and save.", "");
      setMessage("ZIP lookup populated the editor. Preview only; review and save to apply.", "success");
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
    placeActiveMarker(state.activeLocation);
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
    stopMapPinPlacement({ preserveStatus: true });
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
      placeActiveMarker(location);
      clearPreviewMarker();
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
      stopMapPinPlacement({ preserveStatus: true });
      clearSearchTimer();
      abortPendingSearch();
      clearNwsPreview();
      clearPreviewMarker();
      placeActiveMarker(state.activeLocation);
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
    getElement("location-place-pin")?.addEventListener("click", startMapPinPlacement);
    getElement("location-use-map-center")?.addEventListener("click", useMapCenterForPreview);
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
    placeActiveMarker(state.activeLocation);
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
    placeActiveMarker: function () {
      placeActiveMarker(state.activeLocation);
    },
  };

  document.addEventListener("DOMContentLoaded", initialize);
})();
