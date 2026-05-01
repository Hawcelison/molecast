# Alert Banner Modules Manual Checks

No JavaScript test runner is configured for this repo. For this phase, verify in
the browser after starting Molecast:

1. Open the dashboard and confirm alert banners render above the Molecast
   header/logo.
2. Enable two local test alerts and confirm one compact banner appears per
   alert.
3. Confirm compact text follows: icon, alert name, area, until time.
4. Click or press Enter/Space on a banner to expand and minimize details.
5. Add or activate a new alert with a new `canonical_id` or `id`; confirm that
   new banner auto-expands.
6. With reduced motion enabled in the OS/browser, confirm new alerts do not
   smooth-scroll.
7. Confirm the banner container uses `aria-live="assertive"` for an
   Extreme/Severe Immediate warning, and `polite` for lower-priority alerts.
8. Confirm dashboard polling still refreshes around the backend-provided
   interval, defaulting to 60 seconds if omitted.
9. Confirm alert settings persist after reload:
   alert audio and test audio.
10. Confirm audio does not play until `Alert audio` is enabled by a user click.
11. Confirm local test alerts do not play audio unless both `Alert audio` and
   `Test audio` are enabled.
12. Confirm `Silence active` stops audio for the active alert without hiding
   the banner.
13. Confirm `Acknowledge active` stops audio for the active alert.
14. Confirm active Severe/Extreme alerts do not animate the page background;
   severity remains visible through banners, colors, icons, audio, and map
   polygons.
15. Confirm sound profiles by event/source:
   Tornado Warning uses tornado siren; Blizzard/Hurricane/Extreme Wind-type
   warnings use standard alert; Civil/IPAWS test/future alerts use air raid;
   Presidential/National test/future alerts use EBS purge.

Audio notes: browser autoplay policies require the user to interact with the
page before audio can start. The `Alert audio` checkbox is the intended gesture.
