# NetFelix appearance and Android companion, version 1

This version edits the existing TV dashboard. It adds a shared settings service, a phone-friendly appearance editor, and a separate Android phone APK. The existing Wear OS remote remains in its original `:app` module; the new phone app is the `:phone` module.

## Use

1. Open `http://192.168.1.15:8092/tv-customize` from a phone on the home network, or download the APK from `http://192.168.1.15:8092/downloads/netfelix-companion.apk` and install it on an Android 8+ phone.
2. In the Android app, enter your NetFelix server address and tap **Connect to my TV**. The app hosts the same editor, so browser and Android behavior stay consistent. It requires a reachable NetFelix server.
3. Open or reopen NetFelix Hub on the TV. Choose a palette, preview it, then press **Apply to TV**. The open TV dashboard checks for changed settings every 1.5 seconds; no TV app reinstall is needed for this hosted interface.
4. The TV dock also has an **Appearance** button. That version of the editor supports directional remote navigation and Return/Back to TV home.

## Included

- 32 illustrated theme scenes: space, landscapes, cinema, neon city, stadiums, landmarks and national scenes. Theme cards show miniature TV compositions. The artwork and monogram shields are original NetFelix illustrations; Morph screenshots/player photos are not used as wallpapers.
- An expandable 1920×1080 preview renders the actual TV dashboard with unsaved settings. Its SVG icons, background artwork, heading, favorites and styling use the same code as the real TV.
- Theme-default, Glass, Colorful and Outline icon treatments, shared by the TV, preview and icon samples.
- Shared theme, custom accent, title/subtitle, text size, blur, glow, motion, clock format, home prayer/weather visibility.
- JPEG/PNG/WebP wallpaper uploads up to 4 MB. Uploads apply immediately; other edits use Apply. **Use theme background** removes the active photo on the next Apply.
- Favorite app selection and order in the TV dock.
- Up to six family profiles, with separate appearance and favorites. Selecting a profile also selects it on the TV. These are GUI profiles, not Jellyfin accounts or parental enforcement.
- Persistent settings and conflict detection: if another client changes settings while you have an unapplied draft, reload before applying.
- A scene layout integrated into the existing dashboard, keeping its matches, library, search/request, radio and prayer integrations. The hardcoded recently-used row is hidden until it can be backed by real usage data.

## Implementation

`script` paths below are relative to the repository root:

- `scripts/tv_settings.py`: JSON API, validation, atomic writes, profile separation and wallpaper storage.
- `scripts/tv_ui/`: scene registry/artwork, shared SVG icon renderer and treatments, TV styles/controller and customization page.
- `scripts/generate_tv_scenes.py`: reproducibly generates the 32 local SVG illustrations and their registry entries.
- `scripts/ai_media_service.py`: routes to the settings/editor assets and companion download.
- `scripts/tv_dashboard.py`: loads the new scene assets and honors the shared clock preference.
- `watch-remote/phone/`: Android connection screen, WebView editor host and system photo picker. No native JavaScript interface is exposed; top-level navigation stays on the selected server.

Data lives in ignored `config/tv_appearance.json` and `config/tv_wallpapers/`. Existing wallpaper/icon endpoints and media-service configuration are not overwritten. Uploaded photos remain locally stored even after deselection, allowing saved profile references to remain valid.

Wallpaper decoding requires Pillow (`python3 -m pip install -r scripts/requirements-tv-ui.txt`). It is installed on this server. Uploads are decoded before saving; damaged files and images larger than 25 megapixels or 8192 pixels per side are rejected.

The API is part of the existing trusted-home-network service on port 8092. Browser writes require the same origin as the page. There is no new public/internet hosting or account service.

### API

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/tv/appearance` | Active settings, revision, profile summaries, themes and supported apps. |
| POST | `/api/tv/appearance` | `{ "patch": {...}, "profile": "family", "revision": 0 }`; optional revision prevents stale writes. |
| POST | `/api/tv/appearance/profile` | `{ "action": "create", "name": "Kids" }` or `{ "action": "select", "profile": "family" }`. |
| POST | `/api/tv/appearance/upload` | Base64 `image`, profile ID and optional revision; stores a content-addressed local image and selects it. |
| GET | `/api/tv/appearance/wallpaper/{sha256}` | Uploaded image data, with strict digest matching. |
| GET | `/tv-preview` | Actual TV template in a passive, sample-data preview. Receives draft settings from its same-origin parent; does not save or poll household preferences. |
| GET | `/tv-customize` | Shared browser/Android editor; `?tv=1` enables TV arrow/Back handling. |
| GET | `/downloads/netfelix-companion.apk` | Locally built debug APK; 404 if it has not been built on this server. |

## Build and verification

```sh
./watch-remote/build-phone.sh
python3 -m unittest discover -s tests -v
python3 tests/check_tv_appearance_browser.py
python3 -m unittest discover -s tests -p test_tv_appearance_browser.py -v
```

The build uses the locally configured JDK/Android SDK and runs `:phone:assembleDebug :phone:lintDebug`. APK output: `watch-remote/phone/build/outputs/apk/debug/phone-debug.apk`. It is a development APK signed with the local Android debug key, not a store release. The watch build/install flow is unchanged.

The browser check needs Playwright and Chromium; it runs against an isolated temporary settings store and does not change household preferences. It checks 720p/1080p TV layouts, a 390px phone viewport, all theme choices, cross-page synchronization, persistence, profile switching, upload/reset, app ordering, editable search/Back and safe title rendering.

Physical Android installation/photo-picker behavior and Samsung engine/remote behavior still require device testing. No Android device was connected during this build. This version does not yet include Morph's full IPTV library, fitness, native HDMI/USB browser, logo placement, or photo slideshows; those remain subsequent stages of the recreation plan.

Detailed current coverage, bugs fixed, and device-test limits are recorded in [the test report](appearance-test-report.md).

## Preview and icon update

Theme selection now updates a scaled instance of the TV dashboard instead of a simplified color card. **Expand preview** opens a larger view; Escape closes it without discarding edits. The larger dock-icon samples make the selected icon treatment readable on a phone. Previewing never saves settings; Apply remains the persistence boundary. If a personal photo is replacing the theme illustration, an inline **Use theme artwork** action clears that draft override.

The scene registry includes `artwork` and theme-default `iconStyle`; profiles persist `iconStyle` as `theme`, `glass`, `solid`, or `outline`. Existing saved profiles inherit `theme` without a destructive migration.

## Companion 1.1

The Android app now searches for NetFelix on the local network on first launch, remembers the selected server, and reconnects on later launches. **Find NetFelix on Wi-Fi** retries discovery; manual address entry remains available. The server listens for versioned nonce-bound UDP queries on **8093** and replies with its HTTP port **8092**. The phone verifies the HTTP service identity before offering a result. Wi-Fi client isolation or blocked UDP can prevent discovery even when manual connections work.

The shared editor includes section navigation for themes, remote, designs and schedules:

- Full scene thumbnails and an expandable preview render the same TV HTML, SVG icons and CSS as the dashboard.
- **Try on TV** displays a draft for 30 seconds, with a visible TV badge. **Keep** saves it as the profile's base appearance; **Restore** ends it immediately. Expiry or server restart restores the current saved/scheduled appearance. Regular Apply and profile changes also end a trial. An active schedule continues to take priority over the base appearance after a trial.
- Tile size can be small, normal or large. The side menu can be left, right or hidden. These settings also appear in preview, profiles and presets.
- Save up to 30 named presets; duplicate, apply, delete, export or import them. JSON exports include the wallpaper bytes, so photo designs can be imported on another NetFelix server. Imports validate settings, photo format, dimensions and SHA-256 correspondence. Exports containing personal photos should be handled accordingly.
- Add up to 20 schedule rules from saved presets. Choose weekdays, a timezone, start/end times, and optional date ranges for seasonal or single-day themes. For overnight windows, the weekday and date refer to the evening on which the window starts. Last matching rule wins. Outside scheduled windows the base appearance returns. Rules belong to their creating profile; another profile's rules do not apply. Remove rules before deleting their preset.
- The remote provides navigation, Back, Home, playback, volume and mute. Choose **NetFelix Home** for direct dashboard controls or **Samsung TV / other apps** for native Samsung keys. Volume/mute always use Samsung keys. The direct dashboard channel only accepts commands while a dashboard has polled within five seconds; commands expire after five seconds and are never replayed into a new dashboard session.
- The phone keyboard fills NetFelix's search field without submitting a media request. Pressing OK/Enter to submit is a separate action. Samsung native text uses the focused native text field and is not a universal keyboard for app-drawn Netflix/YouTube character grids. Key/text delivery to physical hardware remains a device-specific verification requirement.
- Connection status distinguishes the server, dashboard heartbeat, Samsung reachability and cached pairing state. Pair Samsung TV opens the existing pairing screen.

Android exports use the system document saver and imports/photos use the system document picker. No native JavaScript bridge or broad storage permission is used. Android 8+ is supported; the application is still a debug-signed local build.

### Additional API

All appearance management writes use the current saved `revision`, returning 409 on stale writes. They share the existing same-origin browser write checks.

| Route | Use |
|---|---|
| `POST /api/tv/appearance/trial` | `start` with draft `settings`, then `keep` or `restore` with the returned trial `id` |
| `POST /api/tv/appearance/presets` | `save`, `duplicate`, `restore`, `delete`, `import` |
| `GET /api/tv/appearance/export/{id}` | Download a portable design JSON, including wallpaper if present |
| `POST /api/tv/appearance/schedules` | `save` or `delete` schedule rule |
| `GET /api/tv/companion/info` | Service identity and dashboard heartbeat |
| `POST /api/tv/companion/control` | `target`: `dashboard` / `samsung`; `kind`: `key` / `text` |
| `GET /api/tv/companion/commands?after={sequence}&epoch={epoch}` | Transient dashboard command polling |

Appearance snapshots retain `settings` as the saved base and expose `displaySettings`, `displayRevision`, `trial`, `activeSchedule`, `presets`, and `schedules`. The TV compares `displayRevision`, so time-window boundaries and trial expiry update the display without preference writes. The editor previews its draft rather than the effective scheduled appearance.

Samsung native text packet semantics were checked against the maintained [`samsung-tv-ws-api` implementation](https://github.com/xchwarze/samsung-tv-ws-api/blob/master/samsungtvws/remote.py). NetFelix implements its own small UTF-8/base64 command and intentionally avoids retrying ambiguous text writes. Sending the packet is not proof that a particular app accepted the text.


## Device-tested update 1.1.1

Installed through wireless debugging on Android SDK 37. Rotation now preserves the WebView, unsaved drafts and file-picker callbacks. This follows Android's [WebView state management guidance](https://developer.android.com/develop/adaptive-apps/cookbook/webview-state). The actual Samsung Tizen 6 browser also receives compatible heading/hero CSS fallbacks; modern `clamp()` and `max()` declarations are restricted to feature queries.

All 32 scenes, native Android discovery and document dialogs, phone/TV controls, native text, media playback, scheduling, network recovery and cleanup are recorded in [the completion audit](companion-enhancement-plan.md). APK backup: `/home/dell/Downloads/NetFelix-Companion-1.1.1.apk`; the normal server download route serves this latest build.
