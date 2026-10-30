# Morph TV: initial Samsung app analysis
> Further investigation: [full feature/theme inventory and recreation plan](morphtv/README.md), including Samsung 0.8.191 and Android/phone 0.8.192 test assets.

Inspected 2026-10-29. This is a static inspection of the public release, not a physical-TV or Android app test. No changes were made to the running NetFelix app during this analysis.

## Sources and release identity

- Website: https://morphtv.herroshetta.com/
- Release catalog: https://morphtv.herroshetta.com/catalog.json
- Checksums: https://morphtv.herroshetta.com/SHA256SUMS.txt
- Inspected archive: https://morphtv.herroshetta.com/Morph-TV-Samsung-Computer-0.8.170.zip
- SHA-256: `b39ca838d98e49af7e57604e9d2e7f96331eb822e17adcb7bae442ac96878e52` (verified).

The catalog lists public preview 0.8.170. The landing page separately advertises a 0.8.192 test build; that build was not inspected. The Samsung catalog entry says `available: false` and `physicalDeviceVerified: false`, while exposing computer-install packages. Treat these as separate availability and verification signals.

## What the downloaded app contains

The Samsung computer ZIP contains readable HTML, CSS, JavaScript and assets directly, rather than a nested WGT. Its manifest starts `index.html`, targets Samsung TV/Tizen 5.0, declares a 1920×1080 screen, and disables background support. A separate Tizen 4 configuration is included. Its internal JavaScript namespace is `ClearTV`.

| Area | Evidence in archive | Finding |
| --- | --- | --- |
| Home and appearance | `dock.js`, `home-reference.js`, `theme-packs.js`, `ui/tokens.css` | Separate modules for dock, home presentation and theme assets/tokens. |
| Settings and profiles | `core.js`, `family-ui.js` | JSON localStorage settings; profile-specific settings, pins and recent items. Profile creation caps the list at six. |
| Remote navigation | `focus.js`, `remote.js` | Focus scopes and visible controls; remote commands dispatch keyboard events; text insertion targets an active editable control. This does not establish the phone transport protocol. |
| IPTV | `samsung-media.js`, `iptv/`, `m3u-source.js` | Samsung integration plus a separate IPTV interface. Settings reference subscriptions, favorites and playback progress. Actual provider compatibility was not tested. |
| Radio | `radio/`, `radio/stations.json` | Separate station/player interface and station data. |
| Prayer | `prayer.js`, `prayer.css`, prayer audio assets | Dedicated prayer interface and bundled Adhan audio. Calculation accuracy and audible playback were not tested. |
| Device integration | `samsung-adapter.js`, `inputs.js`, `usb-media.js` | Samsung adapter, input diagnostics and USB-related modules. Hardware functionality remains unverified. |
| Playback dependencies | `vendor/hls-1.5.18.light.min.js`, vendor license files | Bundled HLS.js; actual codec support still depends on the device. |
| Weather | `core.js`, `weather.js` | Configured Open-Meteo forecast/geocoding endpoints and IP-based location services; weather/location cache durations are defined. |

## Comparison with NetFelix

NetFelix currently has a small installed Tizen launcher that redirects to the Python-served TV dashboard. Morph's inspected Samsung package bundles its interface locally. That architectural distinction affects startup, offline UI availability, deployment and access to privileged TV APIs.

NetFelix already provides app shortcuts, geometric remote navigation, matches, prayer widgets, radio and Jellyfin integration. A practical independent recreation can build on those rather than replacing the media stack.

Suggested implementation sequence:

1. Introduce persistent appearance settings: palette, text size, reduced motion, clock format and home-section visibility.
2. Make app favorites and recent usage real persisted data, with a remote-accessible reorder interface.
3. Add dedicated radio and media-library views with consistent focus scopes and Back restoration.
4. Add profiles, keeping UI preferences separate from Jellyfin authentication and parental enforcement.
5. Implement paired phone controls against NetFelix's own backend with an explicit command protocol.
6. Consider bundling the interface in the Tizen package once privileged device integrations are needed; verify on the user's TV.

## Boundaries of these findings

The public package makes static architecture analysis possible without binary decompilation. This inspection does not establish Android internals, the complete phone pairing protocol, Samsung hardware compatibility, or behavior of paid features. Any NetFelix recreation should use independently written code and original or appropriately licensed artwork. Downloaded app files are kept outside the repository in `/tmp/morphtv-inspect`; only this analysis is added to the project.
