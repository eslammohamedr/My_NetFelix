#!/usr/bin/env python3
"""
NetFelix Storage Monitor & Smart Auto-Prune Script
Monitors free space on media disk and safely cleans:
1. Stale temporary partial downloads (.temp.mp4, .part, .ytdl older than 24h).
2. Jellyfin transcode/streaming cache older than 48h.
3. Notifies when disk space is critically low.
"""

import os
import sys
import time
import shutil
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AutoPrune] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AutoPrune")

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/media/dell/Data1/netfelix_data"))
JELLYFIN_CACHE = Path("/home/dell/Desktop/My_NetFelix/config/jellyfin/cache/transcodes")
MIN_FREE_GB = int(os.getenv("MIN_FREE_GB", "40"))


def get_disk_free_gb(path):
    """Returns free space in GB on the filesystem containing path."""
    try:
        total, used, free = shutil.disk_usage(path)
        return free / (1024 ** 3)
    except Exception as e:
        logger.error(f"Error checking disk space for {path}: {e}")
        return 999


def prune_stale_temp_files(max_age_hours=24):
    """Removes leftover temporary download fragments older than max_age_hours."""
    search_dirs = [
        Path("/media/dell/Data1/Downloads"),
        MEDIA_ROOT / "media" / "movies",
        MEDIA_ROOT / "media" / "tv",
    ]

    now = time.time()
    reclaimed_bytes = 0
    temp_extensions = {".temp.mp4", ".part", ".ytdl", ".aria2"}

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for p in search_dir.rglob("*"):
            if p.is_file():
                if any(str(p).endswith(ext) for ext in temp_extensions) or ".temp." in p.name:
                    try:
                        age_hours = (now - p.stat().st_mtime) / 3600
                        if age_hours > max_age_hours:
                            size = p.stat().st_size
                            p.unlink()
                            reclaimed_bytes += size
                            logger.info(f"Removed stale temporary file ({round(size/(1024*1024), 1)} MB): {p.name}")
                    except Exception as e:
                        logger.warning(f"Failed to process {p}: {e}")

    return reclaimed_bytes / (1024 ** 2)


def prune_transcode_cache(max_age_hours=48):
    """Cleans old transcode segments from Jellyfin cache."""
    if not JELLYFIN_CACHE.exists():
        return 0

    now = time.time()
    reclaimed_bytes = 0
    for p in JELLYFIN_CACHE.rglob("*"):
        if p.is_file():
            age_hours = (now - p.stat().st_mtime) / 3600
            if age_hours > max_age_hours:
                size = p.stat().st_size
                try:
                    p.unlink()
                    reclaimed_bytes += size
                except Exception:
                    pass

    return reclaimed_bytes / (1024 ** 2)


def prune_completed_torrents(max_seeding_hours=24, min_ratio=1.0):
    """Safely cleans completed torrents from qBittorrent queue while preserving media files."""
    import urllib.request
    import json
    try:
        import urllib.parse
        req = urllib.request.Request("http://127.0.0.1:8080/api/v2/torrents/info?filter=completed")
        with urllib.request.urlopen(req, timeout=5) as r:
            torrents = json.load(r)

        pruned = 0
        for t in torrents:
            seeding_time = t.get("seeding_time", 0) / 3600
            ratio = t.get("ratio", 0)
            h = t.get("hash")
            if (seeding_time >= max_seeding_hours or ratio >= min_ratio) and h:
                post_data = urllib.parse.urlencode({
                    "hashes": h,
                    "deleteFiles": "false"
                }).encode("utf-8")
                del_req = urllib.request.Request(
                    "http://127.0.0.1:8080/api/v2/torrents/delete",
                    data=post_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                urllib.request.urlopen(del_req, timeout=5)
                pruned += 1
                logger.info(f"Cleaned completed seeding torrent: {t.get('name')}")
        return pruned
    except Exception as e:
        logger.error(f"Error checking completed torrents: {e}")
        return 0


def run_prune():
    free_gb = get_disk_free_gb(MEDIA_ROOT)
    logger.info(f"Disk check: {round(free_gb, 1)} GB free (Threshold: {MIN_FREE_GB} GB).")

    temp_mb = prune_stale_temp_files()
    cache_mb = prune_transcode_cache()
    torrents_cleaned = prune_completed_torrents()
    total_reclaimed_mb = temp_mb + cache_mb

    if total_reclaimed_mb > 0 or torrents_cleaned > 0:
        logger.info(f"Successfully reclaimed {round(total_reclaimed_mb, 1)} MB of disk space. Cleaned {torrents_cleaned} completed torrents.")
    else:
        logger.info("Storage is healthy and clean. No stale fragments found.")

    if free_gb < MIN_FREE_GB:
        logger.warning(f"⚠️ LOW DISK SPACE WARNING: Only {round(free_gb, 1)} GB remaining on {MEDIA_ROOT}!")


if __name__ == "__main__":
    run_prune()
