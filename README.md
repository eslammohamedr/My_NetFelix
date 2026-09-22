# My NetFelix 🎬🍿

An automated, self-hosted streaming and media management stack tailored for local network playback with Arabic subtitle support.

---

## Stack Components

| Service | Local URL | Description |
| :--- | :--- | :--- |
| **Homepage** | [http://192.168.1.15:3000](http://192.168.1.15:3000) | Single dashboard linking all services |
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
- **Hardware Acceleration**: Intel VA-API (`/dev/dri`) is mounted for Jellyfin.
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
