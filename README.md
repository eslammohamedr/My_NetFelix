# My NetFelix 🎬🍿

An automated, self-hosted streaming and media management stack tailored for local network playback with Arabic subtitle support.

---

## Stack Components

| Service | Local URL | Description |
| :--- | :--- | :--- |
| **Homepage** | [http://192.168.1.15:3000](http://192.168.1.15:3000) | Single dashboard linking all services |
| **NetFelix Dashboard** | [http://192.168.1.15:8090](http://192.168.1.15:8090) | Combined links for search, playback, and management |
| **Watch Now** | [http://192.168.1.15:8090/downloads](http://192.168.1.15:8090/downloads) | Play videos while qBittorrent downloads them |
| **Jellyseerr** | [http://192.168.1.15:5055](http://192.168.1.15:5055) | Search & request movies and TV series |
| **Jellyfin** | [http://192.168.1.15:8096](http://192.168.1.15:8096) | Media server & video player |
| **Radarr** | [http://192.168.1.15:7878](http://192.168.1.15:7878) | Movie management & quality automation |
| **Sonarr** | [http://192.168.1.15:8989](http://192.168.1.15:8989) | TV series management & episode tracking |
| **Prowlarr** | [http://192.168.1.15:9696](http://192.168.1.15:9696) | Torrent indexer manager & sync agent |
| **qBittorrent** | [http://192.168.1.15:8080](http://192.168.1.15:8080) | Torrent download client |
| **Bazarr** | [http://192.168.1.15:6767](http://192.168.1.15:6767) | Automatic Arabic subtitle search & downloader |

---

## Architecture & Data Flow

```mermaid
flowchart TD
    User([User]) -->|1. Request Movie/Show| Seerr[Jellyseerr :5055]
    User -->|Watch Stream| Jellyfin[Jellyfin :8096]
    
    Seerr -->|Forward Request| Radarr[Radarr :7878 / Sonarr :8989]
    Prowlarr[Prowlarr :9696] -->|Sync Indexers| Radarr
    
    Radarr -->|Send Download Task| QBit[qBittorrent :8080]
    QBit -->|Save Torrent to /data/torrents| Disk[(Data Drive: 1TB)]
    
    Radarr -->|Hardlink into /data/media| Disk
    Bazarr[Bazarr :6767] -->|Fetch Arabic .srt| Disk
    Disk -->|Stream Media & Subtitles| Jellyfin
```

---

## Hardware Optimization (Laptop Profile)

- **CPU/GPU**: Intel Core i7-4500U with Haswell HD 4400 Graphics.
- **Hardware Acceleration**: Jellyfin is configured for Intel VA-API (`/dev/dri/renderD128`), and the container has access to the render device.
- **Transcoding Note**: Haswell hardware acceleration handles **H.264 up to 1080p**. It does *not* support hardware decoding for HEVC (H.265) or AV1. To prevent high CPU loads, prioritize **1080p H.264** in Radarr/Sonarr profiles for smooth Direct Play.
- **Storage Strategy**:
  - **Fast Configs & SQLite Databases** reside on internal SSD (`./config`).
  - **Bulk Media & Torrents** reside on external Data drive (`/media/dell/Data/netfelix_data`).
  - Single-mount layout (`/data`) enables instant zero-copy **hardlinks** between downloads and media libraries.

---

## Quick Start Guide

### Step 1: Install Docker & Docker Compose
Run the setup script (requires sudo password):
```bash
./setup_docker.sh
```

### Step 2: Start the Stack
On a fresh clone, create your local environment file and adjust its paths:
```bash
cp .env.example .env
```
Live service configuration, databases, credentials, and downloaded media are excluded from Git. Configure services using the walkthrough below on a fresh installation.

```bash
./netfelix.sh start
```

### Step 3: Useful Commands
- Check status: `./netfelix.sh status`
- View logs: `./netfelix.sh logs [service_name]` (e.g., `./netfelix.sh logs radarr`)
- Restart: `./netfelix.sh restart`
- Stop: `./netfelix.sh stop`
- Update containers: `./netfelix.sh update`
- Check all local service endpoints: `./netfelix.sh health`
- Back up service configuration and databases: `./netfelix.sh backup`
- Review old completed torrent jobs: `./netfelix.sh cleanup`; remove jobs but keep files with `./netfelix.sh cleanup --apply`

---

## Initial Service Setup Walkthrough

### 1. qBittorrent (`http://192.168.1.15:8080`)
- Pre-configured to allow local network login without credentials.
- Go to **Tools** > **Options** > **Downloads**:
  - Default Save Path: `/data/torrents/`
  - Keep incomplete torrents in: `/data/torrents/incomplete/`
- Go to **Speed**:
  - Under your laptop connection, limit global downloads to 1 or 2 at a time.

### 2. Prowlarr (`http://192.168.1.15:9696`)
- Go to **Indexers** > **Add Indexer**:
  - Add public sources (e.g., 1337x, EZTV, YTS, TorrentGalaxy).
- Go to **Settings** > **Apps** > **+**:
  - Add **Radarr**:
    - Prowlarr Server: `http://prowlarr:9696`
    - Radarr Server: `http://radarr:7878`
    - API Key: (Copy from Radarr > Settings > General > API Key)
  - Add **Sonarr**:
    - Sonarr Server: `http://sonarr:8989`
    - API Key: (Copy from Sonarr > Settings > General > API Key)
- Click **Sync App Indexers** to push indexers into Radarr & Sonarr automatically.

### 3. Radarr (`http://192.168.1.15:7878`) & Sonarr (`http://192.168.1.15:8989`)
- **Download Client**:
  - Go to **Settings** > **Download Clients** > **+** > **qBittorrent**:
    - Host: `qbittorrent`
    - Port: `8080`
    - Category: `movies` (for Radarr) or `tv` (for Sonarr)
- **Root Folder**:
  - In Radarr: `/data/media/movies`
  - In Sonarr: `/data/media/tv`
- **Quality Profile**:
  - Select or edit the profile to prioritize **1080p** releases.

### 4. Bazarr (`http://192.168.1.15:6767`) - Arabic Subtitles
- Go to **Settings** > **Radarr**:
  - Host: `radarr`, Port: `7878`, API Key from Radarr.
- Go to **Settings** > **Sonarr**:
  - Host: `sonarr`, Port: `8989`, API Key from Sonarr.
- Go to **Settings** > **Languages**:
  - Default Subtitle Language: **Arabic** (`ar`).
  - Enable *Hearing Impaired* fallback if desired.
- Go to **Settings** > **Providers**:
  - Enable providers with strong Arabic support (e.g., Subscene, OpenSubtitles.com, Podnapisi).

### 5. Jellyfin (`http://192.168.1.15:8096`)
- Complete the initial user wizard.
- Add Libraries:
  - **Movies**: `/data/media/movies`
  - **Shows**: `/data/media/tv`
- Go to **Admin Dashboard** > **Playback** > **Transcoding**:
  - Hardware acceleration: Select **Intel QuickSync (QSV)** or **Video Acceleration API (VAAPI)**.
  - VA API Device: `/dev/dri/renderD128`.
  - Enable hardware decoding only for **H.264** and **VC1**. Leave HEVC unchecked to avoid hardware errors on Haswell.

### 6. Jellyseerr (`http://192.168.1.15:5055`)
- Select **Jellyfin** as your media server.
  - Jellyfin URL: `http://jellyfin:8096`
  - Sign in with your Jellyfin credentials.
- In Jellyseerr Settings:
  - Connect **Radarr**: Server `http://radarr:7878`, paste API Key, select Root folder `/data/media/movies` and quality profile.
  - Connect **Sonarr**: Server `http://sonarr:8989`, paste API Key, select Root folder `/data/media/tv` and quality profile.

## Watch while downloading

1. Open **Jellyseerr** at `http://YOUR_SERVER_IP:5055` and search for a movie or show. This is the main search-and-watch entry point; opening port `8090` also redirects here.
2. Open the title and click the new **Watch now** button. If it has not been requested, Jellyseerr opens its normal request dialog (including season selection for TV). Confirm the request to continue to playback. Existing request permissions, quotas, and approval requirements still apply.
3. The player automatically waits for the matching download and prepares it for streaming. A movie opens automatically; a series with multiple video files lets you choose the episode. No manual torrent selection or copied link is needed. Matching uses Radarr/Sonarr download IDs, not approximate title text.
4. Playback begins after the first 16 MiB and final file piece are downloaded and verified. If a completed title's torrent is no longer present, playback navigation falls back to its Jellyfin library page. Browser autoplay policies may require pressing Play once.
5. Use **Open playlist in VLC** if your browser cannot play the format. Downloads continue in the background, and completed titles still import into Jellyfin. **Back to Jellyseerr** returns to the title page.

The downloads overview remains available for troubleshooting at `http://YOUR_SERVER_IP:8090/downloads`. Direct title links use `/watch/movie/TMDB_ID` or `/watch/tv/TMDB_ID`.

The service checks downloaded pieces before sending bytes, including HTTP byte-range requests. It never treats preallocated file size as proof that video data has downloaded. If playback catches up to the download, it waits; a request times out after 120 seconds without usable data. Retry playback after more data downloads. Seeking ahead does not reprioritize individual pieces and may take a while. Download speed and available peers still determine whether playback can remain smooth.

### Netflix-style operation

The recommended user flow is Jellyseerr as the search home, **Watch now** for an in-progress title, and Jellyfin for the completed library. The Homepage dashboard links these in that order and includes a direct Watch Now downloads view. Sonarr's TV default request profile is set to `Any` so older series can fall back to SD or 720p releases when 1080p is unavailable; Radarr's movie profile remains unchanged.

Watch Now distinguishes Arabic dubbing from subtitles. When an Arabic-dub request resolves to an original-language release, it does not autoplay silently. Bazarr TV episode status is checked as well as movie status, and missing Arabic subtitles are shown before the user chooses to play the original. A subtitle upload remains available for a local `.srt` or `.vtt` file.

Jellyfin is configured for VA-API using `/dev/dri/renderD128`. Keep hardware decoding limited to codecs supported by the machine, and verify a real transcode in the Jellyfin dashboard after changing client quality. Intro/credit skip, trickplay previews, per-user profiles, parental controls, and playback statistics are Jellyfin-side features that should be enabled from the dashboard or its official plugin repository after choosing the household policy.

Usenet and private indexers require provider/indexer accounts. They cannot be configured from this repository without credentials; qBittorrent remains the fallback download client.

### Optional Usenet fallback

SABnzbd is included behind the `usenet` Compose profile so it does not start until a provider is configured:

```bash
docker compose --profile usenet up -d sabnzbd
```

Open `http://YOUR_SERVER_IP:8081`, configure the Usenet provider and indexer, then add SABnzbd as a download client in both Sonarr and Radarr. Use `/data/usenet/complete` for completed downloads and `/data/usenet/incomplete` for temporary files. The profile is intentionally credential-free; provider and indexer accounts are required.

The health checker can be run manually or from a scheduler. Set `NETFELIX_NOTIFY_URL` in the ignored `.env` if you have a webhook endpoint. `./netfelix.sh backup` creates a permission-protected archive of configuration and databases while the stateful services are stopped; media and torrents are excluded.

`./netfelix.sh cleanup` is deliberately a report by default. Its `--apply` mode removes only old completed qBittorrent jobs and passes `deleteFiles=false`, so imported media and downloaded files remain on disk.

This version supports **v1 torrents without padding files**. It rejects v2/hybrid torrents instead of guessing their piece offsets. Browser codec support varies; VLC remains the fallback for unsupported formats. Watch Now can expose English subtitle files embedded in the torrent and Arabic/English subtitle files already available through Bazarr, plus local `.srt`/`.vtt` upload with timing controls. Use Jellyfin for its normal library, transcoding, and subtitle features once the import completes. The streaming service is intended for your trusted LAN and has no separate login; do not expose port 8090 to the internet.

### Running and troubleshooting

- `./netfelix.sh start` builds Watch Now and starts the stack. This setup uses Linux host networking to reach qBittorrent at `127.0.0.1:8080` and listens on port `8090`.
- The script finds the drive using `/dev/disk/by-label/Data`, mounts it if necessary, and uses its actual mount point, including `Data1`. It refuses to start when that drive or its `netfelix_data/torrents` folder is missing. Override the device when needed: `MEDIA_DEVICE=/dev/disk/by-uuid/YOUR_UUID ./netfelix.sh start`.
- For direct `docker compose` commands, mount the drive first and set `.env`'s `MEDIA_ROOT` to its real `netfelix_data` path. Existing containers must be recreated after changing bind-mount paths.
- The current qBittorrent installation already permits localhost access. On a fresh installation that requires login, set `QBT_USERNAME` and `QBT_PASSWORD` in your ignored `.env`; restart Watch Now. Do not commit these credentials.
- Set `JELLYSEERR_API_KEY`, `RADARR_API_KEY`, and `SONARR_API_KEY` in the ignored `.env` using each service's settings. These keys stay on the streaming server; they are never included in browser links or responses. The default API addresses use localhost ports 5055, 7878, and 8989.
- Watch Now mounts torrent data read-only. Its API only prepares existing video downloads; add titles through Jellyseerr/qBittorrent.
- Inspect logs with `docker compose logs --tail=100 watch-now`.
- Run the verification suite with `python3 -m unittest discover -s streaming/tests -v`.

API behavior follows the [official qBittorrent Web API documentation](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29).

### Jellyseerr customization

`jellyseerr/Dockerfile` builds the native movie/series **Watch now** buttons against pinned Jellyseerr 2.7.3 source and a matching runtime image. The source archive checksum is verified. `patch.cjs` fails if the expected component insertion points change. The rest of Jellyseerr, including its existing **Play on Jellyfin** and request controls, remains available.

Run `docker compose build jellyseerr watch-now` after changing either implementation, then `docker compose up -d jellyseerr watch-now`. The initial Jellyseerr build takes several minutes on this laptop; subsequent unchanged starts reuse its image. Upstream upgrades require deliberately updating the source checksum/image digest and verifying the patch and build. Runtime configuration and API keys remain excluded from Git.
