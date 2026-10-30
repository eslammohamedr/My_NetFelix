# NetFelix Watch Remote — v0.14

Standalone Wear OS remote for the existing Samsung TV server. Default controls use direction changes with a saved starting direction and personalized thresholds. Raw training examples are not stored. The watch needs Wi-Fi access to the server and the TV must already be paired with the server.

## Use

1. Open NetFelix Remote and enable **Detect movements**.
2. Tap **Calibrate position & movements**. Complete four prompted steps: rest/start direction, hand up, hand down, and a single rightward movement. Wait through each 2-second countdown, then move during the 2.5-second capture window. Hold the endpoint until that step is saved. Rest must be still; weak or unclear gestures ask for a retry.
3. Hold still briefly until the live reading says Ready.
4. Move your whole hand strongly **up** for volume up, **down** for volume down, or **right once** for play/pause.
5. First check the detected action with **Control TV OFF**. Enable Control TV when the actions match your movements. Pause between commands.

The app transforms linear acceleration with the watch rotation vector. Vertical direction follows gravity; horizontal direction follows the reference position. Rightward detection requires sustained positive acceleration and estimated positive horizontal velocity. Leftward strokes disarm detection until a pause, preventing their braking phase from being mistaken for a rightward command. Short spikes, diagonal movement, stale orientation readings, leftward strokes, and repeated commands during cooldown are rejected. Linear acceleration is an estimate, not exact hand position or reliable fist recognition. Physical false-positive and direction testing is still needed on the actual wrist. Fixed thresholds may need tuning.

Use **Show saved values** to inspect the thresholds (m/s²), rightward-speed estimate (m/s), rest noise, and saved horizontal direction. Values are derived from sustained filtered peaks, with noise floors. No actual hand height is measured. The completed profile persists in `direction-profile` preferences and loads automatically; recalibrate if you change wrist, posture, or body direction. Cancelling or leaving during calibration keeps the previous complete profile, if any. TV output remains off during calibration and after reopening.

Detection is active only while the app is open and keeps the display on. Leaving the screen disables detection and TV output. Samsung's built-in Knock knock shortcut should be disabled if it interrupts this app. No finger-pose detection is used.

Volume commands are `KEY_VOLUP` / `KEY_VOLDOWN`; play/pause sends `KEY_ENTER` because the user's TV player responds to OK. In TV menus OK selects the focused item. A successful server response confirms transmission, not that playback changed.

## Training data removal

The training workflow and matcher have been removed. DirectionActivity deletes the old private `gesture-training.json` and old axis-calibration preferences when opened. Downloaded recordings, analysis files, and diagnostic screenshots in the local `training-data/` directory were deleted. Server preferences are preserved. No new training recordings are stored.

## Server and build

Default server: `http://192.168.1.15:8092`. Edit/save the server address at the bottom of the screen. The existing `POST /api/tv/send_key` endpoint is reused. HTTP is supported for this trusted LAN service.

On this computer, tools are installed under `~/.local/share/netfelix-tools/`:

```sh
./build-apk.sh
```

This runs synthetic direction/touch checks, compiles, and runs Android lint. Output: `app/build/outputs/apk/debug/app-debug.apk`. JDK 17, SDK platform/build-tools 35, and Gradle 8.11.1 are used.

Install over Wireless debugging:

```sh
adb pair WATCH_IP:PAIRING_PORT
adb connect WATCH_IP:CONNECTION_PORT
adb -s WATCH_IP:CONNECTION_PORT install -r app/build/outputs/apk/debug/app-debug.apk
```

The pairing and connection ports differ. The APK also retains the prior touch activity as an internal secondary screen; it is not the launcher. No server changes are required.

## Calibration sensor-routing fix (v0.14)

The prior activity incorrectly returned before passing acceleration readings into calibration when a capture was active. The sample gate now explicitly accepts active calibration before any saved reference is available and still blocks remote commands during calibration/countdown. Regression checks cover these states. The capture screen reports received sample counts, and Check sensors counts acceleration and orientation callbacks for two seconds with TV output off.

Version 0.14 changes play/pause to a single rightward movement. Existing calibration values are preserved and initially reused as the rightward thresholds. Recalibrating updates the fourth step to one rightward movement; up/down behavior is unchanged.

## Sensitivity and recovery (v0.16)

Gentle movements defaults ON: effective acceleration and speed thresholds use 60% of the saved values, bounded by a noise floor. Turning it off restores the calibrated sensitivity; stored calibration values remain unchanged. A still period of 200 ms rearms the detector after cooldown, and the status explicitly says Hold still briefly to rearm. Detected actions provide system haptic feedback when enabled on the watch. Test volume + bypasses movement detection and directly tests the watch/server/TV path. Gentler settings may increase false positives; test them before enabling TV control.

## Volume steps (v0.17)

Each detected up/down gesture sends ten sequential volume presses, spaced by 100 ms, using the existing server endpoint. Play/pause remains one OK/Enter press. Test volume + remains a one-press connection check. Only one batch runs at a time; other gestures are ignored while busy. A failed response or transport exception stops the batch and shows how many presses were confirmed sent, without retrying presses that may already have reached the TV. Ten presses may be limited by the TV's minimum/maximum volume and do not confirm a numeric ten-point change on every TV/output device.

## Android phone companion

The separate `:phone` module builds **NetFelix Companion**, a phone app for TV appearance, wallpapers, favorite order and family profiles. It does not replace the Wear OS app. Build with `./build-phone.sh`; see [companion setup and API](../docs/netfelix-companion.md). The default server is the same `http://192.168.1.15:8092`.
