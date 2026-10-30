#!/usr/bin/env python3
"""
NetFelix Device Activity Inspector & Web Dashboard
Provides real-time analytics, application categorization, and interactive monitoring
for every connected device on the local network via AdGuard Home integration.
"""

import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from collections import Counter, defaultdict

logger = logging.getLogger("DeviceDashboard")

BASE_DIR = Path("/home/dell/Desktop/My_NetFelix")
CONFIG_DIR = BASE_DIR / "config"
DEVICES_FILE = CONFIG_DIR / "known_devices.json"
ADULT_FILE = CONFIG_DIR / "adult_domains.txt"

# In-memory cache for adult domains
_ADULT_DOMAINS = set()


def load_adult_domains():
    global _ADULT_DOMAINS
    if not _ADULT_DOMAINS and ADULT_FILE.exists():
        try:
            with open(ADULT_FILE, "r", encoding="utf-8") as f:
                _ADULT_DOMAINS = set(line.strip().lower() for line in f if line.strip() and not line.startswith("#"))
        except Exception as e:
            logger.error(f"Error loading adult domains: {e}")
    return _ADULT_DOMAINS


def is_adult_domain(domain):
    d = domain.lower().strip(".")
    adults = load_adult_domains()
    if d in adults:
        return True
    parts = d.split(".")
    if len(parts) > 2 and ".".join(parts[-2:]) in adults:
        return True
    keywords = ["porn", "xvideos", "xnxx", "redtube", "youporn", "stripchat", "chaturbate", "beeg.com", "brazzers", "spankbang", "eporner"]
    return any(k in d for k in keywords)


def humanize_domain(d):
    """Translates cryptic CDN, streaming, and internal subdomains into clear human-friendly labels."""
    d = d.lower().strip(".")
    if d.endswith(".in-addr.arpa") or d.endswith(".ip6.arpa"):
        return None  # Filter out internal network routing lookups
    if "3gppnetwork.org" in d:
        return "📞 مكالمات الواي فاي (VoWiFi)"
    if "googlevideo.com" in d:
        return "📺 تشغيل فيديو يوتيوب (YouTube Stream)"
    if "ggpht.com" in d or "ytimg.com" in d:
        return "📺 وسائط وقنوات يوتيوب (YouTube Media)"
    if "phncdn.com" in d:
        return "🔞 خوادم تشغيل الفيديو (Video CDN)"
    if any(k in d for k in ["trafficjunky", "adtng.com", "etahub.com"]):
        return "🔞 خوادم توثيق وتصفح المواقع"
    if "fbcdn.net" in d or "fbsbx.com" in d:
        return "🔵 وسائط وصور فيسبوك (Facebook CDN)"
    if "cdninstagram.com" in d:
        return "📸 وسائط وصور إنستغرام (Instagram CDN)"
    if "mtalk.google.com" in d:
        return "🔔 إشعارات وتنبيهات أندرويد (Google Push)"
    if "connectivitycheck" in d or "connectivity" in d:
        return "📶 فحص اتصال الواي فاي بالإنترنت"
    if "inbox.google.com" in d or "mail.google.com" in d:
        return "✉️ بريد جوجل (Gmail / Inbox)"
    if "googleapis.com" in d:
        return "⚙️ خدمات نظام أندرويد (Google Services)"
    if "googletagmanager.com" in d or "analytics" in d:
        return "📊 إحصائيات التصفح (Analytics)"
    if d.startswith("www."):
        d = d[4:]
    return f"🌐 {d}"


def get_devices_activity_data():
    """Fetches and aggregates recent query logs for all devices."""
    known_devices = {}
    if DEVICES_FILE.exists():
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                known_devices = json.load(f)
        except Exception:
            pass

    # Map IP to known device metadata
    ip_to_dev = {
        "192.168.1.15": {"name": "سيرفر NetFelix", "mac": "", "vendor": "Dell Server", "type": "server"},
        "127.0.0.1": {"name": "سيرفر NetFelix (محلي)", "mac": "", "vendor": "Dell Server", "type": "server"},
        "172.18.0.1": {"name": "بوابة Docker الداخلية", "mac": "", "vendor": "Docker Network", "type": "server"}
    }

    # Read live ARP table to know real current IP -> MAC mappings
    live_arp = {}
    try:
        with open("/proc/net/arp") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[0].startswith("192.168.1.") and parts[3] != "00:00:00:00:00:00":
                    live_arp[parts[0]] = parts[3].upper()
    except Exception:
        pass

    # Sort known devices by last_seen ascending so newer seen devices override older stale IPs
    sorted_devs = sorted(known_devices.items(), key=lambda kv: kv[1].get("last_seen", ""))
    for mac, dev in sorted_devs:
        ip = dev.get("ip")
        if ip:
            # If this IP is currently active on network with a different MAC, don't overwrite with stale offline device
            if ip in live_arp and live_arp[ip] != mac:
                continue
            dev_name = dev.get("alias") or dev.get("hostname") or f"جهاز ({ip})"
            dev_type = "mobile"
            vendor_lower = dev.get("vendor", "").lower()
            name_lower = dev_name.lower()
            if "router" in name_lower or "gateway" in name_lower or ip == "192.168.1.1":
                dev_type = "router"
            elif "laptop" in name_lower or "labtop" in name_lower or "cai1" in name_lower:
                dev_type = "laptop"
            elif "tv" in name_lower or "شاشة" in name_lower or "samsung" in name_lower and "ultra" not in name_lower:
                dev_type = "tv"
            elif "phone" in name_lower or "هاتف" in name_lower or "s24" in name_lower:
                dev_type = "mobile"

            ip_to_dev[ip] = {
                "name": dev_name,
                "mac": mac,
                "vendor": dev.get("vendor", "غير محدد"),
                "hostname": dev.get("hostname", ""),
                "type": dev_type
            }

    # For any active IP in live_arp that wasn't in known_devices, ensure it has an entry
    for aip, amac in live_arp.items():
        if aip not in ip_to_dev:
            ip_to_dev[aip] = {
                "name": f"هاتف / جهاز ({aip})",
                "mac": amac,
                "vendor": "غير محدد",
                "hostname": "",
                "type": "mobile"
            }

    # Query AdGuard Query Log
    query_entries = []
    try:
        url = "http://127.0.0.1:8085/control/querylog?limit=500"
        req = urllib.request.Request(url, headers={"Authorization": "Basic YWRtaW46bmV0ZmVsaXg="})
        with urllib.request.urlopen(req, timeout=5) as r:
            qdata = json.load(r)
            query_entries = qdata.get("data", [])
    except Exception as e:
        logger.error(f"Error fetching AdGuard query log: {e}")

    # Group by client IP
    by_client = defaultdict(list)
    total_blocked_overall = 0
    total_adult_overall = 0

    for e in query_entries:
        client = e.get("client")
        if client:
            by_client[client].append(e)
            if e.get("reason", "").startswith("Filter"):
                total_blocked_overall += 1

    devices_list = []

    # First add all active clients with queries
    all_known_ips = set(ip_to_dev.keys())
    active_ips = set(by_client.keys())

    for ip in active_ips:
        qlist = by_client[ip]
        meta = ip_to_dev.get(ip, {"name": f"جهاز ({ip})", "mac": "", "vendor": "غير محدد", "type": "device"})
        domains = []
        blocked = 0
        categories = Counter()

        for q in qlist:
            d = q.get("question", {})
            dname = d.get("name", "").lower()
            if not dname:
                continue
            domains.append(dname)
            if q.get("reason", "").startswith("Filter"):
                blocked += 1

            if is_adult_domain(dname):
                categories["🔞 محتوى للبالغين"] += 1
                total_adult_overall += 1
            elif any(k in dname for k in ["youtube", "googlevideo", "ytimg", "youtu.be", "gvt1", "gvt2", "gvt3"]):
                categories["📺 يوتيوب"] += 1
            elif any(k in dname for k in ["facebook", "fbcdn", "fbsbx", "meta.com", "messenger"]):
                categories["🔵 فيسبوك"] += 1
            elif any(k in dname for k in ["instagram", "cdninstagram"]):
                categories["📸 إنستغرام"] += 1
            elif any(k in dname for k in ["tiktok", "byteoversea", "ibytedtos"]):
                categories["🎵 تيك توك"] += 1
            elif any(k in dname for k in ["whatsapp", "wa.me"]):
                categories["💬 واتساب"] += 1
            elif any(k in dname for k in ["telegram", "t.me"]):
                categories["✈️ تيليجرام"] += 1
            elif any(k in dname for k in ["twitter", "x.com", "twimg"]):
                categories["🐦 إكس / تويتر"] += 1
            elif any(k in dname for k in ["netflix", "nflx", "shahid", "watchit"]):
                categories["🍿 منصات البث"] += 1
            elif any(k in dname for k in ["google", "gstatic", "googleapis", "doubleclick", "googleadservices"]):
                categories["🔍 خدمات جوجل"] += 1
            elif "3gppnetwork.org" in dname:
                categories["📞 مكالمات الواي فاي"] += 1
            elif any(k in dname for k in ["apple", "icloud"]):
                categories["🍏 خدمات آبل"] += 1
            elif any(k in dname for k in ["samsung"]):
                categories["📱 خدمات سامسونج"] += 1

        human_domains = []
        for q in qlist:
            d = q.get("question", {})
            dname = d.get("name", "").lower()
            if dname:
                h = humanize_domain(dname)
                if h:
                    human_domains.append(h)

        top_doms = [{"domain": dom, "count": cnt} for dom, cnt in Counter(human_domains).most_common(5)]
        top_cats = [{"category": cat, "count": cnt} for cat, cnt in categories.most_common(5)]

        last_time = qlist[0].get("time", "")[:19].replace("T", " ") if qlist else ""

        devices_list.append({
            "ip": ip,
            "name": meta["name"],
            "mac": meta.get("mac", ""),
            "vendor": meta.get("vendor", "غير محدد"),
            "type": meta.get("type", "device"),
            "queries_count": len(qlist),
            "blocked_count": blocked,
            "top_categories": top_cats,
            "top_domains": top_doms,
            "last_active": last_time,
            "is_active": True
        })

    # Also add registered devices that have 0 recent queries so user can see their full home network
    for ip in all_known_ips - active_ips:
        if ip in ("127.0.0.1", "172.18.0.1"):
            continue
        meta = ip_to_dev[ip]
        devices_list.append({
            "ip": ip,
            "name": meta["name"],
            "mac": meta.get("mac", ""),
            "vendor": meta.get("vendor", "غير محدد"),
            "type": meta.get("type", "device"),
            "queries_count": 0,
            "blocked_count": 0,
            "top_categories": [],
            "top_domains": [],
            "last_active": "في وضع الخمول",
            "is_active": False
        })

    # Sort: active first by query count descending
    devices_list.sort(key=lambda x: (x["is_active"], x["queries_count"]), reverse=True)

    return {
        "status": "success",
        "total_devices": len(devices_list),
        "active_devices_count": len(active_ips),
        "total_queries_analyzed": len(query_entries),
        "total_blocked": total_blocked_overall,
        "total_adult_queries": total_adult_overall,
        "devices": devices_list
    }


DEVICE_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetFelix | راصد نشاط الأجهزة والشبكة</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220%22%20%22100%22%20%22100%22><text y=%22.9em%22 font-size=%2290%22>🛡️</text></svg>">
    <style>
        :root {
            --bg-main: #0b0f19;
            --bg-card: #151d30;
            --bg-card-hover: #1b2640;
            --border-color: #243252;
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.2);
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-main);
            color: var(--text-main);
            padding: 24px 16px;
            min-height: 100vh;
        }

        .container {
            max-width: 1300px;
            margin: 0 auto;
        }

        /* Top Header */
        header {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }

        .brand-box {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-icon {
            font-size: 2.4rem;
            background: linear-gradient(135deg, #0284c7, #38bdf8);
            border-radius: 14px;
            padding: 8px 12px;
            box-shadow: 0 4px 16px var(--primary-glow);
        }

        .brand-title {
            font-size: 1.6rem;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #fff;
        }

        .brand-desc {
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-top: 4px;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }

        .btn {
            background: var(--bg-card);
            color: #fff;
            border: 1px solid var(--border-color);
            padding: 9px 16px;
            border-radius: 10px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .btn:hover {
            background: var(--bg-card-hover);
            border-color: var(--primary);
            box-shadow: 0 2px 10px var(--primary-glow);
        }

        .btn-primary {
            background: linear-gradient(135deg, #0284c7, #0ea5e9);
            border-color: transparent;
        }
        .btn-primary:hover {
            background: linear-gradient(135deg, #0369a1, #0284c7);
        }

        /* Stats Bar */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 18px 20px;
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .stat-icon {
            font-size: 2rem;
            width: 52px;
            height: 52px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-color);
        }

        .stat-val {
            font-size: 1.6rem;
            font-weight: 700;
            color: #fff;
        }

        .stat-lbl {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 2px;
        }

        /* Filter Controls */
        .filter-row {
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            margin-bottom: 24px;
            align-items: center;
            justify-content: space-between;
        }

        .search-input {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: #fff;
            padding: 11px 18px;
            border-radius: 10px;
            font-size: 0.95rem;
            width: 100%;
            max-width: 380px;
            outline: none;
            transition: border-color 0.2s;
        }

        .search-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        .live-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 20px;
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: pulse 1.8s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        /* Device Cards Grid */
        .devices-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 20px;
        }

        .device-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            transition: transform 0.2s, border-color 0.2s;
            position: relative;
        }

        .device-card:hover {
            transform: translateY(-2px);
            border-color: #3b82f6;
            background: var(--bg-card-hover);
        }

        .device-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
        }

        .device-title-box {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .device-icon {
            font-size: 1.8rem;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
        }

        .device-name {
            font-size: 1.15rem;
            font-weight: 700;
            color: #fff;
            line-height: 1.3;
        }

        .device-vendor {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 3px;
        }

        .ip-badge {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.82rem;
            background: rgba(56, 189, 248, 0.12);
            color: var(--primary);
            padding: 4px 10px;
            border-radius: 8px;
            border: 1px solid rgba(56, 189, 248, 0.25);
            font-weight: 600;
        }

        .metrics-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            padding: 12px 14px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.03);
        }

        .metric-item {
            display: flex;
            flex-direction: column;
        }

        .metric-num {
            font-size: 1.25rem;
            font-weight: 700;
            color: #fff;
        }

        .metric-sub {
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        /* App tags */
        .section-label {
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .tags-container {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        .tag-pill {
            font-size: 0.82rem;
            padding: 4px 10px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--border-color);
            color: #e2e8f0;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .tag-pill.adult {
            background: rgba(239, 68, 68, 0.15);
            color: #fca5a5;
            border-color: rgba(239, 68, 68, 0.35);
        }

        .tag-pill.youtube {
            background: rgba(239, 68, 68, 0.12);
            color: #ff8080;
            border-color: rgba(239, 68, 68, 0.25);
        }

        .tag-count {
            background: rgba(0, 0, 0, 0.3);
            padding: 1px 6px;
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 700;
        }

        /* Domains List */
        .domains-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .domain-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
            padding: 5px 8px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 6px;
        }

        .domain-text {
            color: #cbd5e1;
            direction: ltr;
            text-align: left;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 220px;
            font-family: ui-monospace, SFMono-Regular, monospace;
            font-size: 0.8rem;
        }

        /* Action Buttons */
        .card-actions {
            display: flex;
            gap: 10px;
            margin-top: auto;
            padding-top: 8px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .btn-card {
            flex: 1;
            padding: 8px 12px;
            font-size: 0.82rem;
            text-align: center;
            justify-content: center;
        }

        /* Footer */
        footer {
            margin-top: 48px;
            text-align: center;
            font-size: 0.85rem;
            color: var(--text-muted);
            display: flex;
            flex-direction: column;
            gap: 8px;
            align-items: center;
        }

        .footer-links {
            display: flex;
            gap: 16px;
        }

        .footer-links a {
            color: var(--primary);
            text-decoration: none;
        }
        .footer-links a:hover {
            text-decoration: underline;
        }

        @media (max-width: 640px) {
            .devices-grid {
                grid-template-columns: 1fr;
            }
            .filter-row {
                flex-direction: column;
                align-items: stretch;
            }
            .search-input {
                max-width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand-box">
                <div class="brand-icon">🌐</div>
                <div>
                    <h1 class="brand-title">راصد نشاط الأجهزة والشبكة</h1>
                    <div class="brand-desc">NetFelix Live Device Inspector & Activity Monitor</div>
                </div>
            </div>
            <div class="header-actions">
                <a href="http://192.168.1.15:3000" class="btn" title="العودة للوحة الرئيسية">🏠 لوحة NetFelix</a>
                <a href="http://192.168.1.15:8085/#querylog" target="_blank" class="btn btn-primary" title="سجل استعلامات AdGuard">🛡️ سجل AdGuard المباشر</a>
                <button onclick="fetchData()" class="btn" id="refreshBtn">🔄 تحديث</button>
            </div>
        </header>

        <!-- Stats Overview -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon" style="color: #38bdf8;">📱</div>
                <div>
                    <div class="stat-val" id="totalActiveDevices">-</div>
                    <div class="stat-lbl">أجهزة نشطة ترسل طلبات</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color: #10b981;">📊</div>
                <div>
                    <div class="stat-val" id="totalQueries">-</div>
                    <div class="stat-lbl">إجمالي الاستعلامات المفحوصة</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color: #f59e0b;">🛡️</div>
                <div>
                    <div class="stat-val" id="totalBlocked">-</div>
                    <div class="stat-lbl">إعلانات وتتبع تم حجبها ✅</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="color: #ef4444;">🔞</div>
                <div>
                    <div class="stat-val" id="totalAdult">-</div>
                    <div class="stat-lbl">استعلامات مواقع البالغين (مرصودة)</div>
                </div>
            </div>
        </div>

        <!-- Filter and Search -->
        <div class="filter-row">
            <input type="text" id="searchInput" class="search-input" placeholder="🔍 ابحث بالاسم، الآي بي (IP)، أو الماك (MAC)..." oninput="filterDevices()">
            <div class="live-badge">
                <span class="pulse-dot"></span>
                <span>المراقبة الحية نشطة (تحديث تلقائي كل 10 ثوانٍ)</span>
            </div>
        </div>

        <!-- Grid of Devices -->
        <div class="devices-grid" id="devicesGrid">
            <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
                ⏳ جاري جلب نشاط الأجهزة من شبكة المنزل...
            </div>
        </div>

        <footer>
            <div>NetFelix Smart Ecosystem &copy; 2026 | حماية وتحكم شبكي فائق عبر AdGuard Home</div>
            <div class="footer-links">
                <a href="http://192.168.1.15:3000">لوحة التحكم الرئيسية</a>
                <a href="http://192.168.1.15:8085">إدارة أمان AdGuard</a>
                <a href="http://192.168.1.15:8092/">استوديو التحميل الذكي</a>
            </div>
        </footer>
    </div>

    <script>
        let allDevices = [];

        function getDeviceIcon(type) {
            switch(type) {
                case 'mobile': return '📱';
                case 'laptop': return '💻';
                case 'tv': return '📺';
                case 'router': return '🌐';
                case 'server': return '🖥️';
                default: return '📟';
            }
        }

        async function fetchData() {
            const btn = document.getElementById('refreshBtn');
            if (btn) btn.innerText = '⏳ جاري التحديث...';
            try {
                const res = await fetch('/api/devices/activity');
                const data = await res.json();

                document.getElementById('totalActiveDevices').innerText = data.active_devices_count || 0;
                document.getElementById('totalQueries').innerText = data.total_queries_analyzed || 0;
                document.getElementById('totalBlocked').innerText = data.total_blocked || 0;
                document.getElementById('totalAdult').innerText = data.total_adult_queries || 0;

                allDevices = data.devices || [];
                renderDevices(allDevices);
            } catch (err) {
                console.error('Error fetching devices:', err);
            } finally {
                if (btn) btn.innerText = '🔄 تحديث';
            }
        }

        function renderDevices(devices) {
            const grid = document.getElementById('devicesGrid');
            if (!devices || devices.length === 0) {
                grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">لا توجد أجهزة مطابقة للبحث.</div>';
                return;
            }

            let html = '';
            for (const dev of devices) {
                const icon = getDeviceIcon(dev.type);
                const hasQueries = dev.queries_count > 0;

                let categoriesHtml = '<span style="color: var(--text-muted); font-size: 0.8rem;">لا يوجد نشاط مسجل حديثاً</span>';
                if (dev.top_categories && dev.top_categories.length > 0) {
                    categoriesHtml = dev.top_categories.map(c => {
                        let extraClass = '';
                        if (c.category.includes('بالغين')) extraClass = 'adult';
                        else if (c.category.includes('يوتيوب')) extraClass = 'youtube';
                        return `<span class="tag-pill ${extraClass}">${c.category} <span class="tag-count">${c.count}</span></span>`;
                    }).join('');
                }

                let domainsHtml = '<li style="color: var(--text-muted); font-size: 0.8rem;">لا توجد مواقع مسجلة</li>';
                if (dev.top_domains && dev.top_domains.length > 0) {
                    domainsHtml = dev.top_domains.map(d => {
                        return `<li class="domain-row">
                            <span class="domain-text" title="${d.domain}">${d.domain}</span>
                            <span class="tag-count">${d.count}</span>
                        </li>`;
                    }).join('');
                }

                html += `
                <div class="device-card">
                    <div class="device-header">
                        <div class="device-title-box">
                            <div class="device-icon">${icon}</div>
                            <div>
                                <div class="device-name">${dev.name}</div>
                                <div class="device-vendor">${dev.vendor} ${dev.mac ? '• ' + dev.mac : ''}</div>
                            </div>
                        </div>
                        <div class="ip-badge">${dev.ip}</div>
                    </div>

                    <div class="metrics-row">
                        <div class="metric-item">
                            <span class="metric-num" style="color: ${hasQueries ? '#38bdf8' : '#94a3b8'}">${dev.queries_count}</span>
                            <span class="metric-sub">استعلامات مسجلة</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-num" style="color: ${dev.blocked_count > 0 ? '#10b981' : '#94a3b8'}">${dev.blocked_count}</span>
                            <span class="metric-sub">إعلانات تم حجبها</span>
                        </div>
                    </div>

                    <div>
                        <div class="section-label">أبرز التطبيقات والخدمات:</div>
                        <div class="tags-container">
                            ${categoriesHtml}
                        </div>
                    </div>

                    <div>
                        <div class="section-label">أكثر النطاقات زيارة مؤخراً:</div>
                        <ul class="domains-list">
                            ${domainsHtml}
                        </ul>
                    </div>

                    <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;">
                        ⏰ آخر نشاط: <b>${dev.last_active}</b>
                    </div>

                    <div class="card-actions">
                        <a href="http://192.168.1.15:8085/#querylog?search=${dev.ip}" target="_blank" class="btn btn-card" title="عرض كل المواقع في AdGuard">
                            🔍 سجل الاستعلامات
                        </a>
                        <a href="http://192.168.1.15:8085/#clients" target="_blank" class="btn btn-card" title="تخصيص قواعد الأمان">
                            🛡️ تحكم وحجب
                        </a>
                    </div>
                </div>
                `;
            }

            grid.innerHTML = html;
        }

        function filterDevices() {
            const query = document.getElementById('searchInput').value.trim().toLowerCase();
            if (!query) {
                renderDevices(allDevices);
                return;
            }
            const filtered = allDevices.filter(d =>
                (d.name && d.name.toLowerCase().includes(query)) ||
                (d.ip && d.ip.includes(query)) ||
                (d.mac && d.mac.toLowerCase().includes(query)) ||
                (d.vendor && d.vendor.toLowerCase().includes(query))
            );
            renderDevices(filtered);
        }

        // Initial Load
        fetchData();
        // Auto refresh every 10 seconds
        setInterval(fetchData, 10000);
    </script>
</body>
</html>
"""
