#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# If docker daemon cannot be contacted without sudo but user is in docker group, re-exec with sg docker
if ! docker ps >/dev/null 2>&1; then
    if id -Gn | grep -qw docker || getent group docker | grep -qw "$USER"; then
        if [ "$DOCKER_WRAPPED" != "1" ]; then
            export DOCKER_WRAPPED=1
            exec sg docker -c "$SCRIPT_DIR/netfelix.sh $*"
        fi
    fi
fi


# Ensure Data drive is mounted
ensure_mounted() {
    local media_device="${MEDIA_DEVICE:-/dev/disk/by-label/Data}"
    local mounted_at
    if [ ! -b "$media_device" ]; then
        echo "Media drive not found: $media_device. Connect it before starting."
        return 1
    fi
    mounted_at="$(findmnt -rn -S "$media_device" -o TARGET || true)"
    if [ -z "$mounted_at" ]; then
        udisksctl mount -b "$media_device" || return 1
        mounted_at="$(findmnt -rn -S "$media_device" -o TARGET || true)"
    fi
    if [ -z "$mounted_at" ] || [ ! -d "$mounted_at/netfelix_data/torrents" ]; then
        echo "The media drive is not ready or netfelix_data/torrents is missing."
        return 1
    fi
    export MEDIA_ROOT="$mounted_at/netfelix_data"
}

detect_ip() {
    ip -4 addr show scope global | grep inet | awk '{print $2}' | cut -d/ -f1 | head -n 1 || echo "127.0.0.1"
}

print_urls() {
    local host_ip
    host_ip="$(detect_ip)"
    echo ""
    echo "========================================================================="
    echo "                     My NetFelix Service Directory                      "
    echo "========================================================================="
    printf "  %-18s %-32s %s\n" "SERVICE" "LOCAL URL" "WHAT IT DOES"
    echo "  -----------------------------------------------------------------------"
    printf "  %-18s %-32s %s\n" "Homepage" "http://${host_ip}:3000" "Unified Dashboard"
    printf "  %-18s %-32s %s\n" "Watch Now" "http://${host_ip}:8090" "Play While Downloading"
    printf "  %-18s %-32s %s\n" "Jellyseerr" "http://${host_ip}:5055" "Search & Request Movies / Shows"
    printf "  %-18s %-32s %s\n" "Jellyfin" "http://${host_ip}:8096" "Watch & Stream Media Player"
    printf "  %-18s %-32s %s\n" "Radarr" "http://${host_ip}:7878" "Movie Library Manager"
    printf "  %-18s %-32s %s\n" "Sonarr" "http://${host_ip}:8989" "TV Series Library Manager"
    printf "  %-18s %-32s %s\n" "Prowlarr" "http://${host_ip}:9696" "Torrent Indexers & Sync"
    printf "  %-18s %-32s %s\n" "qBittorrent" "http://${host_ip}:8080" "Torrent Downloader"
    printf "  %-18s %-32s %s\n" "Bazarr" "http://${host_ip}:6767" "Arabic Subtitles"
    echo "========================================================================="
    echo ""
}

case "${1:-start}" in
    start|up)
        ensure_mounted
        echo ">> Starting My NetFelix stack..."
        docker compose up -d --build
        print_urls
        ;;
    stop|down)
        echo ">> Stopping My NetFelix stack..."
        docker compose down
        ;;
    restart)
        ensure_mounted
        echo ">> Restarting My NetFelix stack..."
        docker compose up -d --build --force-recreate
        print_urls
        ;;
    status|ps)
        docker compose ps
        print_urls
        ;;
    logs)
        shift
        docker compose logs -f "$@"
        ;;
    update|pull)
        ensure_mounted
        echo ">> Pulling latest images..."
        docker compose pull
        echo ">> Recreating containers..."
        docker compose up -d --build
        print_urls
        ;;
    backup)
        BACKUP_ROOT="${BACKUP_ROOT:-$SCRIPT_DIR/backups}" ./backup.sh
        ;;
    health)
        python3 scripts/healthcheck.py
        ;;
    cleanup)
        python3 scripts/cleanup.py "${@:2}"
        ;;
    recover)
        python3 scripts/recover_downloads.py
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs [service]|update|backup|health|cleanup [--apply]|recover}"
        exit 1
        ;;
esac
