# NetFelix appearance and companion test report

Date: 2026-10-29. Scope: the implemented NetFelix appearance service, TV GUI integration, shared phone editor, Android APK build and existing streaming test suite. This does not certify the unimplemented features in the Morph research inventory.

## Automated results

| Suite | Result | Evidence |
| --- | --- | --- |
| Appearance HTTP/storage | 17 tests passed | [Run log](test-results/appearance-tests-2026-10-29.txt) |
| Chromium end-to-end UI | 20 tests passed, including all 32 palette choices | [Run log](test-results/appearance-tests-2026-10-29.txt) |
| Samsung connection handling | 4 tests passed using simulated connections | [Run log](test-results/appearance-tests-2026-10-29.txt) |
| Existing streaming/catalog | 35 tests passed | [Run log](test-results/streaming-tests-2026-10-29.txt) |
| Android APK | Build and lint passed; 0 lint errors, 2 compatibility/backup configuration warnings | `./watch-remote/build-phone.sh` |
| APK signature and manifest | Signature verified; phone launcher, Android 8+ minimum, Internet permission | Android SDK `apksigner verify` / `aapt dump badging` |

**Total: 76 automated tests passed.** The 32 palette applications are individual subcases inside the browser suite, not 32 additional tests in that total.

## Covered behavior

- Every palette: preview colors, Apply, TV synchronization and preferences surviving a fresh store read.
- All theme categories: collectively cover exactly 32 distinct theme IDs.
- Custom accent override and restoring a theme's own accent.
- Title/subtitle and Arabic text; smaller/normal/larger preview and TV text.
- Motion, blur, glow, prayer/weather visibility and 12/24-hour clock switches.
- TV layouts at 720p, 1080p and 4K; phone editor widths of 320, 390 and 768 pixels. Long custom text does not overlap the dock.
- Favorite removal, empty dock retaining Appearance access, app reordering and focus preservation.
- Independent profiles, selection and reset isolation; API limit of six profiles and invalid-profile handling.
- JPEG, PNG and WebP uploads, actual image decode, exact downloaded bytes/MIME, damaged/oversized image rejection, dimension limits and removing a wallpaper.
- Request validation, malformed JSON, size limits, rejected foreign origins, path traversal rejection and missing wallpaper handling.
- Concurrent updates, stale-client rejection, failed atomic writes preserving the saved file, and corrupt-file preservation.
- Offline save recovery, draft retention, slow-request timeout unlocking controls, and clearing an obsolete connection warning after reconnecting.
- TV editor arrows/OK/Back, search typing, prayer dialog dismissal and screensaver wake.
- App-launch request routing and failure feedback; media-request success/failure UI; video modal open/close and radio controls.

App launches and media requests in browser tests are intercepted and simulated. The video modal uses a deliberately unavailable fixture video; radio play/pause is simulated. These verify UI/control behavior without waking the household TV, requesting real downloads, or playing third-party streams.

## Bugs found and fixed

| Problem | Corrected behavior |
| --- | --- |
| TV OK did not toggle settings checkboxes | Enter/OK activates the focused checkbox. |
| Category changes and favorite reordering removed keyboard focus | Focus moves to the corresponding replacement control. |
| Preview heading ignored the chosen text size | Preview title and subtitle now scale with the setting. |
| Truncated image headers could be saved as wallpapers | Pillow verifies and decodes supported image data before saving. |
| Invalid profile upload left an unused image file | Profile existence is checked before storing the photo. |
| Connection warning remained after recovery with unchanged settings | Successful polling clears the stale connection warning. |
| Launch/request failures were silently ignored | Failures are shown; a failed media request keeps the search dialog and title. |
| New toast could be hidden by an old toast timer | Each message resets the dismissal timer. |
| Stalled saves left editor controls disabled indefinitely | Requests have a 12-second deadline; drafts remain available and the editor offers reload. |
| Long custom text overlapped the app dock | Hero height expands with its content and long words wrap. |

## Running service checks

After the regression run, the service was restarted while its queue was idle. Appearance JSON, editor, JavaScript, stylesheet and APK download returned HTTP 200. The API exposes 32 palettes. The APK response bytes match the locally built, signature-verified artifact.

Browser tests used temporary stores and never replaced the household appearance file or uploaded photos. The existing Wear OS app was not modified during this test/fix pass.

## Not verified on hardware

No Android device was connected over ADB, no Android emulator was installed, and the Samsung TV at its configured LAN address was offline/unreachable during the checks. Therefore the following remain unverified:

- APK installation, real Android WebView behavior and the system photo picker on the user's phone.
- Samsung remote behavior on its actual browser engine, native app launches and standby/resume.
- Real Jellyfin/live-stream decoding, audio output, codecs/subtitle tracks and radio station availability.
- Sensor/gesture behavior of the separate Wear OS app.

Browser resolution checks do not prove native 4K video playback or TV-engine compatibility. Physical testing can follow when the phone and TV are available.

## Reproduce

```sh
python3 -m pip install -r scripts/requirements-tv-ui.txt
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s streaming/tests -v
./watch-remote/build-phone.sh
```

The UI suite also requires the Python Playwright package and `/usr/bin/chromium`. It starts its own temporary HTTP server and blocks requests outside that test server. This host had those dependencies installed.

## Full-scene preview and icon follow-up

The subsequent visual update replaces the color-only picker with 32 illustrated scene thumbnails and a scaled instance of the actual TV dashboard. That preview uses sample status data and the same scene CSS and SVG icon renderer as the TV. It is passive: changes to its draft do not save settings or steal editor keyboard focus. Glass, Colorful and Outline icons can be previewed, applied and persisted.

The expanded appearance regression suite passed **45 tests**: [run log](test-results/scene-preview-tests-2026-10-29.txt). Additional computed-style checks confirmed that the three icon treatments are visually distinct and match between preview and TV, along with long-text layout and preview isolation: [targeted run log](test-results/icon-treatment-tests-2026-10-29.txt). These follow-up counts supersede the earlier 41-test appearance/connection run; they are not added to it as new independent coverage.

New coverage checks all 32 artwork files, actual screen previews, styled SVG thumbnails, all icon-style choices, preview text-size parity, expand/Escape behavior, unsaved-preview isolation and matching TV/preview icon SVGs. Older-TV layout fallbacks avoid requiring CSS aspect-ratio for theme thumbnails or enlarged preview sizing. Physical device testing remains subject to the limits described above.

## Companion 1.1 — 2026-10-30

Implemented expiring TV previews, portable presets with photos, weekday/timezone/date-range schedules, tile size and menu position choices, Android LAN discovery, dashboard/Samsung remote controls, phone keyboard, connection status, and Android document export/import.

- Full root suite: **62 tests passed in 225.828 seconds**. Covers existing appearance/server behavior and the new transactions, schedule boundaries, profile isolation, portable photo import/export, command expiry/epochs, remote search/playback, and actual browser rollback after the phone page closes.
- After the final menu and phone layout refinements: **3 focused browser tests passed in 15.775 seconds**, including right-side geometry and navigation and hidden-menu focus exclusion. The menu test adds one unique check beyond the full-suite snapshot above.
- Android 1.1 (versionCode 2), min SDK 26, target SDK 35: assembleDebug and lintDebug succeeded. Zero lint errors; two existing manifest compatibility warnings. Final APK signature verified. Only INTERNET permission is declared.
- Live service restarted while the media queue was idle. LAN health, companion identity, appearance API, APK download and nonce-bound UDP discovery verified. Downloaded APK matches the local install artifact byte-for-byte: 34,076 bytes, SHA-256 `fab7ca402201393c5fcb19bbad84dd763f7685519b6e8e667bcc6f8dc8ab63f0`.
- Evidence and isolated fixture screenshots: `docs/test-results/companion-1.1/`.

An initial overlapping browser run had one typing timeout; that test passed alone and in the subsequent complete run without overlapping browser suites.

Physical completion remains unverified: the Samsung TV at 192.168.1.2 was unreachable and ADB listed no phone. Real Android discovery, picker/saver, installation and lifecycle behavior, actual Samsung key/text delivery, playback and TV rendering require the device checklist. Browser playback tests simulate media behavior and do not prove real stream playback. The full enhancement goal remains active until device checks can be completed.


## Physical-device follow-up — Companion 1.1.1

The prior hardware blocker is resolved. The app was paired and installed over wireless debugging, then updated to 1.1.1 on Android SDK 37. Direct TV inspection confirmed Tizen 6 / Chromium 76. All 32 theme scenes decoded, and the user confirmed the appearance visually. Real phone-to-TV text, Samsung native IME, Back/arrows, audio state readback, H.264/AAC HLS playback, seeking, preview Keep/Restore/expiry, photo import/export and scheduled entry/exit were verified. Actual-device network-loss recovery was tested with WebView offline/online emulation while retaining the wireless-debugging connection.

Physical testing found and fixed an unsupported CSS math rule (16 px heading before; 71.04 px after at 1920 px) and Android rotation losing drafts. Two existing text/layout browser tests and one new legacy fallback test passed after the CSS fix. Build/lint passed with zero errors and two existing manifest warnings. Actual Android rotation, picker cancellation and export after rotation now retain the draft.

The final appearance, active profile, original preset/schedule sets, TV volume/mute and phone screen timeout were restored. Test media did not enter the household library or download queue. Durable evidence is in `docs/test-results/companion-1.1/live-tv/`; see `apk.json` for the exact installed version/build and `cleanup-and-final-state.json` for cleanup. Earlier failed automation attempts were investigated; completed native and rendering checks are recorded in the corresponding final JSON results.
