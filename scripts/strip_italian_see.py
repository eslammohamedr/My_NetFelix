#!/usr/bin/env python3
import os
from local_env import load_local_env
load_local_env()
import os
import sys
import glob
import subprocess
import urllib.request
from pathlib import Path

SEE_DIR = Path("/media/dell/Data1/netfelix_data/media/tv/See")
FFMPEG = "/home/dell/.local/bin/ffmpeg"
JELLYFIN_KEY = os.getenv("JELLYFIN_API_KEY", "")

def refresh_jellyfin():
    try:
        url = "http://localhost:8096/Library/Refresh"
        req = urllib.request.Request(url, headers={"Authorization": f'MediaBrowser Token="{JELLYFIN_KEY}"'}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Refresh error: {e}")

def main():
    mkv_files = sorted(glob.glob(str(SEE_DIR / "*.mkv")))
    print(f"Found {len(mkv_files)} episodes.")

    for f in mkv_files:
        # Check if file has Italian audio
        try:
            probe = subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries",
                "stream=index:stream_tags=language", "-select_streams", "a",
                "-of", "csv=p=0", f
            ], text=True)
        except Exception:
            continue

        langs = [line.strip().split(",")[-1] for line in probe.strip().splitlines() if line.strip()]
        if "ita" not in langs:
            print(f"Already English only: {os.path.basename(f)}")
            continue

        print(f"Stripping Italian from: {os.path.basename(f)}")
        tmp_out = f + ".eng_only.mkv"
        cmd = [
            FFMPEG, "-i", f,
            "-map", "0:v",
            "-map", "0:a:m:language:eng",
            "-map", "0:s?",
            "-c", "copy",
            tmp_out, "-y"
        ]

        ret = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ret.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 1000000:
            os.replace(tmp_out, f)
            print(f"Successfully processed: {os.path.basename(f)}")
        else:
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
            print(f"Failed to process: {os.path.basename(f)}")

    refresh_jellyfin()
    print("All See episodes processed!")

if __name__ == "__main__":
    main()
