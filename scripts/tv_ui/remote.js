(function() {
    'use strict';
    if (window.NetFelixPreviewMode || location.pathname === '/tv-preview') return;
    var epoch = '', sequence = 0, busy = false;
    async function poll() {
        if (busy || document.hidden) return;
        busy = true;
        try {
            var response = await fetch('/api/tv/companion/commands?after=' + sequence + '&epoch=' + encodeURIComponent(epoch),{cache:'no-store'});
            if (!response.ok) return;
            var value = await response.json();
            epoch = value.epoch; sequence = value.sequence;
            for (var i = 0; i < value.commands.length; i++) {
                var command = value.commands[i];
                resetScreensaverTimer();
                if (command.kind === 'text') {
                    openSearchModal();
                    var input = document.getElementById('sd-query-input');
                    input.value = command.text; input.dispatchEvent(new Event('input',{bubbles:true}));
                } else if (command.key === 'HOME') {
                    closeSearchModal(); closePrayerHub(); closePlayer();
                    window.scrollTo(0,0); refreshFocusables(); setFocus(0);
                } else if (['PLAY','PAUSE','STOP','REWIND','FF'].indexOf(command.key) >= 0) {
                    var video = document.getElementById('tv-video-player');
                    var audio = document.getElementById('quran-audio-player');
                    var media = getComputedStyle(document.getElementById('player-modal')).display !== 'none' ? video : audio;
                    if (command.key === 'PLAY') { var play = media.play(); if (play && play.catch) play.catch(function() { showToast('Press Play on the TV to enable playback.','▶'); });
                        if (media === audio && play && play.then) play.then(function() { document.getElementById('audio-bar').style.display = 'flex'; }).catch(function() {}); }
                    if (command.key === 'PAUSE') media.pause();
                    if (media === audio && ['PAUSE','STOP'].indexOf(command.key) >= 0) document.getElementById('audio-bar').style.display = 'none';
                    if (command.key === 'STOP') { media.pause(); if (Number.isFinite(media.duration)) media.currentTime = 0; }
                    if (['REWIND','FF'].indexOf(command.key) >= 0 && Number.isFinite(media.duration)) media.currentTime = Math.max(0, Math.min(media.duration, media.currentTime + (command.key === 'FF' ? 10 : -10)));
                } else {
                    var event = new KeyboardEvent('keydown',{bubbles:true,cancelable:true,keyCode:command.code,which:command.code});
                    document.activeElement.dispatchEvent(event);
                }
            }
        } catch (error) { /* Reconnect automatically; expired input is never replayed. */ }
        finally { busy = false; }
    }
    poll(); setInterval(poll,500);
}());
