# Companion 1.1 device verification

Completed on the actual Samsung TV and Android phone on 2026-10-30; see [the completion audit](companion-enhancement-plan.md) and `test-results/companion-1.1/live-tv/`. The checklist remains useful for future releases. Connection-loss validation used the real WebView network stack with CDP offline/online emulation, retaining Wi-Fi for wireless debugging.

1. Install the new 1.1 APK over the existing app. Verify existing server preferences remain. On a first install, verify Wi-Fi discovery finds the correct server; test retry and manual entry if discovery is blocked.
2. Open NetFelix Home on the Samsung TV. Confirm the app distinguishes server connected, dashboard open, and Samsung online. Test pairing only if requested by the TV.
3. Preview contrasting scenes and all icon styles. Confirm photos, small/large tiles, right/hidden menus and long Arabic/English titles look correct at the TV's real resolution.
4. Start a TV preview and close/disconnect the phone. Verify the previous saved/scheduled appearance returns after 30 seconds. Repeat and Keep; repeat and Restore.
5. Test directional controls, OK, Back and Home. Type Arabic and English titles using NetFelix Home mode, confirm they appear on TV, then clear or close without requesting unwanted media.
6. Use an existing playable stream to check Play/Pause/Stop and seeking where the source supports it. Verify volume/mute in Samsung mode. Test Samsung keyboard only with a native TV input focused; custom character-grid keyboards may not support native text.
7. Use the Android document picker to upload a photo. Export a saved photo design with the Android document saver, import it and apply it. Verify cancellation/error recovery and app rotation around the saver/picker.
8. Create a short schedule window in the correct timezone, verify entry and exit on the real TV, then remove the test rule. Confirm another profile does not inherit it.
9. Disconnect/reconnect Wi-Fi. Verify connection status, retained unsaved draft, automatic reconnection, and no stale navigation/text commands replay after returning.

Remove test schedules/presets and restore household preferences after device checks. Do not claim universal Samsung native text compatibility from browser tests.
