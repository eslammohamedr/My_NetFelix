#!/usr/bin/env python3
"""
NetFelix Match Center & Sports Web UI
Renders a modern, responsive Arabic dark-mode dashboard for today's live matches,
beIN Sports channel controls, and TV launch actions.
"""

MATCH_CENTER_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>⚽ NetFelix Sports - مباريات اليوم وبي إن سبورتس</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f1015;
            --card-bg: #181a22;
            --card-hover: #212430;
            --primary: #E50914;
            --primary-glow: rgba(229, 9, 20, 0.4);
            --accent: #00d26a;
            --accent-glow: rgba(0, 210, 106, 0.3);
            --bein-purple: #5c1682;
            --text-main: #f0f2f5;
            --text-muted: #8b92a5;
            --border: rgba(255, 255, 255, 0.08);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Cairo', -apple-system, BlinkMacSystemFont, sans-serif;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            padding-bottom: 60px;
        }

        /* Top Header */
        header {
            background: linear-gradient(180deg, rgba(24, 26, 34, 0.95) 0%, rgba(15, 16, 21, 0.9) 100%);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
            padding: 14px 20px;
        }

        .header-container {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand h1 {
            font-size: 1.4rem;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .brand span.net { color: var(--primary); }
        .brand span.felix { color: #fff; }
        .brand .badge {
            background: linear-gradient(135deg, var(--bein-purple), #8e2de2);
            color: #fff;
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .btn {
            background: var(--card-bg);
            color: #fff;
            border: 1px solid var(--border);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 700;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
            text-decoration: none;
        }

        .btn:hover {
            background: var(--card-hover);
            transform: translateY(-1px);
        }

        .btn-primary {
            background: var(--primary);
            border-color: var(--primary);
        }

        .btn-primary:hover {
            background: #b80710;
            box-shadow: 0 4px 14px var(--primary-glow);
        }

        .btn-tv {
            background: linear-gradient(135deg, #1f4037, #99f2c8);
            color: #0f2027;
            font-weight: 800;
            border: none;
        }

        .btn-tv:hover {
            box-shadow: 0 4px 14px rgba(153, 242, 200, 0.4);
        }

        /* Container & Tabs */
        .main-container {
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 16px;
        }

        .hero-banner {
            background: linear-gradient(135deg, #240b36 0%, #c31432 100%);
            border-radius: 14px;
            padding: 20px 24px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            flex-wrap: wrap;
            gap: 16px;
        }

        .hero-text h2 {
            font-size: 1.3rem;
            font-weight: 800;
            margin-bottom: 6px;
        }

        .hero-text p {
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.85);
        }

        .filter-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
            overflow-x: auto;
            padding-bottom: 6px;
        }

        .tab {
            padding: 8px 18px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--text-muted);
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s;
        }

        .tab.active, .tab:hover {
            background: #fff;
            color: #000;
            border-color: #fff;
        }

        /* Matches Grid */
        .matches-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 16px;
        }

        .match-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: all 0.25s ease;
        }

        .match-card:hover {
            border-color: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }

        .match-card.is-live {
            border-color: var(--accent);
            box-shadow: 0 0 16px var(--accent-glow);
        }

        .match-header {
            padding: 10px 14px;
            background: rgba(255, 255, 255, 0.03);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-muted);
        }

        .match-header .tournament {
            color: #fff;
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .match-status {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 800;
        }

        .match-status.live {
            background: var(--accent);
            color: #000;
            animation: pulse 1.8s infinite;
        }

        .match-status.upcoming {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
        }

        .match-status.finished {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-muted);
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }

        /* Teams Body */
        .teams-body {
            padding: 16px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }

        .team {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            gap: 8px;
        }

        .team img {
            width: 46px;
            height: 46px;
            object-fit: contain;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.4));
        }

        .team-name {
            font-size: 0.95rem;
            font-weight: 700;
            line-height: 1.25;
            max-width: 120px;
        }

        .score-time {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 0 8px;
        }

        .score-time .time-val {
            font-size: 1.3rem;
            font-weight: 900;
            letter-spacing: 1px;
            color: #fff;
        }

        .score-time .vs-label {
            font-size: 0.75rem;
            font-weight: 800;
            color: var(--text-muted);
        }

        /* Match Footer / Channel Info */
        .match-footer {
            padding: 12px 14px;
            background: rgba(0, 0, 0, 0.2);
            border-top: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .meta-line {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        .channel-pill {
            background: rgba(92, 22, 130, 0.35);
            color: #d8b4fe;
            border: 1px solid rgba(168, 85, 247, 0.3);
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .comm-pill {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            color: #e2e8f0;
        }

        .card-actions {
            display: flex;
            gap: 8px;
            margin-top: 4px;
        }

        .btn-play-tv {
            flex: 1;
            background: linear-gradient(135deg, #2b5876, #4e4376);
            color: #fff;
            font-weight: 700;
            font-size: 0.8rem;
            border: none;
            padding: 8px;
            border-radius: 6px;
            cursor: pointer;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            transition: all 0.2s;
        }

        .btn-play-tv:hover {
            filter: brightness(1.2);
        }

        /* Toast */
        #toast {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: #181a22;
            color: #fff;
            border: 1px solid rgba(255,255,255,0.2);
            padding: 12px 24px;
            border-radius: 30px;
            font-size: 0.9rem;
            font-weight: 700;
            box-shadow: 0 8px 32px rgba(0,0,0,0.6);
            z-index: 1000;
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: none;
        }

        #toast.show {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }

        /* Responsive */
        @media (max-width: 600px) {
            .matches-grid {
                grid-template-columns: 1fr;
            }
            .header-container {
                flex-direction: column;
                align-items: stretch;
            }
            .header-actions {
                justify-content: space-between;
            }
        }
    </style>
</head>
<body>

    <header>
        <div class="header-container">
            <div class="brand">
                <h1>⚽ <span class="net">Net</span><span class="felix">Felix</span> Sports</h1>
                <span class="badge">Live IPTV</span>
            </div>
            <div class="header-actions">
                <button class="btn btn-tv" onclick="launchTV()">📺 تشغيل التلفزيون</button>
                <button class="btn btn-primary" id="btn-refresh" onclick="refreshMatches()">🔄 تحديث المباريات</button>
            </div>
        </div>
    </header>

    <div class="main-container">
        <div class="hero-banner">
            <div class="hero-text">
                <h2>بث مباشر لمباريات اليوم وقنوات beIN Sports</h2>
                <p>مدمجة تلقائياً مع سيرفر Jellyfin وتطبيق شاشة سامسونج (Tizen) بدقة عالية وبدون تقطيع.</p>
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="btn" onclick="copyPlaylistUrl()">📋 نسخ رابط M3U</button>
                <a href="/api/sports.m3u" class="btn" download>📥 تحميل M3U</a>
            </div>
        </div>

        <div class="filter-tabs">
            <div class="tab active" onclick="filterMatches('all')">جميع المباريات (<span id="count-all">0</span>)</div>
            <div class="tab" onclick="filterMatches('live')">🔴 جارية الآن (<span id="count-live">0</span>)</div>
            <div class="tab" onclick="filterMatches('upcoming')">⏰ قادمة اليوم (<span id="count-upcoming">0</span>)</div>
            <div class="tab" onclick="filterMatches('bein')">🏆 قنوات beIN Sports</div>
        </div>

        <div class="matches-grid" id="matches-grid">
            <div style="text-align: center; grid-column: 1/-1; padding: 40px; color: var(--text-muted);">
                جارٍ تحميل مباريات اليوم... ⏳
            </div>
        </div>
    </div>

    <div id="toast">تم الإجراء بنجاح</div>

    <script>
        let allMatches = [];

        async function loadMatches() {
            try {
                const res = await fetch('/api/sports/matches');
                allMatches = await res.json();
                renderMatches(allMatches);
                updateCounts();
            } catch (e) {
                console.error(e);
                document.getElementById('matches-grid').innerHTML = '<div style=\"grid-column: 1/-1; text-align: center; color: #ff6b6b;\">تعذر تحميل المباريات. يرجى الضغط على زر التحديث.</div>';
            }
        }

        function updateCounts() {
            document.getElementById('count-all').innerText = allMatches.length;
            const live = allMatches.filter(m => m.is_live).length;
            const upcoming = allMatches.filter(m => m.is_upcoming).length;
            document.getElementById('count-live').innerText = live;
            document.getElementById('count-upcoming').innerText = upcoming;
        }

        function renderMatches(matches) {
            const grid = document.getElementById('matches-grid');
            if (!matches || matches.length === 0) {
                grid.innerHTML = '<div style=\"grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);\">لا توجد مباريات مطابقة للفلتر المحدد.</div>';
                return;
            }

            grid.innerHTML = matches.map(m => {
                const isLive = m.is_live;
                const statusClass = isLive ? 'live' : (m.status === 'انتهت' ? 'finished' : 'upcoming');
                const chId = m.channel_id || 'bein1';
                const defaultLogo = 'https://assets.bein.com/mena/sites/3/2023/09/logos-_beINSPORTS1.png';
                const logo1 = m.team1_logo || defaultLogo;
                const logo2 = m.team2_logo || defaultLogo;

                return `
                <div class=\"match-card ${isLive ? 'is-live' : ''}\">
                    <div class=\"match-header\">
                        <span class=\"tournament\">🏆 ${m.tournament || 'مباراة ودية / دوري'}</span>
                        <span class=\"match-status ${statusClass}\">${isLive ? '🔴 مباشر' : m.status || m.time}</span>
                    </div>
                    <div class=\"teams-body\">
                        <div class=\"team\">
                            <img src=\"${logo1}\" alt=\"${m.team1}\" onerror=\"this.style.opacity=0.3\">
                            <span class=\"team-name\">${m.team1}</span>
                        </div>
                        <div class=\"score-time\">
                            <span class=\"time-val\">${m.time || 'VS'}</span>
                            <span class=\"vs-label\">ضد</span>
                        </div>
                        <div class=\"team\">
                            <img src=\"${logo2}\" alt=\"${m.team2}\" onerror=\"this.style.opacity=0.3\">
                            <span class=\"team-name\">${m.team2}</span>
                        </div>
                    </div>
                    <div class=\"match-footer\">
                        <div class=\"meta-line\">
                            <span class=\"channel-pill\">📺 ${m.channel_raw || 'beIN Sports'}</span>
                            ${m.commentator && m.commentator !== '—' ? `<span class=\"comm-pill\">🎙️ ${m.commentator}</span>` : ''}
                        </div>
                        <div class=\"card-actions\">
                            <button class=\"btn-play-tv\" onclick=\"playChannelOnTV('${chId}')\">📺 تشغيل على الشاشة</button>
                            <a class=\"btn-play-tv\" style=\"background: rgba(255,255,255,0.08);\" href=\"/api/sports/stream/${chId}\" target=\"_blank\">▶️ فتح الرابط</a>
                        </div>
                    </div>
                </div>
                `;
            }).join('');
        }

        function filterMatches(type) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');

            if (type === 'all') {
                renderMatches(allMatches);
            } else if (type === 'live') {
                renderMatches(allMatches.filter(m => m.is_live));
            } else if (type === 'upcoming') {
                renderMatches(allMatches.filter(m => m.is_upcoming));
            } else if (type === 'bein') {
                renderMatches(allMatches.filter(m => (m.channel_raw && m.channel_raw.includes('بي إن')) || (m.channel_id && m.channel_id.includes('bein'))));
            }
        }

        async function refreshMatches() {
            const btn = document.getElementById('btn-refresh');
            btn.disabled = true;
            btn.innerText = 'جارٍ التحديث... ⏳';
            showToast('جارٍ جلب أحدث مواعيد المباريات وروابط البث...');
            try {
                const res = await fetch('/api/sports/refresh', { method: 'POST' });
                const data = await res.json();
                showToast(`تم التحديث بنجاح! تم رصد ${data.count} مباراة اليوم.`);
                loadMatches();
            } catch (e) {
                showToast('تعذر التحديث: ' + e.message);
            } finally {
                btn.disabled = false;
                btn.innerText = '🔄 تحديث المباريات';
            }
        }

        async function launchTV() {
            showToast('جارٍ تشغيل تطبيق Jellyfin Live TV على شاشة التلفاز...');
            try {
                const res = await fetch('/api/tv/launch_app', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ app: 'jellyfin' })
                });
                const data = await res.json();
                showToast(data.message || 'تم إرسال الأمر للشاشة');
            } catch (e) {
                showToast('خطأ في إرسال الأمر: ' + e.message);
            }
        }

        async function playChannelOnTV(chId) {
            showToast(`جارٍ فتح قناة ${chId} على الشاشة...`);
            launchTV();
        }

        function copyPlaylistUrl() {
            const url = window.location.origin + '/api/sports.m3u';
            navigator.clipboard.writeText(url).then(() => {
                showToast('تم نسخ رابط M3U للحافظة بنجاح 📋');
            });
        }

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 3500);
        }

        // Initial Load
        loadMatches();
        // Auto refresh every 5 mins
        setInterval(loadMatches, 300000);
    </script>
</body>
</html>
"""
