#!/usr/bin/env python3
"""
NetFelix Immich Photo & Folder Share Manager
Allows selecting multiple folders/albums to create a single public view-only link
with downloads blocked (or allowed).
"""

from local_env import load_local_env
load_local_env()
import os
import json
import logging
import urllib.request
import urllib.error
import subprocess
from datetime import datetime

logger = logging.getLogger("PhotoShareManager")

IMMICH_API_KEY = os.environ.get("IMMICH_API_KEY", "")
IMMICH_URL = os.environ.get("IMMICH_INTERNAL_URL", "http://localhost:2283/api")
PUBLIC_SHARE_BASE = os.environ.get("PUBLIC_SHARE_BASE", "https://eslam-photos.duckdns.org/share")

def _request(endpoint, method="GET", data=None):
    url = f"{IMMICH_URL}/{endpoint.lstrip('/')}"
    headers = {
        "x-api-key": IMMICH_API_KEY,
        "Accept": "application/json"
    }
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            resp_bytes = res.read()
            if resp_bytes:
                return json.loads(resp_bytes.decode("utf-8"))
            return None
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        logger.error(f"Immich API HTTP error {e.code} on {endpoint}: {err_msg}")
        raise RuntimeError(f"Immich API error {e.code}: {err_msg}")
    except Exception as e:
        logger.error(f"Immich API request failed on {endpoint}: {e}")
        raise


def get_all_albums():
    """Retrieve all albums with asset counts."""
    data = _request("albums") or []
    # Filter and sort
    albums = []
    for a in data:
        albums.append({
            "id": a.get("id"),
            "name": a.get("albumName", "Untitled"),
            "count": a.get("assetCount", 0),
            "updatedAt": a.get("updatedAt", "")
        })
    # Sort alphabetically case-insensitive
    albums.sort(key=lambda x: x["name"].lower())
    return albums


def get_asset_ids_for_albums(album_ids):
    """Retrieve all asset IDs belonging to the given album IDs using PostgreSQL."""
    if not album_ids:
        return []
    ids_str = ", ".join([f"'{aid}'" for aid in album_ids])
    sql = f'SELECT DISTINCT "assetId" FROM album_asset WHERE "albumId" IN ({ids_str});'
    try:
        proc = subprocess.run(
            ["docker", "exec", "-i", "netfelix-immich-postgres", "psql", "-U", "postgres", "-d", "immich", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0:
            return [line.strip() for line in proc.stdout.split("\n") if line.strip()]
    except Exception as e:
        logger.warning(f"PostgreSQL direct fetch failed ({e}), falling back to API...")

    # Fallback via API
    all_assets = set()
    for aid in album_ids:
        try:
            a_data = _request(f"albums/{aid}")
            for asset in a_data.get("assets", []):
                all_assets.add(asset["id"])
        except Exception:
            pass
    return list(all_assets)


def create_folder_share_link(album_ids, custom_name="", allow_download=False, description=""):
    """
    Creates a view-only (or downloadable) shared link for one or multiple albums.
    If multiple albums, creates a combined album first.
    """
    if not album_ids:
        raise ValueError("No folders selected")

    # Get album names for labeling
    all_albums = {a["id"]: a["name"] for a in get_all_albums()}
    selected_names = [all_albums.get(aid, "Folder") for aid in album_ids]

    target_album_id = None
    created_combined_album = False
    asset_count = 0

    if len(album_ids) == 1:
        target_album_id = album_ids[0]
        album_name = selected_names[0]
        # Query asset count
        assets = get_asset_ids_for_albums([target_album_id])
        asset_count = len(assets)
    else:
        # Multiple albums: gather all assets and create combined album
        asset_ids = get_asset_ids_for_albums(album_ids)
        if not asset_ids:
            raise ValueError("Selected folders contain no photos.")
        asset_count = len(asset_ids)

        if not custom_name or not custom_name.strip():
            # Build smart title
            if len(selected_names) <= 3:
                album_name = " + ".join(selected_names)
            else:
                album_name = f"{selected_names[0]}, {selected_names[1]} & {len(selected_names)-2} more"
            album_name = f"Shared: {album_name}"
        else:
            album_name = custom_name.strip()

        # Create combined album
        new_album = _request("albums", method="POST", data={
            "albumName": album_name,
            "description": f"Combined collection containing: {', '.join(selected_names)}",
            "assetIds": asset_ids
        })
        target_album_id = new_album["id"]
        created_combined_album = True

    # Now create shared link
    desc = description.strip() if description else f"Shared collection of {len(album_ids)} folders"
    sl_data = _request("shared-links", method="POST", data={
        "type": "ALBUM",
        "albumId": target_album_id,
        "allowDownload": bool(allow_download),
        "allowUpload": False,
        "showMetadata": True,
        "description": desc
    })

    key = sl_data.get("key")
    link_id = sl_data.get("id")
    share_url = f"{PUBLIC_SHARE_BASE}/{key}"

    return {
        "success": True,
        "id": link_id,
        "key": key,
        "url": share_url,
        "album_name": album_name,
        "folders_count": len(album_ids),
        "folder_names": selected_names,
        "photos_count": asset_count,
        "allow_download": bool(allow_download)
    }


def list_active_shares():
    """List all current shared links with metadata."""
    data = _request("shared-links") or []
    shares = []
    for sl in data:
        album_info = sl.get("album") or {}
        shares.append({
            "id": sl.get("id"),
            "key": sl.get("key"),
            "url": f"{PUBLIC_SHARE_BASE}/{sl.get('key')}",
            "type": sl.get("type"),
            "title": album_info.get("albumName") or sl.get("description") or "Shared Link",
            "allowDownload": sl.get("allowDownload", False),
            "createdAt": sl.get("createdAt", ""),
            "expiresAt": sl.get("expiresAt"),
            "assetCount": album_info.get("assetCount", len(sl.get("assets", [])))
        })
    # Sort newest first
    shares.sort(key=lambda x: x["createdAt"], reverse=True)
    return shares


def revoke_shared_link(link_id):
    """Delete a shared link."""
    _request(f"shared-links/{link_id}", method="DELETE")
    return {"success": True}


# HTML Frontend
PHOTO_SHARE_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NetFelix Photo Folder Share Manager</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body {
      background: #0b0f19;
      color: #e2e8f0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .folder-card {
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .folder-card:hover {
      transform: translateY(-2px);
      border-color: #3b82f6;
    }
    .folder-card.selected {
      background: rgba(30, 58, 138, 0.35);
      border-color: #3b82f6;
      box-shadow: 0 0 15px rgba(59, 130, 246, 0.25);
    }
    /* Custom scrollbar */
    ::-webkit-scrollbar {
      width: 8px;
    }
    ::-webkit-scrollbar-track {
      background: #0f172a;
    }
    ::-webkit-scrollbar-thumb {
      background: #334155;
      border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #475569;
    }
  </style>
</head>
<body class="min-h-screen pb-16">
  <!-- Navbar -->
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
    <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <a href="http://192.168.1.15:3000" class="text-slate-400 hover:text-white transition">
          <i class="fa-solid fa-arrow-left text-lg"></i>
        </a>
        <div class="flex items-center space-x-2">
          <div class="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-lg">
            <i class="fa-solid fa-folder-open text-base"></i>
          </div>
          <div>
            <h1 class="text-lg font-bold text-white tracking-wide">Folder Share Manager</h1>
            <p class="text-xs text-slate-400">Share multiple folders with 1 view-only link</p>
          </div>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <a href="https://eslam-photos.duckdns.org" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 border border-slate-700 flex items-center gap-1.5 transition">
          <i class="fa-solid fa-images text-indigo-400"></i>
          <span>Open Immich</span>
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-6xl mx-auto px-4 py-6">
    <!-- Top Action Banner -->
    <div class="bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800 rounded-2xl p-5 mb-6 shadow-xl">
      <div class="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
        <div>
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span>Mark Folders to Share</span>
            <span id="selected-badge" class="text-xs bg-blue-600/30 text-blue-400 border border-blue-500/40 px-2 py-0.5 rounded-full font-medium">0 folders selected</span>
          </h2>
          <p class="text-xs text-slate-400 mt-1">Select any number of folders. They will be combined into a single web link without allowing viewers to download.</p>
        </div>

        <div class="flex flex-wrap items-center gap-3 w-full lg:w-auto">
          <!-- Toggle download -->
          <label class="flex items-center gap-2 px-3 py-2 bg-slate-800/80 rounded-xl border border-slate-700 cursor-pointer select-none">
            <input type="checkbox" id="allow-download-toggle" class="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-600 bg-slate-700">
            <span class="text-xs text-slate-300 font-medium flex items-center gap-1.5">
              <i class="fa-solid fa-download text-xs text-amber-400"></i> Allow Download
            </span>
          </label>

          <!-- Create Link Button -->
          <button id="create-link-btn" onclick="openShareModal()" disabled class="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm rounded-xl shadow-lg shadow-blue-600/25 transition flex items-center gap-2">
            <i class="fa-solid fa-share-nodes"></i>
            <span>Create Share Link</span>
          </button>
        </div>
      </div>

      <!-- Quick filters & search -->
      <div class="mt-5 pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div class="relative w-full sm:w-80">
          <i class="fa-solid fa-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs"></i>
          <input type="text" id="search-input" oninput="filterFolders()" placeholder="Search folders (e.g. saaaa7l, قايتباي)..." class="w-full bg-slate-950/60 border border-slate-700 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition">
        </div>

        <div class="flex items-center space-x-2 w-full sm:w-auto justify-end text-xs">
          <button onclick="selectAll()" class="px-2.5 py-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition">Select All</button>
          <span class="text-slate-600">|</span>
          <button onclick="clearAll()" class="px-2.5 py-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition">Clear Selection</button>
        </div>
      </div>
    </div>

    <!-- Folders Grid -->
    <div id="loading-state" class="text-center py-16">
      <i class="fa-solid fa-circle-notch fa-spin text-3xl text-blue-500 mb-3"></i>
      <p class="text-slate-400 text-sm">Loading your photo folders...</p>
    </div>

    <div id="folders-grid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5 hidden">
      <!-- Populated via JS -->
    </div>

    <!-- Active Shares Section -->
    <div class="mt-12">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-bold text-white flex items-center gap-2">
          <i class="fa-solid fa-link text-indigo-400"></i>
          <span>Active Shared Links</span>
        </h3>
        <button onclick="loadActiveShares()" class="text-xs text-slate-400 hover:text-white transition flex items-center gap-1">
          <i class="fa-solid fa-rotate-right"></i> Refresh
        </button>
      </div>
      <div id="active-shares-container" class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg">
        <!-- Populated via JS -->
      </div>
    </div>
  </main>

  <!-- Share Modal -->
  <div id="share-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
      <button onclick="closeShareModal()" class="absolute right-4 top-4 text-slate-400 hover:text-white text-lg">
        <i class="fa-solid fa-xmark"></i>
      </button>

      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-xl bg-blue-600/20 text-blue-400 flex items-center justify-center border border-blue-500/30">
          <i class="fa-solid fa-link text-lg"></i>
        </div>
        <div>
          <h3 class="text-lg font-bold text-white">Generate Shared Link</h3>
          <p class="text-xs text-slate-400">Combine selected folders into 1 public link</p>
        </div>
      </div>

      <div class="space-y-4">
        <div>
          <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Collection Title (Optional)</label>
          <input type="text" id="modal-album-name" placeholder="e.g. Summer Memories, رحلات العائلة" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500">
          <p class="text-[11px] text-slate-500 mt-1">If blank, folder names will be used automatically.</p>
        </div>

        <div class="bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs space-y-2">
          <div class="flex items-center justify-between text-slate-300">
            <span class="text-slate-400">Folders to combine:</span>
            <span id="modal-folder-count" class="font-bold text-white">0</span>
          </div>
          <div class="flex items-center justify-between text-slate-300">
            <span class="text-slate-400">Total photos included:</span>
            <span id="modal-photo-count" class="font-bold text-white">0</span>
          </div>
          <div class="flex items-center justify-between text-slate-300">
            <span class="text-slate-400">Download Permission:</span>
            <span id="modal-download-status" class="font-bold text-emerald-400 flex items-center gap-1">
              <i class="fa-solid fa-ban text-xs"></i> Blocked (View-only)
            </span>
          </div>
        </div>

        <!-- Result Box (Hidden until created) -->
        <div id="modal-result" class="hidden">
          <div class="p-3.5 bg-emerald-950/40 border border-emerald-600/40 rounded-xl space-y-2">
            <div class="text-xs font-bold text-emerald-300 flex items-center gap-1.5">
              <i class="fa-solid fa-check-circle"></i> Link created successfully!
            </div>
            <div class="flex items-center gap-2">
              <input type="text" id="generated-url-input" readonly class="w-full bg-slate-950 text-emerald-300 text-xs font-mono px-3 py-2 rounded-lg border border-emerald-800/50 select-all">
              <button onclick="copyGeneratedUrl()" id="copy-btn" class="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium whitespace-nowrap transition">
                <i class="fa-solid fa-copy mr-1"></i> Copy
              </button>
            </div>
          </div>
          <div class="mt-3 flex justify-end">
            <a id="modal-open-btn" href="#" target="_blank" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-white rounded-lg transition flex items-center gap-1.5">
              <i class="fa-solid fa-arrow-up-right-from-square"></i> Open Link
            </a>
          </div>
        </div>

        <!-- Submit Button -->
        <div id="modal-actions" class="pt-2 flex justify-end gap-2">
          <button onclick="closeShareModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl transition">Cancel</button>
          <button id="modal-confirm-btn" onclick="submitShare()" class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-xl shadow-lg shadow-blue-600/30 transition flex items-center gap-2">
            <i class="fa-solid fa-bolt"></i> Generate Link
          </button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let allAlbums = [];
    const selectedAlbumIds = new Set();

    async function loadFolders() {
      try {
        const res = await fetch('/api/photos/albums');
        const data = await res.json();
        allAlbums = data;
        renderFolders(allAlbums);
        document.getElementById('loading-state').classList.add('hidden');
        document.getElementById('folders-grid').classList.remove('hidden');
      } catch (err) {
        document.getElementById('loading-state').innerHTML = `<p class="text-rose-400">Failed to load folders: ${err.message}</p>`;
      }
    }

    function renderFolders(folders) {
      const container = document.getElementById('folders-grid');
      container.innerHTML = '';
      if (!folders.length) {
        container.innerHTML = '<p class="col-span-full text-center text-slate-500 py-8">No matching folders found.</p>';
        return;
      }

      folders.forEach(f => {
        const isSelected = selectedAlbumIds.has(f.id);
        const card = document.createElement('div');
        card.id = `folder-card-${f.id}`;
        card.className = `folder-card p-3.5 rounded-xl border border-slate-800 bg-slate-900/60 cursor-pointer select-none flex items-start gap-3 ${isSelected ? 'selected' : ''}`;
        card.onclick = () => toggleSelect(f.id);

        card.innerHTML = `
          <input type="checkbox" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation(); toggleSelect('${f.id}')" class="mt-1 w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-700 bg-slate-800 cursor-pointer">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1.5">
              <i class="fa-solid fa-folder text-blue-400 text-sm"></i>
              <h4 class="text-xs font-semibold text-white truncate" title="${f.name}">${f.name}</h4>
            </div>
            <p class="text-[11px] text-slate-400 mt-1">${f.count} ${f.count === 1 ? 'photo' : 'photos'}</p>
          </div>
        `;
        container.appendChild(card);
      });
      updateStats();
    }

    function toggleSelect(id) {
      if (selectedAlbumIds.has(id)) {
        selectedAlbumIds.delete(id);
      } else {
        selectedAlbumIds.add(id);
      }
      const card = document.getElementById(`folder-card-${id}`);
      if (card) {
        card.classList.toggle('selected', selectedAlbumIds.has(id));
        const checkbox = card.querySelector('input[type="checkbox"]');
        if (checkbox) checkbox.checked = selectedAlbumIds.has(id);
      }
      updateStats();
    }

    function selectAll() {
      allAlbums.forEach(a => selectedAlbumIds.add(a.id));
      renderFolders(getFilteredAlbums());
    }

    function clearAll() {
      selectedAlbumIds.clear();
      renderFolders(getFilteredAlbums());
    }

    function getFilteredAlbums() {
      const q = document.getElementById('search-input').value.trim().toLowerCase();
      if (!q) return allAlbums;
      return allAlbums.filter(a => a.name.toLowerCase().includes(q));
    }

    function filterFolders() {
      renderFolders(getFilteredAlbums());
    }

    function updateStats() {
      const count = selectedAlbumIds.size;
      document.getElementById('selected-badge').textContent = `${count} ${count === 1 ? 'folder' : 'folders'} selected`;
      document.getElementById('create-link-btn').disabled = count === 0;
    }

    function openShareModal() {
      if (selectedAlbumIds.size === 0) return;
      const allowDl = document.getElementById('allow-download-toggle').checked;

      let totalPhotos = 0;
      allAlbums.forEach(a => {
        if (selectedAlbumIds.has(a.id)) totalPhotos += a.count;
      });

      document.getElementById('modal-folder-count').textContent = selectedAlbumIds.size;
      document.getElementById('modal-photo-count').textContent = totalPhotos;

      const dlBadge = document.getElementById('modal-download-status');
      if (allowDl) {
        dlBadge.innerHTML = '<i class="fa-solid fa-check text-xs"></i> Allowed';
        dlBadge.className = 'font-bold text-amber-400 flex items-center gap-1';
      } else {
        dlBadge.innerHTML = '<i class="fa-solid fa-ban text-xs"></i> Blocked (View-only)';
        dlBadge.className = 'font-bold text-emerald-400 flex items-center gap-1';
      }

      document.getElementById('modal-result').classList.add('hidden');
      document.getElementById('modal-actions').classList.remove('hidden');
      document.getElementById('share-modal').classList.remove('hidden');
    }

    function closeShareModal() {
      document.getElementById('share-modal').classList.add('hidden');
    }

    async function submitShare() {
      const btn = document.getElementById('modal-confirm-btn');
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';

      const customName = document.getElementById('modal-album-name').value.trim();
      const allowDownload = document.getElementById('allow-download-toggle').checked;
      const albumIds = Array.from(selectedAlbumIds);

      try {
        const res = await fetch('/api/photos/share', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: json_stringify = JSON.stringify({
            albumIds: albumIds,
            customName: customName,
            allowDownload: allowDownload
          })
        });

        const data = await res.json();
        if (!data.success) throw new Error(data.error || 'Failed to generate link');

        document.getElementById('generated-url-input').value = data.url;
        document.getElementById('modal-open-btn').href = data.url;
        document.getElementById('modal-result').classList.remove('hidden');
        document.getElementById('modal-actions').classList.add('hidden');
        loadActiveShares();
      } catch (err) {
        alert('Error: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Generate Link';
      }
    }

    function copyGeneratedUrl() {
      const input = document.getElementById('generated-url-input');
      input.select();
      navigator.clipboard.writeText(input.value);
      const copyBtn = document.getElementById('copy-btn');
      copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
      setTimeout(() => {
        copyBtn.innerHTML = '<i class="fa-solid fa-copy"></i> Copy';
      }, 2000);
    }

    async function loadActiveShares() {
      const container = document.getElementById('active-shares-container');
      try {
        const res = await fetch('/api/photos/shares');
        const data = await res.json();
        if (!data || !data.length) {
          container.innerHTML = '<div class="p-6 text-center text-xs text-slate-500">No active shared links found.</div>';
          return;
        }

        let html = '<div class="divide-y divide-slate-800/80">';
        data.forEach(s => {
          const dateStr = s.createdAt ? new Date(s.createdAt).toLocaleDateString() : '';
          html += `
            <div class="p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 hover:bg-slate-850/50 transition">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <h4 class="text-xs font-bold text-white truncate">${s.title}</h4>
                  <span class="text-[10px] px-2 py-0.5 rounded-full font-medium ${s.allowDownload ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'}">
                    ${s.allowDownload ? 'Download Allowed' : 'View Only (No Download)'}
                  </span>
                </div>
                <div class="flex items-center gap-3 text-[11px] text-slate-400 mt-1">
                  <span>${s.assetCount} photos</span>
                  <span>•</span>
                  <span>Created ${dateStr}</span>
                </div>
              </div>
              <div class="flex items-center gap-2 self-end sm:self-center">
                <button onclick="navigator.clipboard.writeText('${s.url}'); alert('Link copied to clipboard!');" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 rounded-lg transition flex items-center gap-1">
                  <i class="fa-solid fa-copy"></i> Copy
                </button>
                <a href="${s.url}" target="_blank" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-blue-400 rounded-lg transition flex items-center gap-1">
                  <i class="fa-solid fa-external-link"></i> Open
                </a>
                <button onclick="revokeShare('${s.id}')" class="px-2 py-1.5 hover:bg-rose-950/60 text-slate-500 hover:text-rose-400 text-xs rounded-lg transition" title="Revoke Link">
                  <i class="fa-solid fa-trash-can"></i>
                </button>
              </div>
            </div>
          `;
        });
        html += '</div>';
        container.innerHTML = html;
      } catch (err) {
        container.innerHTML = `<div class="p-4 text-xs text-rose-400">Error loading shares: ${err.message}</div>`;
      }
    }

    async function revokeShare(id) {
      if (!confirm('Are you sure you want to revoke this shared link? Anyone using it will immediately lose access.')) return;
      try {
        const res = await fetch(`/api/photos/shares/${id}`, {method: 'DELETE'});
        const data = await res.json();
        if (data.success) {
          loadActiveShares();
        } else {
          alert('Failed to revoke link: ' + (data.error || 'Unknown error'));
        }
      } catch (err) {
        alert('Error: ' + err.message);
      }
    }

    // Init
    loadFolders();
    loadActiveShares();
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    albums = get_all_albums()
    print(f"Loaded {len(albums)} albums from Immich.")
