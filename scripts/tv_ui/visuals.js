/* Shared, original SVG icons and theme treatment for the TV and its previews. */
(function() {
    'use strict';
    var paths = {
        jellyfin:'<path d="M27 8Q32 0 37 8L57 46Q62 56 51 56H13Q2 56 7 46Z" fill="currentColor"/><path d="M29 23l15 10-15 10z" fill="#fff" stroke="none"/>',
        iptv:'<rect x="8" y="11" width="48" height="34" rx="7"/><path d="M23 54h18M32 45v9"/><path d="M27 21l13 8-13 8z" fill="currentColor" stroke="none"/>',
        youtube:'<rect x="3" y="12" width="58" height="40" rx="13" fill="#ff284c" stroke="none"/><path d="M27 23l16 9-16 9z" fill="#fff" stroke="none"/>',
        netflix:'<path d="M17 7h10v50H17zM37 7h10v50H37z" fill="#b20710" stroke="none"/><path d="M17 7h11l19 50H36Z" fill="currentColor" stroke="none"/>',
        prayer:'<path d="M47 10A24 24 0 1 0 55 46 25 25 0 0 1 47 10Z"/><path d="M20 52h31"/>',
        radio:'<rect x="7" y="22" width="50" height="33" rx="8"/><path d="M14 20L46 8M16 31h16M17 38h13M17 45h13"/><circle cx="44" cy="39" r="7"/>',
        matches:'<circle cx="32" cy="32" r="24"/><path d="M32 21l11 8-4 13H25l-4-13zM32 8v13M55 25l-12 4M46 51l-7-9M18 51l7-9M9 25l12 4"/>',
        search:'<circle cx="27" cy="27" r="17"/><path d="M40 40l16 16"/>',
        appearance:'<path d="M31 7l7 17 18 8-18 7-7 18-8-18-17-7 17-8zM50 7v12M44 13h12"/>',
        home:'<path d="M8 29L32 9l24 20M15 25v30h34V25M26 55V37h12v18"/>',
        series:'<rect x="7" y="19" width="50" height="35" rx="7"/><path d="M13 12h38M19 5h26M27 28l15 9-15 9z"/>'
    };
    var brands = {jellyfin:'#ae8aff',iptv:'#ffcb83',youtube:'#ff284c',netflix:'#ff304b',prayer:'#d8dcff',radio:'#72e9db',matches:'#8fdfaa',search:'#bad5ff',appearance:'#edc4ff',home:'#c7dcff'};
    function icon(id) {
        var host = document.createElement('span'); host.className = 'nf-app-icon nf-icon-' + id;
        host.style.setProperty('--nf-brand', brands[id] || '#d5e7ff');
        host.innerHTML = '<svg viewBox="0 0 64 64" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">' + (paths[id] || paths.appearance) + '</svg>';
        return host;
    }
    function style(settings,theme) {
        return settings.iconStyle && settings.iconStyle !== 'theme' ? settings.iconStyle : theme.iconStyle || 'glass';
    }
    window.NetFelixVisuals = {icon:icon,iconStyle:style};
}());
