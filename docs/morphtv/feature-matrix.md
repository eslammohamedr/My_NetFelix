# Feature inventory and NetFelix comparison

Evidence: Samsung 0.8.191 package unless explicitly marked phone/Android 0.8.192. **Observed** means the UI was opened in local Chromium. **Code** means static implementation evidence, not a successful hardware/provider test. **Advertised** means release-page claims only. No external API requests, account connections, paid activation, or TV installation were performed during browser inspection.

NetFelix comparison is against the existing `scripts/tv_dashboard.py`, `scripts/ai_media_service.py`, Tizen launcher, and Samsung remote service. “Missing” means no corresponding implementation found in those inspected entry points; it is not a claim about every service in the repository.

| Area | Feature / behavior | Evidence | Current NetFelix / recreation work |
| --- | --- | --- | --- |
| Shell | Full-screen wallpaper with dark scrims and integrated hero | Observed: home; `ui/modern-shell.css` | Has wallpaper and card hero; change to integrated full-screen composition. |
| Shell | Centered navigation, brand, status, clock and search | Observed: home | Header exists; restyle and reduce duplication. |
| Shell | Left shortcut sidebar and bottom glass app dock | Observed: home; `dock.js` | Both exist; change geometry, icons and density. |
| Shell | Glass reflections, focus enlargement, themed outlines | Code: `dock.css`, `app-polish.js` | Has glow/focus; introduce effect controls and consistent tokens. |
| Shell | Optional recent-app rail, up to five remembered apps | Code: `home-refinements.js` | Existing recent cards are hardcoded; persist actual usage. |
| Shell | Optional HDMI shortcut rail and last-used HDMI tile | Code: `home-refinements.js` | Existing HDMI tile is a toast; needs functional device adapter. |
| Shell | Optional fitness shortcut | Observed: Home settings | Missing; add only when fitness implementation exists. |
| Shell | Background slides and manual slide selection | Code: `app.js`, `home-refinements.js` | Has idle photo screensaver; distinct from home slideshow. |
| Apps | Installed-app discovery, refresh, count and search | Observed: Apps; `catalog.js` | Static shortcut list; integrate Samsung app discovery. |
| Apps | Launch native Samsung apps | Code: `catalog.js`, manifest privileges | Existing backend launches apps; retain it. |
| Apps | Pin/unpin favorites | Observed controls; `app.js` | Missing persistent favorite editor. |
| Apps | Remote reorder mode and saved app order | Code: `reorder.js` | Missing. |
| Apps | App context/actions and store launch | Code: `app-actions.js` | Some launch shortcuts exist; add contextual actions. |
| Navigation | Scoped focus for view/dialog/player | Code: `focus.js` | Existing spatial engine and modal filtering; preserve fixes and generalize. |
| Navigation | Directional navigation, scroll reveal, long-press behavior | Code: `focus.js`, dock and app modules | Existing arrows/OK/Back; extend without breaking input editing. |
| Navigation | Back restores prior focus | Code: focus/view/dialog modules | Existing dialog return handling; expand to screen stack. |
| Navigation | Phone text insertion into active editable input | Code: `remote.js` | Existing phone Samsung remote; GUI text bridge not found. |
| Themes | 32 theme choices and 10 category tabs | Observed picker; `app.js` | Single visual design; build registry and picker. |
| Themes | Theme identities affect palette, art, crest and hero copy | Code: `club-themes.js`, `theme-locale.js` | Add schema and original/licensed artwork. |
| Themes | 11 downloadable packs, install status and removal | Code: manifest, `theme-packs.js`, `packs-tv.js` | Missing; a simpler local asset registry may suit NetFelix. |
| Themes | Hash/version metadata and cached pack lifecycle | Code: pack manifest/loader | Missing. |
| Themes | Theme preview before selection | Code: `theme-preview.js` | Missing. |
| Appearance | Separate Arabic and English text sizes: smaller/current/larger | Observed Settings; `text-size.js` | Fixed text sizes; add language-aware scaling. |
| Appearance | Custom accent, highlight, text, card, tint and background colors | Code: `app.js`, `ui/theme-adapter.js`; phone editor | Missing configurable settings. |
| Appearance | Custom title, subtitle, logo and hero art | Code: app configuration and phone picker | Has household wording and custom wallpaper/icon endpoints; add editor/storage. |
| Appearance | Art/title/subtitle/logo scaling and positioning | Code: configuration application; phone editor | Missing configurable layout. |
| Appearance | Glass opacity and card width | Code: `app.js` | Fixed values. |
| Appearance | Photo background slideshow and interval | Code: `app.js`; original app Plus gate | Idle screensaver exists; add home-specific controls. |
| Performance | Light, Balanced and Full effects presets | Observed Settings | Missing. These are interface effects, not media quality. |
| Performance | Separate blur, glow/shadow and animation toggles | Observed Settings | Reduced-motion CSS exists; add persistent controls. |
| Compatibility | Legacy Tizen layout fallbacks and fit/scaling helpers | Code: `tv-compat.js`, `screen-fit.js` | Responsive styles exist; test native TV engine and overscan. |
| Weather | Automatic approximate location, city search, off | Observed Settings; `weather.js` | Fixed Cairo location. |
| Weather | Celsius/Fahrenheit and forecast detail | Code: `weather.js`, `app.js` | Cairo summary only. |
| Weather | Three-day forecast with cached/error states | Code: `app.js` | Missing detailed forecast and honest unavailable state. |
| Clock | 12/24-hour format and visibility | Observed Settings; configuration code | Clock exists; add preferences. |
| Prayer | Dedicated clock/weather/countdown/timetable screen | Observed prayer screen | Existing prayer hub; restyle and improve state handling. |
| Prayer | City selection and four calculation methods | Observed controls; `prayer.js` | Fixed Cairo / Egyptian method. |
| Prayer | Standard/Hanafi Asr calculation | Observed controls | Missing. |
| Prayer | Egypt/Makkah Adhan, preview/stop, volume and automatic switch | Observed controls; playback code | Dashboard currently shows notification at countdown completion; do not treat as a complete Adhan engine. |
| Prayer | Pause internal playback during Adhan, restore afterward | Code: `prayer.js` | Missing tested integration. |
| Prayer | Optional ten-minute prayer break within Morph | Observed settings; `prayer.js` | Missing; cannot enforce outside the app. |
| Prayer | Morning/evening/after-prayer/between-prayer/general duas | Code: `prayer-duas.js`, data | Existing static dhikr; add scheduled categories. |
| Prayer | Text rotation 30/60/120 seconds | Code: `prayer-duas.js` | Missing. |
| Prayer | After-prayer reminder delay 10/15/20/30 minutes | Code: `prayer-duas.js` | Missing; delay is from Adhan, not detected prayer completion. |
| Profiles | Up to six named viewers | Code: `core.js`; Family UI | Missing dashboard profiles. |
| Profiles | Profile-specific settings, pins and recent items | Code: `core.js` scoped storage | Missing; coordinate with Jellyfin users rather than confuse the two. |
| Parental | Create/change/confirm 4–6 digit PIN and app locks | Code: `samsung-locks.js` | No equivalent dashboard control found. |
| Parental | Failed-attempt delay and saved allowances | Code: `samsung-locks.js` | Missing; original allowances do not automatically renew daily. |
| Parental | Internal IPTV/radio time budget, custom 1–1440 minutes | Code: `samsung-locks.js` | Missing; cannot interrupt external YouTube/Netflix. |
| IPTV | Separate home with Live, Movies, Series and continue tiles | Observed shell; `iptv/` | NetFelix uses Jellyfin and one live stream; build views around existing sources. |
| IPTV | Xtream and M3U subscription handling on Samsung | Code: `samsung-media.js` | Needs dedicated provider/source model. |
| IPTV | Multiple saved accounts, active-source switch and account details | Code: Samsung media + IPTV account UI | Missing unified account UI. |
| IPTV | Subscription expiry/status where provider supplies it | Code: `account-details.js`, Samsung adapter | Missing. |
| IPTV | Free Arabic-language, Arab-region and world-news playlists | Observed settings; `m3u-source.js` | Existing local playlist; optional source browser could be added. |
| IPTV | Preserve personal subscription when using free channels | Code: Samsung media/source selection | Missing. |
| IPTV | Categories, unified search, sort and comfortable/compact density | Code: `iptv/app.js` | Needs library browsing UI; do not replace Jellyfin backend. |
| IPTV | Favorites across live/VOD/series | Code: IPTV app | Missing dashboard-level favorites. |
| IPTV | Continue-watching history and last live/movie/series tiles | Observed shell; code | Existing Jellyfin resume cards; wire actual item IDs and episode links. |
| IPTV | Series details, seasons, episodes, poster/rating metadata | Code: IPTV app and Samsung media | Use Jellyfin metadata where available. |
| IPTV | Provider EPG panel and current-program indications | Code: `epg()` and IPTV EPG UI | Match cards are not an EPG; add separately if source supports it. |
| IPTV | Metadata/page/catalog caching and refresh states | Code: IPTV media-performance/cache helpers | Existing server caches; add client library cache as needed. |
| Playback | Samsung AVPlay-backed media player | Code: `samsung-media.js` | Existing HTML video player; needs privileged local bridge for AVPlay. |
| Playback | Play/pause, seek ±10 seconds, held seek and position display | Code: Samsung media | Native HTML controls exist; add remote-friendly overlay. |
| Playback | Previous/next live channel and episode | Code: Samsung media | Missing. |
| Playback | Resume/start over and fit/fill display mode | Code: Samsung media | Partial via Jellyfin; integrate for dashboard player. |
| Playback | 1×/2×/4× VOD speed controls | Code: Samsung media; capability-dependent | Missing local controls; verify player support. |
| Playback | Audio-track, CC and stream-info dialogs | Code: Samsung 0.8.191; release notes | Missing local player dialogs; expose supported tracks only. |
| Playback | Preferred audio/subtitle language, external subtitle formats and styling | Android 0.8.191 advertised; native Media3 not runtime-tested | Existing Watch Now subtitle features should be reused; Samsung parity requires verification. |
| Playback | Quality selection from source-provided variants | Android 0.8.191 advertised | Depends on player/source; not a universal Samsung feature. |
| Radio | All/Quran/FM/Favorites/Sports views and search | Observed shell; `radio/app.js` | One radio toggle; build station library. |
| Radio | Favorite stations with held OK, play/pause/stop/reconnect | Code: radio app | Existing start/stop only. |
| Radio | Black-screen overlay while audio continues | Observed button; `radio/screen-off.js` | Missing; this is a UI cover, not physical panel power-off. |
| Radio | Playback status survives return to home | Code: `radio-background.js`, Samsung media | Existing audio bar; generalize. |
| Kids | Kidsy live-channel view, retry, mute, pause and fullscreen | Observed shell/error; `kids.js` | Existing kids media is in Jellyfin; add a shortcut/view if wanted. |
| Fitness | Exercise categories, program/detail/browser and custom builder | Code: fitness modules; entry is Plus-gated | No equivalent found; optional later module. |
| Fitness | 63 exercise definitions and 15 program definitions | Counted shipped data calls, not exercise quality validation | Inventory only; independently write content if recreating. |
| Fitness | Work/rest timer, pause/resume, exit confirmation and session completion | Code: fitness engine/UI | Missing. |
| Fitness | Progress history, weekly view, calorie estimate and audio settings | Code: fitness UI/store/audio | Missing; estimates are not measured health data. |
| Device | HDMI/live-TV discovery, connected state, rename and diagnostics | Code: inputs/adapter/input-names | Needs local Tizen bridge and physical-TV validation. |
| Device | Broadcast current channel/program information | Code: inputs | Conditional on TV broadcast APIs, not streaming provider metadata. |
| Device | USB drive/folder browser and media opening | Code: usb/usb-media | Missing TV-side browser; manifest/filesystem access required. |
| Device | Wi-Fi/device settings and startup help | Observed Settings; device modules | Existing remote backend; add platform-appropriate controls. |
| Phone | Discover/connect TV, installation/update flows and app list/pins | Phone 0.8.192 asset code | Existing phone remote; preserve and extend it. |
| Phone | Custom image picker, appearance editor and layout reset | Phone asset code | Missing customization editor. |
| Phone | Internal vs Samsung network remote, keys and text | Phone asset code; `remote.js` | Existing Samsung remote service already useful; add internal UI commands. |
| Phone | Cast/screen-sharing entry points and DLNA URL playback/control | Phone asset code, native handlers not decompiled | Not verified; do not claim browser asset code proves receiver support. |
| Android only | Portal + MAC account input | Samsung adapter explicitly rejects Portal; Android release advertises it | Optional independent provider adapter, outside initial Samsung UI work. |
| Android only | QR subscription setup, same Wi-Fi, five-minute single-use key | Android 0.8.192 release notes + `subscription-setup.html` POST form | Needs a NetFelix pairing backend; original native validation not inspected. |
| Android only | Multi-view up to four channels with audio/layout selection | Capability-gated `iptv/multiview.js`; release notes | Samsung does not expose this capability in the inspected adapter. |
| Product | App update checks, support/about/contact and language picker | Observed/code | NetFelix needs its own version/status/help, not Morph activation or donation flows. |
| Language | Arabic, English, French, Chinese and Japanese resources | Code: locale modules | Existing mixed English/Arabic; introduce consistent localization/RTL. |

## Scope exclusions and unresolved behavior

Paid theme artwork was not downloaded through activation and paid feature gates were not modified. Native Android DEX code, private servers, physical TV behavior, provider logins and successful remote pairing were not tested. The phone APK's web assets were inspected; this is not complete Android decompilation. The matrix describes all feature groups discovered in the inspected releases, not undiscovered future/server-side functionality.
