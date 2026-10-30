# Companion enhancements: completion audit

Completed and verified on 2026-10-30. Companion **1.1.1** is installed on the user's Android phone through wireless debugging. The Samsung UA50AU7000UXEG was tested directly through its Tizen 6 / Chromium 76 inspector.

| Original requirement | Implementation and authoritative evidence |
|---|---|
| Full theme and icon previews | Shared TV renderer and scene gallery; all 32 scenes decoded on the real TV, with actual text/icon/tile/menu attributes and layout checked. `test-results/companion-1.1/live-tv/theme-matrix.json`. User confirmed background, title and icons look correct. |
| Temporary TV preview, Keep, automatic restore | Real Android-to-TV Try/Restore and 30-second rollback while Android was backgrounded; Keep saved the theme and a preset applied the photo on TV. `phone-tv-controls.json`, `keep-and-preset.json`. |
| Automatic LAN discovery | Nonce-bound UDP discovery and HTTP identity verification; Android's native discovery found the actual server over Wi-Fi and reconnected. `android-discovery.json`. Existing server preference survived the upgrade. |
| Remote navigation, playback and phone keyboard | Actual dashboard and Samsung Back, native arrow events, direct Arabic/English search, native Samsung Arabic/English IME, volume/mute with UPnP readback and restoration. Actual H.264/AAC HLS decoding, Play/Pause/Stop/seeking/Home. `phone-tv-controls.json`, `native-ime.json`, `native-audio.json`, `media-playback.json`. |
| Backgrounds, icon styles, tile sizes, menu position and favorites | All scenes exercised on TV while cycling three icon styles, text sizes, tile sizes and menu positions; native Android photo picker uploaded the fixture, and real TV applied it. Existing favorites ordering/visibility browser and API coverage retained. |
| Schedules | Real TV entered and exited a one-minute scheduled window, restored the original base appearance, and the temporary rule was removed. `schedule-transition.json`. Unit tests cover weekday, date, timezone, overnight and profile boundaries. |
| Saved presets | Save/duplicate/import/export/apply/delete covered by store/API/browser checks; native Android document saver exported the exact photo bytes, native import retained them, and the preset applied on the actual TV. `android-export.json`, `android-import.json`, `keep-and-preset.json`, `saver-rotation.json`. |
| Connection status and recovery | Actual app reported server/dashboard/Samsung reachability and pairing. Network loss/recovery was induced in the real Android WebView through CDP; draft retained and failed text command not replayed. Wi-Fi radio was deliberately left connected to retain wireless debugging. `network-recovery.json`. |

Two physical-device issues were fixed:

1. Chromium 76 rejects `clamp()`/`max()` in the previous heading rule, which resolved to 16 px. Legacy declarations now work independently of guarded modern CSS. TV verified normal title 71.04 px, small 63.936 px and large 81.696 px. Modern and legacy fallback regression checks pass.
2. Rotating Android previously recreated the WebView and lost its draft. The activity now handles size/orientation/keyboard configuration changes and invalidates the WebView. Actual before/after probes show draft loss before, preservation after, with the page retained. Picker cancellation and native export after rotation also preserve the draft.

Final cleanup checked the original saved appearance, profile, preset and schedule sets. Generated device files and unreferenced test wallpaper were removed; TV volume/mute and phone screen timeout were restored. `cleanup-and-final-state.json` records the final state. Temporary fixture HTTP servers and SDB forwarding were closed.

Validation scope: playback used a locally generated, silent test pattern, not household downloads. Seeking lands near stream keyframes. Native Samsung typing was verified in the NetFelix HTML input with native IME support; this does not promise support for third-party apps' custom character grids. Network recovery used actual-device WebView offline/online emulation, not a Wi-Fi radio toggle.
