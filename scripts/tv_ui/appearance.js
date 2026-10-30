(function () {
    'use strict';
    var revision = -1, busy = false, dockSignature = '', previewMode = location.pathname === '/tv-preview';
    var actions = {
        jellyfin: function () { launchApp('jellyfin'); }, iptv: function () { openLiveTV(); },
        youtube: function () { launchApp('youtube'); }, netflix: function () { launchApp('netflix'); },
        prayer: function () { openPrayerHub(); }, radio: function () { toggleQuranRadio(); },
        matches: function () { scrollToMatches(); }, search: function () { openSearchModal(); }
    };
    function apply(state) {
        var s = state.displaySettings || state.settings, theme = state.themes.filter(function(t) { return t.id === s.theme; })[0];
        if (!theme) return;
        window.NetFelixAppearance = s;
        var trialBadge = document.getElementById('nf-trial-badge');
        if (!trialBadge && !previewMode) {
            trialBadge = document.createElement('div'); trialBadge.id = 'nf-trial-badge';
            trialBadge.setAttribute('role','status'); document.body.appendChild(trialBadge);
        }
        if (trialBadge) {
            trialBadge.hidden = !state.trial;
            trialBadge.textContent = state.trial ? 'Temporary TV preview · restores automatically after 30 seconds' : '';
        }
        var body = document.body;
        body.style.setProperty('--nf-accent', s.accent || theme.primary);
        body.style.setProperty('--nf-scene', theme.secondary);
        body.style.setProperty('--nf-artwork', 'url("' + theme.artwork + '")');
        body.style.setProperty('--nf-text-scale', {small: .9, normal: 1, large: 1.15}[s.textSize]);
        body.style.setProperty('--nf-wallpaper', s.wallpaper ? 'url("' + s.wallpaper + '")' : 'none');
        ['motion','blur','glow','prayer','weather'].forEach(function(key) {
            var value = key === 'prayer' ? s.showPrayer : key === 'weather' ? s.showWeather : s[key];
            body.setAttribute('data-nf-' + key, String(value));
        });
        body.setAttribute('data-nf-theme', s.theme);
        body.setAttribute('data-nf-tiles', s.tileSize || 'normal');
        body.setAttribute('data-nf-menu', s.menuPosition || 'left');
        body.setAttribute('data-nf-icons', NetFelixVisuals.iconStyle(s,theme));
        body.classList.add('nf-ready');
        document.querySelector('.hero-headline').textContent = s.title;
        document.querySelector('.hero-desc').textContent = s.subtitle;
        var title = document.querySelector('.hero-headline');
        title.dir = 'auto'; document.querySelector('.hero-desc').dir = 'auto';
        var tagline = document.querySelector('.hero-tagline span');
        if (tagline) tagline.textContent = state.profiles.filter(function(p) { return p.id === state.activeProfile; })[0].name.toUpperCase() + ' · NETFELIX';
        var dock = document.querySelector('.tvm-bottom-dock');
        var signature = JSON.stringify(s.favorites);
        if (dock && dockSignature !== signature) {
            var activeId = document.activeElement.getAttribute('data-nf-app');
            var hadDockFocus = dock.contains(document.activeElement);
            dock.textContent = '';
            s.favorites.forEach(function(id) {
                var button = document.createElement('button');
                button.className = 'dock-app-card focusable'; button.tabIndex = 0;
                button.setAttribute('data-nf-app', id);
                button.setAttribute('aria-label', state.apps[id]);
                button.onclick = actions[id];
                var icon = document.createElement('span'); icon.className = 'dock-icon'; icon.appendChild(NetFelixVisuals.icon(id));
                var label = document.createElement('span'); label.className = 'dock-app-name'; label.textContent = state.apps[id];
                button.appendChild(icon); button.appendChild(label); dock.appendChild(button);
            });
            var customize = document.createElement('button'); customize.className = 'dock-app-card focusable';
            customize.setAttribute('aria-label','✦ Appearance');
            customize.appendChild(NetFelixVisuals.icon('appearance'));
            var customizeLabel = document.createElement('span'); customizeLabel.className = 'dock-app-name'; customizeLabel.textContent = 'Appearance';
            customize.appendChild(customizeLabel); customize.onclick = function() { location.href = '/tv-customize?tv=1'; };
            dock.appendChild(customize);
            var anchor = document.getElementById('matches-section-anchor');
            if (anchor) anchor.parentNode.insertBefore(dock, anchor);
            dockSignature = signature;
            if (!previewMode) refreshFocusables();
            if (!previewMode && hadDockFocus) {
                var restore = dock.querySelector('[data-nf-app="' + activeId + '"]') || dock.firstElementChild;
                restore.focus();
            }
        }
        var recent = document.querySelector('.recent-grid');
        if (recent && recent.previousElementSibling) recent.previousElementSibling.classList.add('nf-recent-heading');
        document.querySelectorAll('.left-vertical-dock .sidebar-btn').forEach(function(button) {
            var action = button.getAttribute('onclick') || '';
            var id = action.indexOf('Prayer') >= 0 ? 'prayer' : action.indexOf('jellyfin') >= 0 ? 'jellyfin' :
                action.indexOf('LiveTV') >= 0 ? 'iptv' : action.indexOf('Matches') >= 0 ? 'matches' : action.indexOf('youtube') >= 0 ? 'youtube' : 'radio';
            var glyph = button.querySelector('.s-icon');
            if (glyph && !glyph.querySelector('svg')) { glyph.textContent = ''; glyph.appendChild(NetFelixVisuals.icon(id)); }
        });
        var navIcons = ['home','iptv','jellyfin','series','matches','prayer','radio'];
        var navLabels = ['Home','Live TV','Movies','Series','Matches','Prayer Hub','Quran Radio'];
        document.querySelectorAll('.tvm-nav-tabs .nav-tab').forEach(function(tab,index) {
            if (!navIcons[index] || tab.querySelector('svg')) return;
            tab.textContent = ''; tab.appendChild(NetFelixVisuals.icon(navIcons[index]));
            var label = document.createElement('span'); label.textContent = navLabels[index]; tab.appendChild(label);
        });
        if (!previewMode) {
            refreshFocusables();
            if (focusableElements.indexOf(document.activeElement) < 0) setFocus(0);
        }
        if (previewMode) {
            document.querySelectorAll('.focused').forEach(function(el) { el.classList.remove('focused'); });
        }
    }
    async function sync() {
        if (busy || document.hidden) return;
        busy = true;
        try {
            var response = await fetch('/api/tv/appearance', {cache: 'no-store'});
            if (!response.ok) return;
            var state = await response.json();
            if ((state.displayRevision || state.revision) !== revision) { apply(state); revision = state.displayRevision || state.revision; }
        } catch (error) { /* Keep the last displayed appearance during a network interruption. */ }
        finally { busy = false; }
    }
    if (previewMode) {
        clearTimeout(screensaverTimer);
        document.body.classList.add('nf-preview-mode');
        window.addEventListener('message',function(event) {
            if (event.source !== parent || event.origin !== location.origin || !event.data || event.data.type !== 'netfelix-preview') return;
            apply(event.data.state);
            parent.postMessage({type:'netfelix-preview-rendered',theme:event.data.state.settings.theme},location.origin);
        });
        parent.postMessage({type:'netfelix-preview-ready'},location.origin);
    } else {
        sync(); setInterval(sync, 1500);
        document.addEventListener('visibilitychange', sync);
    }
}());
