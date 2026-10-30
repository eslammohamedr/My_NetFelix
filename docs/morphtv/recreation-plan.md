# Edit the existing NetFelix GUI

This is a proposed implementation sequence, not an implementation or deployment. Keep the current TV app identity and existing media services.

## Existing integration points

| Current file / service | Role | Planned use |
| --- | --- | --- |
| `scripts/tv_dashboard.py` | Python-rendered TV home, inline CSS/JS, prayer/matches/Jellyfin data | Existing GUI entry point; progressively extract static styles and UI controllers, retaining data/render integration. |
| `scripts/ai_media_service.py` | `/tv-dashboard`, `/api/tv/dashboard-data`, wallpaper/icon, requests and TV control routes | Serve UI assets and add validated settings/profile/favorite APIs alongside current routes. |
| `scripts/samsung_tv.py` | Samsung network pairing, remote keys, native app launch and phone remote | Retain pairing and launch capabilities; add a separate command path for navigation inside the NetFelix GUI. |
| `tizen_apps/NetFelixHub/index.html` | Installed launcher redirects to hosted dashboard | Retain initially; later use a local wrapper/bridge when privileged TV APIs are required. |
| `streaming/` and Jellyfin | Existing playback/library/subtitles | Reuse media IDs, resume positions and existing player features. |

The Python file currently mixes presentation, runtime state and data retrieval. Extracting its presentation incrementally will make 32 themes and multiple views maintainable without rebuilding the media backend.

## Stage 1: home composition and theme foundation

Use the reference screen proportions: full-screen scene, restrained left scrim, centered top navigation, slim sidebar, compact prayer card in the top right, large left-aligned hero and bottom-centered app dock. Current NetFelix separates the hero into a large bordered card and includes repeated shortcut rows; consolidate the first screen and keep matches/continue-watching in accessible sections or views.

Create independent NetFelix design tokens for background, raised surface, text, muted text, accent, focus ring, card border, glass opacity, blur, radii and motion duration. Map all 32 themes into a registry with stable IDs, category, colors, hero style and asset references. Use original or appropriately licensed artwork. Do not distribute the original app's scripts, brand assets or paid activation system.

Persist language, theme, font scaling, motion, blur, glow, clock format and home-section visibility. Provide a remote-accessible theme picker with previews and categories. Keep original app access labels only in research metadata; NetFelix does not need commercial theme gates.

Acceptance: readable at 720p and 1080p, no horizontal overflow, visible focus on every control, settings survive reload, Arabic/English layouts work, and reduced effects visibly change the UI without changing playback quality.

## Stage 2: truthful home data and app management

Replace hardcoded recent-app tiles with actual usage history. Add pin/unpin, favorite ordering, app discovery where available, clear empty states and launch failure feedback. Use real Jellyfin media IDs and resume links. Existing continue-watching cards currently direct to app launch rather than guaranteed item-specific resumption; wire each item through a verified playback route.

Preserve the user's matches, search/request flow, wallpaper, household customization and screensaver. Put search/request actions in an explicit dialog with proper editable focus. HDMI tiles should appear as controls only when a functional adapter is available.

Acceptance: favorite order persists, reordering works with the remote, no fake recent entries, correct title/episode launches, and Back restores the originating tile.

## Stage 3: settings, prayer and radio views

Create a settings screen with Appearance, Performance, Home & apps, Prayer, Time & weather and System categories. Centralize focus scopes and view history, retaining the existing input and immediate-Back fixes.

Expand prayer settings with city/method/Asr school, Adhan voice and volume, previews and optional on-screen remembrance. Replace fabricated fallback values with unavailable/cached labels. Add scheduled alert deduplication and pause/resume coordination. A prayer break should be optional and explicitly confined to the GUI.

Expand radio from one toggle into a categorized searchable station library with favorites, reconnect, now-playing state and black-screen cover. Keep station availability failures distinct from empty favorites.

Acceptance: navigation never escapes an active dialog; stale/unavailable weather or prayer data is labeled; alerts do not fire twice; leaving a radio screen follows an explicit playback policy.

## Stage 4: media browsing and player controls

Build live/library/movie/series views over existing Jellyfin and playlist integrations. Add source categories, search, favorites, actual continue-watching and details/episode navigation. Use provider EPG only when available.

Add a remote-friendly player overlay for pause/resume, seeking, next episode/channel, sizing, supported audio/subtitle tracks and stream information. First reuse the existing streaming subtitle implementation. Capability checks must distinguish HTML video, Jellyfin playback and Samsung AVPlay.

Keep provider credentials on the local backend. UI preferences may use local storage, but media-service secrets should not be copied into browser settings. Adding a new source model is a separate implementation task from reproducing the visual shell.

Acceptance: correct item identity, seek/resume accuracy, supported tracks displayed honestly, clear codec/source errors, and Back fully stops or transfers playback according to policy.

## Stage 5: profiles and phone customization

Implement profile-specific appearance, pins, recent items and media favorites, with deliberate mapping to Jellyfin identities. UI profiles alone do not enforce Jellyfin permissions.

Extend the existing phone remote with theme selection, image upload, app ordering, text entry and an explicit internal-UI navigation channel. Suggested independent command shape: action, payload, command ID and acknowledged result. Pair devices using the NetFelix backend, rather than depending on Morph's native APIs.

Add PIN controls only with a defined scope. Network-level access and Jellyfin parental controls must enforce anything intended to apply beyond this GUI. Timers in an app cannot terminate unrelated native apps.

## Stage 6: hardware features and optional modules

For installed-app discovery, HDMI, live broadcast information, AVPlay and USB, introduce a local Tizen bridge and verify privileges/API behavior on the user's actual model. The redirected web dashboard cannot be assumed to have the same privileges as a locally bundled Tizen app. Test Home, Return, standby/resume and cold boot separately.

Kids and fitness can be independent optional modules. The original fitness code is Plus-gated; implement new exercise content and timers independently if selected. Portal providers, Android QR setup and multi-view are separate capability projects, not requirements for the Samsung visual redesign.

## Completion checks for the eventual rebuild

Browser checks: layouts at target resolutions, complete arrow/OK/Back paths, editable search fields, modal focus restoration, preference persistence, profile separation, real empty/loading/failure states and sensible performance with effects disabled.

Physical TV checks: native launches, media decoding, AVPlay tracks, remote media keys, HDMI/USB permissions, safe area, focus speed, standby/resume and Arabic text. These cannot be signed off by a Chromium screenshot alone.
