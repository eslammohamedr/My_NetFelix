# Morph TV investigation for the existing NetFelix GUI

Research completed 2026-10-29 against the public Samsung 0.8.170 package, Samsung 0.8.191 test package, and web assets inside Android TV / phone 0.8.192 test APKs. NetFelix runtime code and the running TV service were not changed during this investigation.

The inspected Samsung test build exposes **32 theme choices in 10 categories**. Its unactivated theme picker and access list agree on **17 free / 15 Plus** themes. The manifest contains **11 downloadable packs**; pack membership is not the same as theme access. In particular, Golden hour is a simple palette but is Plus-gated, and a mixed Europe pack includes both free and Plus themes.

## Research files

- [Feature inventory and NetFelix comparison](feature-matrix.md): discovered feature groups, evidence level, platform limits and current GUI gaps.
- [All themes](themes.md): names, IDs, original access labels and color pairs.
- [Theme metadata](themes.json): all 32 entries, reference art filenames, bundled-art flags and complete pack metadata.
- [Palette overview](theme-palettes.svg): original swatch rendering of all theme color pairs.
- [Observed settings](observed-settings.md): settings captured from the actual locally running UI.
- [Settings key map](settings-keys.json): statically discovered `C.settings` property references by module; not a complete schema because the code also uses dynamic keys and separate storage.
- [Plan to modify the existing GUI](recreation-plan.md): exact entry points, proposed stages and validation requirements.

## What was actually tested

The Samsung test package was served on localhost and opened in Chromium at 1920×1080. Outbound requests were blocked. Home, Apps, Settings and its categories, the theme picker, prayer screen, IPTV shell, radio shell and kids error state were inspected. The initial browser run reported no JavaScript page errors. Browser-visible installed apps are preview data and do not prove what is installed on the user's TV.

Theme locks were observed without changing activation state. The fitness entry opened a Plus prompt; its capabilities were inventoried statically, not exercised by bypassing that prompt. Paid packs were not downloaded or unlocked. Radio displayed no loaded stations in this isolated session, so station playback was not verified; its shipped station JSON and control implementation were inspected separately.

Provider authentication, stream playback, audio output, native TV APIs, QR token validation, phone-to-TV transport and physical remote pairing were not exercised. Android APK web assets were inspected; native DEX code was not decompiled. Source evidence and advertised behavior are distinguished in the feature matrix.

## Reference screens

These are screenshots of the inspected third-party interface, retained as design research, not NetFelix production artwork. Empty/weather/prayer error states are expected with external requests blocked.

| Screen | Screenshot |
| --- | --- |
| Home / Midnight | [Open](screens/home.png) |
| Apps | [Open](screens/apps.png) |
| Theme picker | [Open](screens/themes.png) |
| Appearance settings | [Open](screens/settings-appearance.png) |
| Effects and performance | [Open](screens/settings-performance.png) |
| Home visibility settings | [Open](screens/settings-home.png) |
| Prayer settings | [Open](screens/settings-prayer.png) |
| Clock and weather settings | [Open](screens/settings-time.png) |
| System settings | [Open](screens/settings-system.png) |
| Prayer screen | [Open](screens/prayer.png) |
| IPTV / account selection | [Open](screens/iptv.png) |
| Radio shell | [Open](screens/radio.png) |

![Inspected home screen](screens/home.png)

## Architecture findings

Morph Samsung bundles the UI locally as modular HTML/CSS/JS, using a `ClearTV` namespace, profile-scoped preferences and device adapters. Its media integration uses Samsung APIs where available, separate IPTV/radio interfaces, and shared focus/theme helpers. The modern theme adapter derives readable text/focus colors from identity colors; the recreation should likewise use shared tokens rather than isolated per-card CSS overrides.

The phone APK contains a separate web interface, native bridge calls and bundled installation payloads. It exposes app/theme/profile/remote configuration workflows and DLNA controls, but its web assets alone do not establish the native protocol's implementation. The Android TV package shares many UI modules and adds native capability bridges.

NetFelix already has a TV dashboard, Samsung remote backend, app launching, Jellyfin data, matches, prayer hub, radio toggle and screensaver. Modify those existing components. The principal gaps are persistent theme/settings data, real favorites/recent usage, a consistent screen/focus controller, dedicated library views and capability-aware device integration.

## Platform and version differences

| Item | Finding |
| --- | --- |
| Public catalog | 0.8.170, separate from newer test builds. |
| Samsung 0.8.191 test | 32 themes; audio, CC and stream-info controls in Samsung media code. |
| Android / phone 0.8.192 test | Release page adds QR subscription setup and Portal/MAC workflow. |
| QR setup | Android release describes same-Wi-Fi, five-minute single-use keys; Samsung/LG excluded. |
| Portal | Explicitly rejected by the Samsung adapter in the inspected code. |
| Multi-view | Up to four channels in a native-capability-gated module; not exposed by the inspected Samsung bridge. |
| Audio/subtitles | UI/track availability depends on source and player; Android's Media3 options must not be assumed on Samsung. |
| Prayer | Foreground app behavior; no dependable alert while another app is active or TV is off. |
| Parental timers | Samsung code limits internal IPTV/radio; cannot interrupt external YouTube or Netflix. Saved allowances are not daily budgets. |
| Samsung Home | Site explicitly states Smart Hub Home is not replaced; cold boot is different from remote standby/wake. |
| Radio black screen | UI overlay while audio continues, not physical screen power control. |

## Source provenance

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| Samsung computer ZIP 0.8.170 | `b39ca838d98e49af7e57604e9d2e7f96331eb822e17adcb7bae442ac96878e52` | Matches published checksum. |
| Samsung test WGT 0.8.191 | `88f19f836e485e23e440af28cf26b5af47bec07f80b1dbd4c838f5e29d4bc701` | Locally calculated fingerprint; not independently publisher-verified. |
| Phone test APK 0.8.192 | `4c24be37f7d3b5c5ebb7883447231447370efcf1f615da91955422e100962e92` | Locally calculated fingerprint. |
| Android TV test APK 0.8.192 | `48d9f17ac45f946ba5183d869624cea8612f0920a78d08db2258c2307e6f06c2` | Locally calculated fingerprint. |

Primary sources: [site](https://morphtv.herroshetta.com/), [release catalog](https://morphtv.herroshetta.com/catalog.json), [public checksums](https://morphtv.herroshetta.com/SHA256SUMS.txt), [Samsung computer archive](https://morphtv.herroshetta.com/Morph-TV-Samsung-Computer-0.8.170.zip), [0.8.191 test notes and downloads](https://morphtv.herroshetta.com/test-releases/20261029-mobile-tv-0.8.191/), [0.8.192 test notes and downloads](https://morphtv.herroshetta.com/test-releases/20261029-mobile-tv-0.8.192/).

Raw downloads and extracted third-party scripts remain outside the project in `/tmp/morphtv-inspect` and may disappear on reboot. The durable research records here contain metadata, analysis, palette swatches and reference screenshots. They are not a redistribution of the original app or a claim to have verified every native or server-side feature.
