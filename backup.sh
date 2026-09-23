#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root_dir"
backup_root="${BACKUP_ROOT:-$root_dir/backups}"
mkdir -p "$backup_root"
stamp="$(date +%Y%m%d-%H%M%S)"
archive="$backup_root/netfelix-config-$stamp.tar.gz"

# Stop writes to SQLite databases while making the archive. Media and torrents
# are intentionally excluded; they are large and remain on the data drive.
docker compose stop jellyfin jellyseerr radarr sonarr prowlarr bazarr >/dev/null
trap 'docker compose start jellyfin jellyseerr radarr sonarr prowlarr bazarr >/dev/null' EXIT
tar -czf "$archive" \
  --exclude='*/db/*.db-shm' --exclude='*/db/*.db-wal' \
  config .env.example docker-compose.yml
chmod 600 "$archive"
echo "Created $archive"
