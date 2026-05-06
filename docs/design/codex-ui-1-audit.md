# Codex UI: 1 Dashboard Audit

Date: 2026-05-06
Scope: Current Molecast dashboard UI and a separate non-production design prototype at `/mockups/codex-ui-1`.

## Current UI Findings

### Visual Hierarchy

- Alert banners are correctly positioned near the top and use strong event colors, which supports fast hazard recognition.
- The header carries too many peer-level controls at once: brand, active location, radar refresh, layers, edit location, saved locations, and alert controls compete for attention.
- The map is functionally central but visually arrives after several operational sections, so it does not read as the primary decision surface on first scan.

Recommendation: keep alerts first, then make active location and the map the dominant above-the-fold objects. Move secondary tools into compact controls or a supporting rail.

### Navigation Clarity

- The current page is mostly a single operational canvas with limited global navigation. This is efficient for known users but gives less orientation for new or occasional users.
- Test alert tooling is exposed in the same footer area as production navigation, which is acceptable locally but should remain visually secondary.

Recommendation: introduce a clear dashboard shell concept with primary areas such as Overview, Map, Locations, Alerts, and Tools. Keep test tooling grouped under Tools and suppress or de-emphasize it in public mode.

### Responsive and Mobile Layout

- The current header already collapses to a single column, and buttons expand to usable widths on small screens.
- The amount of header content can still push the map and alerts down on mobile, especially when alert controls wrap.

Recommendation: use a compact mobile header with active location first, alert state second, and all lower-frequency actions behind grouped controls.

### Spacing and Density

- The current density is useful for an operations dashboard, but several controls have similar visual weight.
- Alert summary chips are compact, which is good. The editor form is detailed and appropriately hidden until needed.

Recommendation: preserve density for repeated operational use, but create stronger section grouping and reduce always-visible control weight.

### Dashboard Information Architecture

- Core tasks are present: monitor alerts, inspect radar/map, manage the active location, monitor saved locations, and access test tools.
- The current ordering does not fully distinguish primary monitoring from configuration and maintenance tasks.

Recommendation: organize the dashboard around a primary monitoring plane, with configuration and saved-location management as supporting panels.

### Alert Visibility

- Full-width alert banners are high-visibility and should stay production-critical.
- Alert summary provides useful context but should not compete with active hazard banners.

Recommendation: retain strong alert banners and keep summary as compact context directly adjacent to the map or active location.

### Map and Radar Usability

- Layer controls and radar auto-refresh are discoverable in the header, but they share space with unrelated location actions.
- The map would benefit from stronger visual framing and nearby controls that clearly belong to map interaction.

Recommendation: keep layer controls compact, but place them with the map. Use a focused map panel with quick toggles for radar, alerts, recenter, and refresh.

### Saved-Location Usability

- Saved locations currently live inside the location editor flow. This keeps production safe but hides monitoring context.
- Users monitoring multiple places need a quick readout without opening the full editor.

Recommendation: separate saved-location monitoring from saved-location editing. Show a compact saved-location status list; keep editing behind an explicit Manage or Edit action.

### Accessibility Basics

- Existing markup uses labels, live regions, button semantics, and details/summary in several places.
- Focus states exist on many controls, but the dense header can still make keyboard pathfinding harder.

Recommendation: keep semantic buttons/links, maintain visible focus rings, use landmarks and headings for major regions, and avoid relying on color alone for alert severity.

### Touch Targets

- Most current buttons meet practical target sizing on mobile after wrapping.
- Small inline controls such as summary chips and dense toggles need consistent minimum heights when they become interactive.

Recommendation: maintain 44px minimum targets for main controls and leave compact chips non-interactive unless they can meet target sizing.

### Progressive Disclosure

- The active location editor is already a good progressive disclosure pattern.
- Layer controls use `details`, which is appropriate for lower-frequency map controls.
- Test tooling should remain discoverable for local development but out of the main monitoring hierarchy.

Recommendation: keep editor and tooling behind explicit actions. Expose only status and quick controls in the default dashboard view.

## Codex UI: 1 Prototype Direction

The prototype explores a modern operations dashboard shell without replacing production:

- A compact prototype strip clearly labels the page as `Codex UI: 1`.
- A global navigation rail improves orientation on desktop and wraps into a compact navigation band on smaller screens.
- The active location is promoted into a prominent status header.
- Alert banners stay visually prioritized above the main content.
- The map/radar panel becomes the largest visual region and owns its layer controls.
- Saved locations and alert summary move into a supporting side stack.
- Test alert tooling is visually secondary and respects public-mode visibility in the mockup.
- Mobile layout collapses to one column with full-width touch targets and no intentional horizontal overflow.

## Production Integration Notes

The approved Codex UI: 1 direction was applied to the production dashboard at `/` without replacing the live dashboard with static mockup content.

- The dashboard now uses a production shell with a navigation rail, compact workspace header, prominent active-location panel, high-priority alert banner region, primary map/radar focus panel, and a supporting side stack for alert summary and location tools.
- Existing production DOM hooks were preserved for active location, alert banners, alert summary scope switching, saved alert drilldown, map/radar rendering, radar auto-refresh, layer controls, alert polygons, county boundaries, and the location editor workflows.
- Layer controls and radar auto-refresh moved from the global active-location header into the map panel so they are discoverable near the map they control.
- The saved-location editor remains the existing functional editor instead of a static monitor list; the production layout exposes it through prominent location actions and a secondary location tools card.
- The non-production `/mockups/codex-ui-1` page remains available as a clearly marked prototype reference.
- The `Codex UI: 1` footer link was de-emphasized as a prototype reference because the design direction is now represented in production.
