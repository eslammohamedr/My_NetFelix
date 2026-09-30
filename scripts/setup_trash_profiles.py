#!/usr/bin/env python3
"""
NetFelix TRaSH Quality Profiles & Custom Formats Setup
Configures Radarr and Sonarr for:
1. x265 / HEVC prioritization (+500 score)
2. CAM / TeleSync / Screeners rejection (-10000 score)
3. Surround Audio prioritization (+200 score)
4. Automated Quality Upgrading
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

ENV_FILE = Path("/home/dell/Desktop/My_NetFelix/.env")
env = {}
if ENV_FILE.exists():
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")

RADARR_URL = os.getenv("RADARR_URL", "http://127.0.0.1:7878")
RADARR_KEY = env.get("RADARR_API_KEY", "6254cab200464f29a49cdb10060a5a26")

SONARR_URL = os.getenv("SONARR_URL", "http://127.0.0.1:8989")
SONARR_KEY = env.get("SONARR_API_KEY", "29adbfd421e4418bb35dfc5fcddff7e6")

CUSTOM_FORMATS = [
    {
        "name": "x265 / HEVC (High Efficiency)",
        "includeCustomFormatWhenRenaming": False,
        "specifications": [
            {
                "name": "HEVC/x265",
                "implementation": "ReleaseTitleSpecification",
                "negate": False,
                "required": True,
                "fields": [{"name": "value", "value": r"[xh][\.\s]?265|hevc"}]
            }
        ],
        "score": 500
    },
    {
        "name": "Reject CAM / TeleSync / Low Quality",
        "includeCustomFormatWhenRenaming": False,
        "specifications": [
            {
                "name": "CAM/TS",
                "implementation": "ReleaseTitleSpecification",
                "negate": False,
                "required": True,
                "fields": [{"name": "value", "value": r"\b(CAM|TS|TELESYNC|HDTS|HDCAM|HD-CAM|SCREENER|SCR)\b"}]
            }
        ],
        "score": -10000
    },
    {
        "name": "Surround Sound (5.1 / 7.1 / Atmos)",
        "includeCustomFormatWhenRenaming": False,
        "specifications": [
            {
                "name": "Surround",
                "implementation": "ReleaseTitleSpecification",
                "negate": False,
                "required": True,
                "fields": [{"name": "value", "value": r"\b(DDP5[\.\s]1|DD\+5[\.\s]1|Atmos|TrueHD|DTS-HD|5[\.\s]1|7[\.\s]1)\b"}]
            }
        ],
        "score": 200
    }
]


def setup_service(service_name, base_url, api_key):
    print(f"[*] Configuring {service_name} at {base_url}...")
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    # 1. Fetch existing custom formats
    req = urllib.request.Request(f"{base_url}/api/v3/customformat", headers=headers)
    with urllib.request.urlopen(req) as resp:
        existing_cf = json.load(resp)

    existing_names = {cf["name"]: cf["id"] for cf in existing_cf}
    cf_id_scores = {}

    for cf in CUSTOM_FORMATS:
        name = cf["name"]
        score = cf["score"]
        if name in existing_names:
            cf_id = existing_names[name]
            print(f"  [-] Custom format '{name}' already exists (ID: {cf_id})")
        else:
            payload = {
                "name": name,
                "includeCustomFormatWhenRenaming": cf["includeCustomFormatWhenRenaming"],
                "specifications": cf["specifications"]
            }
            req_post = urllib.request.Request(
                f"{base_url}/api/v3/customformat",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(req_post) as resp_post:
                created = json.load(resp_post)
                cf_id = created["id"]
                print(f"  [+] Created custom format '{name}' (ID: {cf_id})")
        cf_id_scores[cf_id] = score

    # 2. Update Quality Profiles to include these scores and enable upgrades
    req_qp = urllib.request.Request(f"{base_url}/api/v3/qualityprofile", headers=headers)
    with urllib.request.urlopen(req_qp) as resp_qp:
        profiles = json.load(resp_qp)

    for p in profiles:
        p_name = p.get("name", "")
        # Enable upgrades for primary profiles
        p["upgradeAllowed"] = True
        
        # Merge format scores
        format_items = p.get("formatItems", [])
        existing_ids = {f.get("format"): f for f in format_items}

        for cf_id, score in cf_id_scores.items():
            if cf_id in existing_ids:
                existing_ids[cf_id]["score"] = score
            else:
                format_items.append({
                    "format": cf_id,
                    "name": next((cf["name"] for cf in CUSTOM_FORMATS if cf["name"] in existing_names or True), "Format"),
                    "score": score
                })

        p["formatItems"] = format_items

        # PUT updated profile
        req_put = urllib.request.Request(
            f"{base_url}/api/v3/qualityprofile/{p['id']}",
            data=json.dumps(p).encode("utf-8"),
            headers=headers,
            method="PUT"
        )
        with urllib.request.urlopen(req_put) as r_put:
            print(f"  [✓] Updated Quality Profile '{p_name}' (Upgrades: ON, Custom Formats: {len(format_items)})")

    print(f"[SUCCESS] {service_name} TRaSH configuration completed.\n")


if __name__ == "__main__":
    setup_service("Radarr", RADARR_URL, RADARR_KEY)
    setup_service("Sonarr", SONARR_URL, SONARR_KEY)
