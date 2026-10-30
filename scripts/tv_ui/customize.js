(function () {
    'use strict';
    var state, draft, category = 'All', dirty = false, pending = false, lockedControls = [], pollError = false, pollBusy = false;
    var $ = function(id) { return document.getElementById(id); };
    var categories = {
        Simple: ['blue','night','emerald','amber','violet'],
        Islamic: ['islamic-makkah','islamic-madinah','islamic-quds'],
        Cinema: ['blue-cinema'], Gaming: ['gta6'],
        'Egyptian clubs': ['ahly','zamalek','ismaily'],
        'World clubs': ['madrid','barcelona','ac-milan-legends','inter-miami'],
        'Saudi Arabia': ['king-salman','crown-prince','nassr','hilal','ittihad','ahli-saudi'],
        'National teams': ['egypt','argentina','portugal'],
        Sports: ['basketball','baseball','montreal','toronto'],
        Patriotic: ['saudi-national','egypt-national']
    };
    function message(text, error) { $('status').textContent = text; $('status').className = error ? 'error' : ''; }
    async function request(path, body) {
        var timeout;
        try {
            return await Promise.race([
                (async function() {
                    var response = await fetch(path, body === undefined ? {cache:'no-store'} : {
                        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
                    });
                    var value = await response.json();
                    if (!response.ok) {
                        if (response.status === 409) $('reload').className = 'visible';
                        throw new Error(value.error || 'The server could not save your changes');
                    }
                    return value;
                }()),
                new Promise(function(resolve,reject) {
                    timeout = setTimeout(function() {
                        $('reload').className = 'visible';
                        reject(new Error('Request timed out. It may have reached the TV; load latest before retrying.'));
                    },12000);
                })
            ]);
        } finally {
            clearTimeout(timeout);
        }
    }
    function setPending(value) {
        if (value && !pending) {
            lockedControls = Array.from(document.querySelectorAll('#editor button,#editor input,#editor select')).map(function(el) {
                var previous = [el, el.disabled]; el.disabled = true; return previous;
            });
        } else if (!value) {
            lockedControls.forEach(function(pair) { if (pair[0].isConnected) pair[0].disabled = pair[1]; });
            lockedControls = [];
        }
        pending = value;
        $('save').disabled = value || !state;
        $('create-profile').disabled = value;
        $('profile').disabled = value;
        $('wallpaper').disabled = value;
        $('clear-wallpaper').disabled = value;
        $('reset').disabled = value;
    }
    function preview() {
        var theme = state.themes.filter(function(t) { return t.id === draft.theme; })[0];
        document.documentElement.style.setProperty('--accent', draft.accent || theme.primary);
        document.documentElement.style.setProperty('--scene', theme.secondary);
        document.documentElement.style.setProperty('--nf-accent', draft.accent || theme.primary);
        $('preview').style.setProperty('--wallpaper', draft.wallpaper ? 'url("' + draft.wallpaper + '")' : 'none');
        $('preview-title').textContent = draft.title;
        $('preview-subtitle').textContent = draft.subtitle;
        $('preview-theme').textContent = theme.name;
        document.querySelector('.preview-meta span').textContent = dirty ? 'Unsaved preview' : 'Saved appearance';
        $('photo-override').hidden = !draft.wallpaper;
        var scale = draft.textSize === 'large' ? 1.15 : draft.textSize === 'small' ? .9 : 1;
        $('preview-title').style.fontSize = (30 * scale) + 'px';
        $('preview-subtitle').style.fontSize = (16 * scale) + 'px';
        var frame = $('tv-preview');
        frame.contentWindow.postMessage({type:'netfelix-preview',state:Object.assign({},state,{settings:draft,displaySettings:null,trial:null})},location.origin);
        $('icon-samples').setAttribute('data-nf-icons', NetFelixVisuals.iconStyle(draft,theme));
        $('icon-samples').textContent = '';
        (draft.favorites.length ? draft.favorites : ['jellyfin','iptv','youtube','netflix']).slice(0,5).forEach(function(id) {
            var face = document.createElement('span'); face.className = 'dock-app-card'; face.title = state.apps[id];
            face.appendChild(NetFelixVisuals.icon(id)); $('icon-samples').appendChild(face);
        });
        resizePreview();
    }
    function resizePreview() {
        if ($('preview-shell').classList.contains('expanded')) {
            var width = Math.max(1,Math.min(innerWidth - 48,(innerHeight - 210)*16/9));
            $('preview').style.width = width + 'px';
            $('preview').style.height = (width * 9/16) + 'px';
        } else {
            $('preview').style.width = '';
            $('preview').style.height = '';
        }
        $('tv-preview').style.transform = 'scale(' + ($('preview').clientWidth / 1920) + ')';
    }
    window.addEventListener('resize',resizePreview);
    if (window.ResizeObserver) new ResizeObserver(resizePreview).observe($('preview'));
    $('tv-preview').addEventListener('load',function() { if (state) preview(); });
    window.addEventListener('message',function(event) {
        if (event.source !== $('tv-preview').contentWindow || event.origin !== location.origin || !event.data) return;
        if (event.data.type === 'netfelix-preview-ready' && state) preview();
        if (event.data.type === 'netfelix-preview-rendered') $('preview').setAttribute('data-rendered-theme',event.data.theme);
    });
    $('expand-preview').onclick = function() {
        var expanded = $('preview-shell').classList.toggle('expanded');
        $('expand-preview').textContent = expanded ? 'Close preview' : 'Expand preview';
        $('expand-preview').setAttribute('aria-expanded',String(expanded));
        resizePreview();
    };
    document.addEventListener('keydown',function(event) {
        if ((event.keyCode === 27 || event.keyCode === 10009) && $('preview-shell').classList.contains('expanded')) {
            event.preventDefault(); event.stopImmediatePropagation(); $('expand-preview').click();
        }
    },true);
    function changed() { dirty = true; preview(); message('Preview ready. Apply to TV to save your changes.'); }
    function themes() {
        $('themes').textContent = '';
        state.themes.filter(function(t) { return category === 'All' || categories[category].indexOf(t.id) >= 0; }).forEach(function(t) {
            var button = document.createElement('button'); button.className = 'theme';
            button.style.setProperty('--card-scene', t.secondary); button.style.setProperty('--card-accent', t.primary);
            button.setAttribute('aria-pressed', String(t.id === draft.theme)); button.setAttribute('data-theme',t.id);
            button.setAttribute('aria-label',t.name);
            var shot = document.createElement('div'); shot.className = 'theme-shot';
            shot.style.backgroundImage = 'url("' + t.artwork + '")';
            shot.setAttribute('data-nf-icons',NetFelixVisuals.iconStyle(draft,t));
            var nav = document.createElement('span'); nav.className = 'mini-nav'; nav.textContent = 'NETFELIX     HOME   YOUR APPS';
            var headline = document.createElement('span'); headline.className = 'mini-title'; headline.textContent = 'Your TV. Your world.';
            var dock = document.createElement('div'); dock.className = 'mini-dock';
            ['jellyfin','iptv','youtube','netflix'].forEach(function(id) {
                var face = document.createElement('span'); face.className = 'dock-app-card';
                face.appendChild(NetFelixVisuals.icon(id)); dock.appendChild(face);
            });
            shot.appendChild(nav); shot.appendChild(headline); shot.appendChild(dock);
            var name = document.createElement('span'); name.className = 'theme-name'; name.textContent = t.name;
            var treatment = document.createElement('small'); treatment.textContent = {glass:'Glass',solid:'Colorful',outline:'Outline'}[NetFelixVisuals.iconStyle(draft,t)] + ' icons';
            button.appendChild(shot); button.appendChild(name); button.appendChild(treatment);
            button.onclick = function() {
                draft.theme = t.id;
                if ($('theme-accent').checked) $('accent').value = t.primary;
                themes(); changed(); $('themes').querySelector('[data-theme="' + t.id + '"]').focus();
            };
            $('themes').appendChild(button);
        });
    }
    function filters() {
        $('filters').textContent = '';
        ['All'].concat(Object.keys(categories)).forEach(function(name) {
            var button = document.createElement('button'); button.textContent = name; button.className = 'theme-filter';
            button.setAttribute('aria-pressed', String(category === name));
            button.onclick = function() {
                category = name; filters(); themes();
                Array.from($('filters').children).filter(function(el) { return el.textContent === name; })[0].focus();
            };
            $('filters').appendChild(button);
        });
    }
    function favorites() {
        $('favorites').textContent = '';
        var order = draft.favorites.concat(Object.keys(state.apps).filter(function(id) { return draft.favorites.indexOf(id) < 0; }));
        order.forEach(function(id) {
            var row = document.createElement('div'); row.className = 'favorite';
            var check = document.createElement('input'); check.type = 'checkbox'; check.checked = draft.favorites.indexOf(id) >= 0;
            check.setAttribute('aria-label','Show ' + state.apps[id] + ' in dock');
            check.onchange = function() {
                draft.favorites = draft.favorites.filter(function(item) { return item !== id; });
                if (check.checked) draft.favorites.push(id);
                changed(); favorites();
                $('favorites').querySelector('[data-favorite="' + id + '"] input').focus();
            };
            var label = document.createElement('strong'); label.textContent = state.apps[id];
            row.setAttribute('data-favorite', id);
            row.appendChild(check); row.appendChild(label);
            [-1,1].forEach(function(delta) {
                var button = document.createElement('button'); button.className = 'secondary'; button.textContent = delta < 0 ? '↑' : '↓';
                button.setAttribute('aria-label','Move ' + state.apps[id] + (delta < 0 ? ' up' : ' down'));
                var index = draft.favorites.indexOf(id);
                button.disabled = index < 0 || index + delta < 0 || index + delta >= draft.favorites.length;
                button.onclick = function() {
                    draft.favorites.splice(index,1); draft.favorites.splice(index + delta,0,id); changed(); favorites();
                    var row = $('favorites').querySelector('[data-favorite="' + id + '"]');
                    var buttons = row.querySelectorAll('button');
                    var target = buttons[delta < 0 ? 0 : 1];
                    if (target.disabled) target = row.querySelector('input');
                    target.focus();
                };
                row.appendChild(button);
            });
            $('favorites').appendChild(row);
        });
    }
    function populate(value) {
        state = value; draft = JSON.parse(JSON.stringify(value.settings)); dirty = false;
        $('profile').textContent = '';
        state.profiles.forEach(function(p) {
            var option = document.createElement('option'); option.value = p.id; option.textContent = p.name;
            option.selected = p.id === state.activeProfile; $('profile').appendChild(option);
        });
        ['title','subtitle','textSize','iconStyle','tileSize','menuPosition'].forEach(function(k) { $(k).value = draft[k]; });
        ['motion','blur','glow','clock24','showPrayer','showWeather'].forEach(function(k) { $(k).checked = draft[k]; });
        var theme = state.themes.filter(function(t) { return t.id === draft.theme; })[0];
        $('accent').value = draft.accent || theme.primary; $('theme-accent').checked = !draft.accent;
        $('editor').hidden = false; $('reload').className = '';
        filters(); themes(); favorites(); preview(); renderDesigns(); setPending(false);
    }
    async function save() {
        if (pending || !state) return;
        setPending(true);
        try {
            populate(await request('/api/tv/appearance',{patch:draft,profile:state.activeProfile,revision:state.revision}));
            message('Saved. Your TV will update within two seconds.');
        } catch (error) { message(error.message,true); }
        finally { setPending(false); }
    }
    function renderDesigns() {
        ['preset-list','schedule-preset'].forEach(function(id) {
            var select = $(id), previous = select.value;
            select.textContent = '';
            (state.presets || []).forEach(function(p) {
                var option = document.createElement('option'); option.value = p.id; option.textContent = p.name;
                select.appendChild(option);
            });
            if (Array.from(select.options).some(function(o) { return o.value === previous; })) select.value = previous;
        });
        $('schedule-list').textContent = '';
        (state.schedules || []).filter(function(r) { return r.profile === state.activeProfile; }).forEach(function(r) {
            var preset = (state.presets || []).filter(function(p) { return p.id === r.preset; })[0];
            var row = document.createElement('div'); row.className = 'favorite';
            var label = document.createElement('span');
            label.textContent = (preset ? preset.name : 'Design') + ' · ' + r.start + '–' + r.end + ' · ' + r.days.map(function(d) { return ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d]; }).join(', ') + ' · ' + r.timezone + (r.startsOn || r.endsOn ? ' · ' + (r.startsOn || 'any date') + ' to ' + (r.endsOn || 'ongoing') : '');
            var remove = document.createElement('button'); remove.className = 'secondary'; remove.textContent = 'Remove';
            remove.onclick = function() { manage('schedules',{action:'delete',id:r.id}); };
            row.appendChild(label); row.appendChild(remove); $('schedule-list').appendChild(row);
        });
    }
    // Auxiliary changes preserve the unsaved editor draft.
    async function manage(kind, body) {
        if (!state || pending) return;
        setPending(true);
        try {
            body.revision = state.revision;
            var value = await request('/api/tv/appearance/' + kind, body);
            if ((kind === 'presets' && body.action === 'restore') || (kind === 'trial' && body.action === 'keep')) populate(value);
            else { state = value; renderDesigns(); }
            message('Done.');
        } catch (error) { message(error.message,true); }
        finally { setPending(false); }
    }
    $('try-tv').onclick = function() { manage('trial',{action:'start',settings:draft}); };
    $('keep-trial').onclick = function() { if (state.trial) manage('trial',{action:'keep',id:state.trial.id}); };
    $('restore-trial').onclick = function() { if (state.trial) manage('trial',{action:'restore',id:state.trial.id}); };
    setInterval(function() {
        var remaining = state && state.trial ? Math.max(0,Math.ceil(state.trial.expires - Date.now()/1000)) : 0;
        $('trial-status').textContent = remaining ? 'TV preview · ' + remaining + ' seconds remaining' : 'TV preview inactive';
        $('keep-trial').disabled = pending || !remaining;
        $('restore-trial').disabled = pending || !remaining;
        $('try-tv').disabled = pending || !state || !!remaining;
    },250);
    $('save-preset').onclick = function() { manage('presets',{action:'save',name:$('preset-name').value,settings:draft}); };
    $('restore-preset').onclick = function() {
        if (dirty && !confirm('Apply this preset and discard unapplied changes?')) return;
        manage('presets',{action:'restore',id:$('preset-list').value});
    };
    $('duplicate-preset').onclick = function() { manage('presets',{action:'duplicate',id:$('preset-list').value,name:$('preset-name').value}); };
    $('delete-preset').onclick = function() { manage('presets',{action:'delete',id:$('preset-list').value}); };
    $('export-preset').onclick = function() {
        var preset = (state.presets || []).filter(function(p) { return p.id === $('preset-list').value; })[0];
        if (!preset) return message('Choose a saved design first.',true);
        var link = document.createElement('a');
        link.href = '/api/tv/appearance/export/' + encodeURIComponent(preset.id); link.download = 'netfelix-design.json'; link.click();
    };
    $('import-preset').onchange = async function() {
        var file = this.files[0];
        try {
            if (!file || file.size > 5700000) throw new Error('Choose a design JSON smaller than 5.7 MB');
            var text = await new Promise(function(resolve,reject) { var reader = new FileReader(); reader.onload = function() { resolve(reader.result); }; reader.onerror = reject; reader.readAsText(file); });
            var design = JSON.parse(text);
            if (design.format !== 'netfelix-design' || design.version !== 1) throw new Error('Unsupported design file');
            await manage('presets',{action:'import',name:design.name,settings:design.settings,wallpaperImage:design.wallpaperImage});
        } catch (error) { message(error.message,true); }
        this.value = '';
    };
    ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].forEach(function(day,index) {
        var label = document.createElement('label'), check = document.createElement('input');
        check.type = 'checkbox'; check.value = index; check.checked = true;
        label.appendChild(check); label.appendChild(document.createTextNode(day)); $('schedule-days').appendChild(label);
    });
    $('add-schedule').onclick = function() {
        manage('schedules',{action:'save',preset:$('schedule-preset').value,start:$('schedule-start').value,
            end:$('schedule-end').value,timezone:$('schedule-zone').value,startsOn:$('schedule-date-start').value,endsOn:$('schedule-date-end').value,
            days:Array.from($('schedule-days').querySelectorAll('input:checked')).map(function(c) { return Number(c.value); })});
    };
    $('save').onclick = save;
    ['title','subtitle','textSize','iconStyle','tileSize','menuPosition'].forEach(function(k) { $(k).addEventListener('input',function() { draft[k] = $(k).value; changed(); if (k === 'iconStyle') themes(); }); });
    ['motion','blur','glow','clock24','showPrayer','showWeather'].forEach(function(k) { $(k).onchange = function() { draft[k] = $(k).checked; changed(); }; });
    $('accent').oninput = function() { $('theme-accent').checked = false; draft.accent = $('accent').value; changed(); };
    $('theme-accent').onchange = function() { draft.accent = $('theme-accent').checked ? '' : $('accent').value; changed(); };
    $('reset').onclick = function() { populate(Object.assign({},state,{settings:state.defaults})); changed(); };
    $('clear-wallpaper').onclick = function() { draft.wallpaper = ''; changed(); };
    $('use-scene-background').onclick = $('clear-wallpaper').onclick;
    $('profile').onchange = async function() {
        if (pending) return;
        var id = $('profile').value;
        if (dirty && !confirm('Switch profile and discard unapplied changes?')) { $('profile').value = state.activeProfile; return; }
        setPending(true);
        try { populate(await request('/api/tv/appearance/profile',{action:'select',profile:id})); message('Profile selected on TV.'); }
        catch (error) { $('profile').value = state.activeProfile; message(error.message,true); }
        finally { setPending(false); }
    };
    $('create-profile').onclick = async function() {
        if (pending) return;
        if (dirty && !confirm('Create a profile and discard unapplied changes?')) return;
        setPending(true);
        try { populate(await request('/api/tv/appearance/profile',{action:'create',name:$('new-profile').value})); $('new-profile').value = ''; message('Profile created and selected on TV.'); }
        catch (error) { message(error.message,true); }
        finally { setPending(false); }
    };
    $('wallpaper').onchange = async function() {
        var file = $('wallpaper').files[0]; if (!file || pending) return;
        if (file.size > 4*1024*1024 || ['image/jpeg','image/png','image/webp'].indexOf(file.type) < 0) {
            message('Choose a JPEG, PNG or WebP smaller than 4 MB.',true); $('wallpaper').value = ''; return;
        }
        setPending(true); message('Uploading your photo…');
        try {
            var encoded = await new Promise(function(resolve,reject) {
                var reader = new FileReader(); reader.onload = function() { resolve(reader.result.split(',')[1]); }; reader.onerror = reject; reader.readAsDataURL(file);
            });
            var value = await request('/api/tv/appearance/upload',{image:encoded,profile:state.activeProfile,revision:state.revision});
            draft.wallpaper = value.settings.wallpaper; state.revision = value.revision;
            preview(); message('Photo applied to the TV. Other edits still need Apply.');
        } catch (error) { message(error.message || 'Photo upload failed',true); }
        finally { $('wallpaper').value = ''; setPending(false); }
    };
    async function load() {
        if (pending) return;
        setPending(true);
        try { populate(await request('/api/tv/appearance')); message('Connected. Changes apply to the active TV profile.'); }
        catch (error) { message('Could not connect. Check the server address and try again.',true); $('reload').className = 'visible'; }
        finally { setPending(false); }
    }
    $('reload').onclick = function() { if (!dirty || confirm('Discard unapplied changes and load the TV settings?')) load(); };
    setInterval(async function() {
        if (!state || pending || pollBusy || document.hidden) return;
        pollBusy = true;
        var requestedRevision = state.revision;
        try {
            var value = await request('/api/tv/appearance');
            if (pollError) {
                pollError = false;
                message(dirty ? 'Connection restored. Your unapplied draft is kept.' : 'Connected. TV settings are up to date.');
            }
            if (!pending) state.trial = value.trial;
            if (pending || state.revision !== requestedRevision || value.revision === state.revision) return;
            if (!dirty) { populate(value); message('Synced with TV.'); }
            else { $('reload').className = 'visible'; message('TV settings changed elsewhere. Load latest before applying your draft.'); }
        } catch (error) {
            pollError = true;
            if (!pending) message('Connection lost. Your draft is kept; reconnect before applying.',true);
        } finally { pollBusy = false; }
    },4000);
    if (new URLSearchParams(location.search).get('tv') === '1') {
        document.addEventListener('keydown',function(event) {
            var key = event.keyCode;
            if (key === 13 && document.activeElement.type === 'checkbox') {
                event.preventDefault();
                document.activeElement.click();
                return;
            }
            if (key === 10009 || key === 27) {
                event.preventDefault();
                if (!dirty || confirm('Discard unapplied changes and return to TV?')) location.href = '/tv-dashboard';
                return;
            }
            if ([37,38,39,40].indexOf(key) < 0) return;
            var active = document.activeElement;
            if ((active.tagName === 'INPUT' && active.type !== 'checkbox' && (key === 37 || key === 39)) ||
                (active.tagName === 'SELECT' && (key === 38 || key === 40))) return;
            var controls = Array.from(document.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),a[href]')).filter(function(el) { return el.getClientRects().length; });
            var rect = active.getBoundingClientRect(), best, score = Infinity;
            controls.forEach(function(el) {
                if (el === active) return;
                var candidate = el.getBoundingClientRect();
                var x = candidate.left + candidate.width/2 - rect.left - rect.width/2;
                var y = candidate.top + candidate.height/2 - rect.top - rect.height/2;
                var forward = key === 37 ? -x : key === 39 ? x : key === 38 ? -y : y;
                var cross = key === 37 || key === 39 ? Math.abs(y) : Math.abs(x);
                if (forward > 0 && forward + cross*3 < score) { best = el; score = forward + cross*3; }
            });
            event.preventDefault();
            var next = best || controls[0];
            if (next) { next.focus(); next.scrollIntoView({block:'center'}); }
        });
    }
    var statusBusy = false;
    async function checkConnection() {
        if (statusBusy || document.hidden) return;
        statusBusy = true;
        try {
            var values = await Promise.all([request('/api/tv/companion/info'),request('/api/tv/status')]);
            $('connection-state').textContent = 'Server connected · NetFelix Home ' + (values[0].dashboardOnline ? 'open' : 'not open') + ' · Samsung TV ' + (values[1].online ? 'online' : 'unreachable') + (values[1].token_paired ? ' · paired' : ' · pairing needed');
        } catch (error) { $('connection-state').textContent = 'Server unreachable. Check Wi-Fi and server address, then reconnect.'; }
        finally { statusBusy = false; }
    }
    $('reconnect-status').onclick = checkConnection;
    async function remote(body) {
        body.target = ['VOLUP','VOLDOWN','MUTE'].indexOf(body.key) >= 0 ? 'samsung' : $('remote-target').value;
        try {
            var value = await request('/api/tv/companion/control',body);
            if (!value.success) throw new Error(value.error || 'TV command failed');
            $('remote-status').textContent = value.message || 'Command sent to Samsung TV';
        } catch (error) { $('remote-status').textContent = error.message; }
    }
    [['HOME','Home'],['UP','↑'],['RETURN','Back'],['LEFT','←'],['ENTER','OK'],['RIGHT','→'],['VOLUP','Vol +'],['DOWN','↓'],['VOLDOWN','Vol −'],['REWIND','−10s'],['PLAY','Play'],['FF','+10s'],['MUTE','Mute'],['PAUSE','Pause'],['STOP','Stop']].forEach(function(pair) {
        var button = document.createElement('button'); button.className = 'secondary'; button.textContent = pair[1];
        button.setAttribute('aria-label','Remote ' + pair[0]);
        button.onclick = function() { remote({kind:'key',key:pair[0]}); };
        $('remote-pad').appendChild(button);
    });
    $('send-text').onclick = function() { remote({kind:'text',text:$('remote-text').value}); };
    checkConnection(); setInterval(checkConnection,15000);
    load();
}());
