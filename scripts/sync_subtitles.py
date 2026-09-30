#!/usr/bin/env python3
"""
NetFelix Subtitle Synchronization & Generation Script
Extracts embedded subtitles to external .srt files and generates Arabic translations
where needed, then notifies Jellyfin and Bazarr.
"""

import os
import sys
import re
import json
import time
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/media/dell/Data1/netfelix_data/media")
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "http://127.0.0.1:8096")
JELLYFIN_TOKEN = os.getenv("JELLYFIN_TOKEN", "4d40f90a8b854cdcbb4faa23134d057b")
BAZARR_URL = os.getenv("BAZARR_URL", "http://127.0.0.1:6767")
BAZARR_API_KEY = os.getenv("BAZARR_API_KEY", "36ee82e7b103b981f2097c25f859b9a1")

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".m4v"}
DELIMITER = "§§§"


def translate_text(text, src="en", dest="ar", retries=3):
    """Translate text using Google Translate GTX endpoint with retry."""
    if not text.strip():
        return text
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={src}&tl={dest}&dt=t&q=" + urllib.parse.quote(text)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return "".join([part[0] for part in data[0] if part and part[0]])
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(1 + attempt)
    return text


def parse_srt(srt_path):
    """Parse SRT file into a list of (index, timestamp, text) tuples."""
    with open(srt_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip())
    cues = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 2:
            idx = lines[0].strip()
            # Timestamp line looks like 00:00:00,000 --> 00:00:00,000
            if "-->" in lines[1]:
                timestamp = lines[1].strip()
                text = "\n".join(lines[2:])
                cues.append((idx, timestamp, text))
            elif "-->" in lines[0]:
                timestamp = lines[0].strip()
                text = "\n".join(lines[1:])
                cues.append((str(len(cues) + 1), timestamp, text))
    return cues


def write_srt(cues, output_path):
    """Write (index, timestamp, text) tuples to an SRT file."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, (_, timestamp, text) in enumerate(cues, 1):
            f.write(f"{i}\n{timestamp}\n{text}\n\n")


def translate_cues_to_arabic(cues, batch_size=25):
    """Translate SRT cues from English to Arabic in robust batches."""
    translated_cues = []
    total = len(cues)

    for start_idx in range(0, total, batch_size):
        batch = cues[start_idx : start_idx + batch_size]
        texts = [c[2] for c in batch]
        joined = f"\n{DELIMITER}\n".join(texts)

        try:
            trans_res = translate_text(joined, src="en", dest="ar")
            parts = [p.strip() for p in trans_res.split(DELIMITER)]
            if len(parts) == len(batch):
                for (idx, ts, _), trans_text in zip(batch, parts):
                    translated_cues.append((idx, ts, trans_text))
                continue
        except Exception as e:
            print(f"    Batch translation warning: {e}, falling back to item-by-item...")

        # Fallback to item-by-item if batch split length doesn't match
        for idx, ts, orig_text in batch:
            try:
                trans_text = translate_text(orig_text, src="en", dest="ar")
                translated_cues.append((idx, ts, trans_text.strip()))
            except Exception as e:
                print(f"    Item translation failed: {e}")
                translated_cues.append((idx, ts, orig_text))
            time.sleep(0.05)

    return translated_cues


def get_docker_media_path(host_path):
    """Convert host media path to Jellyfin container path."""
    host_str = str(host_path)
    if host_str.startswith(MEDIA_ROOT):
        rel = os.path.relpath(host_str, MEDIA_ROOT)
        return f"/data/media/{rel}"
    return host_str


def probe_streams(host_video_path):
    """Check audio and subtitle streams using Jellyfin's ffprobe."""
    container_path = get_docker_media_path(host_video_path)
    cmd = [
        "docker", "exec", "netfelix-jellyfin",
        "/usr/lib/jellyfin-ffmpeg/ffprobe",
        "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name:stream_tags=language,title",
        "-of", "json",
        container_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout).get("streams", [])
    except Exception as e:
        print(f"Error probing {host_video_path}: {e}")
        return []


def extract_subtitle_stream(host_video_path, stream_idx, output_srt_host):
    """Extract an embedded subtitle track to an external SRT file."""
    container_video = get_docker_media_path(host_video_path)
    container_srt = get_docker_media_path(output_srt_host)
    cmd = [
        "docker", "exec", "netfelix-jellyfin",
        "/usr/lib/jellyfin-ffmpeg/ffmpeg",
        "-y",
        "-i", container_video,
        "-map", f"0:{stream_idx}",
        "-c:s", "srt",
        container_srt
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr}")
        return False


def process_video_file(video_path):
    """Process a single video file to ensure English and Arabic SRTs exist."""
    parent = video_path.parent
    stem = video_path.stem
    en_srt = parent / f"{stem}.en.srt"
    ar_srt = parent / f"{stem}.ar.srt"

    # Also check if any existing .en / .ar variations exist
    has_en = en_srt.exists() or any(parent.glob(f"{stem}*.en*.srt"))
    has_ar = ar_srt.exists() or any(parent.glob(f"{stem}*.ar*.srt"))

    if has_en and has_ar:
        return

    print(f"\n[Processing] {video_path.name}")
    streams = probe_streams(video_path)
    sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

    # If missing English SRT, check if there's an embedded English track
    if not has_en:
        eng_stream = None
        for s in sub_streams:
            lang = (s.get("tags", {}).get("language") or "").lower()
            title = (s.get("tags", {}).get("title") or "").lower()
            if lang in ("eng", "en") or "english" in title or "cc" in title:
                eng_stream = s
                break
        if not eng_stream and sub_streams:
            eng_stream = sub_streams[0]

        if eng_stream:
            print(f"  -> Extracting embedded English subtitle (stream {eng_stream.get('index')})...")
            if extract_subtitle_stream(video_path, eng_stream.get("index"), en_srt):
                has_en = True
                print(f"  -> Created {en_srt.name}")

    # If English SRT exists and Arabic SRT is missing, generate Arabic
    if has_en and not has_ar:
        source_en = en_srt if en_srt.exists() else next(parent.glob(f"{stem}*.en*.srt"))
        print(f"  -> Translating English subtitles to Arabic ({source_en.name} -> {ar_srt.name})...")
        cues = parse_srt(source_en)
        if cues:
            translated = translate_cues_to_arabic(cues)
            write_srt(translated, ar_srt)
            # Ensure correct file permissions
            os.chmod(ar_srt, 0o664)
            print(f"  -> Successfully generated {ar_srt.name} ({len(translated)} cues)!")
        else:
            print(f"  -> Warning: No cues found in {source_en.name}")


def sync_all():
    """Scan movies and tv folders and process all video files."""
    media_dir = Path(MEDIA_ROOT)
    if not media_dir.exists():
        print(f"Error: Media root does not exist: {MEDIA_ROOT}")
        return

    print(f"Scanning media directory: {MEDIA_ROOT}...")
    video_files = []
    for ext in VIDEO_EXTS:
        video_files.extend(media_dir.rglob(f"*{ext}"))

    # Exclude trickplay or partial downloads
    video_files = [f for f in video_files if ".trickplay" not in str(f) and "!qB" not in str(f)]
    print(f"Found {len(video_files)} media files.")

    for v in sorted(video_files):
        try:
            process_video_file(v)
        except Exception as e:
            print(f"Error processing {v}: {e}")

    # Notify Jellyfin to refresh libraries
    print("\nTriggering Jellyfin Library Refresh...")
    try:
        req = urllib.request.Request(
            f"{JELLYFIN_URL}/Library/Refresh",
            headers={"Authorization": f'MediaBrowser Token="{JELLYFIN_TOKEN}"'},
            data=b""
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("  Jellyfin Library Refresh triggered successfully.")
    except Exception as e:
        print(f"  Could not trigger Jellyfin refresh: {e}")

    # Notify Bazarr to sync disk subtitles
    print("\nTriggering Bazarr subtitle indexer...")
    try:
        req = urllib.request.Request(
            f"{BAZARR_URL}/api/series?action=sync",
            headers={"X-Api-Key": BAZARR_API_KEY},
            data=b""
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("  Bazarr Series sync triggered.")
    except Exception as e:
        print(f"  Could not trigger Bazarr sync: {e}")


if __name__ == "__main__":
    sync_all()
