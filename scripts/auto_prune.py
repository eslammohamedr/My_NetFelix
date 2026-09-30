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
    if not MEDIA_ROOT.exists():
        return 0

    now = time.time()
    reclaimed_bytes = 0
    temp_extensions = {".temp.mp4", ".part", ".ytdl", ".aria2"}

    for p in MEDIA_ROOT.rglob("*"):
        if p.is_file():
            if any(str(p).endswith(ext) for ext in temp_extensions) or ".temp." in p.name:
                age_hours = (now - p.stat().st_mtime) / 3600
                if age_hours > max_age_hours:
                    size = p.stat().st_size
                    try:
                        p.unlink()
                        reclaimed_bytes += size
                        logger.info(f"Removed stale temporary file ({round(size/(1024*1024), 1)} MB): {p.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete {p}: {e}")

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


def run_prune():
    free_gb = get_disk_free_gb(MEDIA_ROOT)
    logger.info(f"Disk check: {round(free_gb, 1)} GB free (Threshold: {MIN_FREE_GB} GB).")

    temp_mb = prune_stale_temp_files()
    cache_mb = prune_transcode_cache()
    total_reclaimed_mb = temp_mb + cache_mb

    if total_reclaimed_mb > 0:
        logger.info(f"Successfully reclaimed {round(total_reclaimed_mb, 1)} MB of disk space.")
    else:
        logger.info("Storage is healthy and clean. No stale fragments found.")

    if free_gb < MIN_FREE_GB:
        logger.warning(f"⚠️ LOW DISK SPACE WARNING: Only {round(free_gb, 1)} GB remaining on {MEDIA_ROOT}!")


if __name__ == "__main__":
    run_prune()
