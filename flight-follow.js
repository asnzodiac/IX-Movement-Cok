/* ============================================================
   flight-follow.js
   ------------------------------------------------------------
   Add-on for AIX SEC OPS index.html — does NOT modify any
   existing logic in index.html. It only reads the arrivals
   table that index.html already builds and layers a "track
   this flight" checkbox + a live progress-bar panel on top.

   WHAT IT DOES
   ------------
   1. Adds a "Track" checkbox column to the end of every row in
      the Arrivals table (existing column indices are untouched,
      so nothing else on the page breaks).
   2. When a flight is checked, it appears in a floating panel
      (bottom-right) showing: flight number, route, ETA (IST),
      time remaining, and a live progress bar that fills up as
      the flight approaches its ETA.
   3. Progress bars update every 15s and automatically pick up
      delay changes (if ETA slips, the bar recalculates).
   4. Optional OS notifications ("Enable Alerts" button) fire at
      60 / 30 / 15 / 10 / 5 / 0 minutes remaining for any tracked
      flight — useful for ground staff who need a heads-up
      without staring at the screen.
   5. Selections persist across page refreshes (localStorage),
      keyed by the flight's internal ID, so staff don't lose
      their tracked list on reload.

   HOW TO INSTALL
   ---------------
   Add ONE line just before </body> in index.html:

       <script src="flight-follow.js"></script>

   That's it — no other changes needed.
============================================================ */
(function () {
  'use strict';

  /* ============================================================
     CONFIG
  ============================================================ */
  const STORAGE_KEY   = 'ff_followed_v1';
  const SCAN_MS        = 2000;   // how often we scan for new rows to add checkboxes to
  const TICK_MS        = 15000;  // how often the panel + progress bars refresh
  const ALERT_MINUTES  = [60, 30, 15, 10, 5, 0]; // minutes-remaining alert thresholds

  /* ============================================================
     STATE
  ============================================================ */
  // Map<flightId, { fid, fn, from, sch, eta, startedAt, notified:number[] }>
  let followed = new Map();
  let alertsEnabled = false;

  /* ============================================================
     HELPERS: locate the arrivals table regardless of which
     index.html variant is loaded (they use slightly different
     ids / dataset key names).
  ============================================================ */
  function getArrivalsBody() {
    return document.querySelector('#bArr') ||
           document.querySelector('#arrivals-table tbody');
  }
  function getArrivalsHeadRow() {
    return document.querySelector('#tArr thead tr') ||
           document.querySelector('#arrivals-table thead tr');
  }
  function rowId(tr) {
    return tr.dataset.fid || tr.dataset.flightId || '';
  }
  function rowEta(tr) {
    // prefer estimated time, fall back to scheduled
    return (parseInt(tr.dataset.est, 10) || parseInt(tr.dataset.sch, 10) || 0);
  }
  function rowSch(tr) {
    return parseInt(tr.dataset.sch, 10) || 0;
  }
  function rowFlightNo(tr) {
    return (tr.cells[0] ? tr.cells[0].textContent : '').trim();
  }
  function rowFrom(tr) {
    return (tr.cells[2] ? tr.cells[2].textContent : '').trim();
  }
  function isRealRow(tr) {
    return tr.cells && tr.cells.length >= 6 && !tr.dataset.skeleton;
  }

  /* ============================================================
     TIME FORMATTING (reuse page's toIST() if it exists)
  ============================================================ */
  function fmtIST(ts) {
    if (typeof window.toIST === 'function') {
      try { return window.toIST(ts); } catch (e) { /* fall through */ }
    }
    if (!ts) return '–';
    try {
      return new Date(ts * 1000).toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false
      });
    } catch (e) { return '–'; }
  }
  function fmtRemaining(sec) {
    if (sec <= 0) return 'Due now';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }
  function toast(msg) {
    if (typeof window.showToast === 'function') {
      try { window.showToast(msg); return; } catch (e) { /* fall through */ }
    }
    // minimal fallback toast
    let t = document.getElementById('ffFallbackToast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'ffFallbackToast';
      t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);' +
        'background:#3b82f6;color:#fff;padding:8px 16px;border-radius:10px;font-size:.8rem;' +
        'z-index:9999;opacity:0;transition:opacity .3s;';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = '1';
    clearTimeout(t._timer);
    t._timer = setTimeout(() => { t.style.opacity = '0'; }, 2500);
  }

  /* ============================================================
     PERSISTENCE
  ============================================================ */
  function loadStore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const arr = JSON.parse(raw);
      arr.forEach(item => followed.set(item.fid, item));
    } catch (e) { /* ignore corrupt storage */ }
  }
  function saveStore() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(followed.values())));
    } catch (e) { /* storage may be full/unavailable */ }
  }

  /* ============================================================
     FOLLOW / UNFOLLOW
  ============================================================ */
  function followFlight(tr) {
    const fid = rowId(tr);
    if (!fid || followed.has(fid)) return;
    const record = {
      fid,
      fn: rowFlightNo(tr),
      from: rowFrom(tr),
      sch: rowSch(tr),
      eta: rowEta(tr),
      startedAt: Math.floor(Date.now() / 1000),
      notified: []
    };
    followed.set(fid, record);
    saveStore();
    renderPanel();
    toast(`Tracking ${record.fn}`);
    maybePromptForAlerts();
  }

  function unfollowFlight(fid) {
    if (!followed.has(fid)) return;
    const rec = followed.get(fid);
    followed.delete(fid);
    saveStore();
    renderPanel();
    // sync checkbox in table if row is still present
    const body = getArrivalsBody();
    if (body) {
      const tr = body.querySelector(`tr[data-fid="${CSS.escape(fid)}"], tr[data-flight-id="${CSS.escape(fid)}"]`);
      const cb = tr && tr.querySelector('.ff-check');
      if (cb) cb.checked = false;
    }
    if (rec) toast(`Stopped tracking ${rec.fn}`);
  }

  /* ============================================================
     INJECT CHECKBOX COLUMN INTO ARRIVALS TABLE
     (appended at the END of each row — never inserted at the
     start — so existing column-index logic elsewhere on the
     page is completely unaffected.)
  ============================================================ */
  function ensureHeaderColumn() {
    const headRow = getArrivalsHeadRow();
    if (!headRow || headRow.querySelector('.ff-th')) return;
    const th = document.createElement('th');
    th.className = 'ff-th';
    th.textContent = 'Track';
    th.style.width = '52px';
    headRow.appendChild(th);
  }

  function ensureCheckbox(tr) {
    if (!isRealRow(tr) || tr.querySelector('.ff-check')) return;
    const fid = rowId(tr);
    if (!fid) return;

    const td = document.createElement('td');
    td.style.textAlign = 'center';

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'ff-check';
    cb.title = 'Track this flight for live updates';
    cb.checked = followed.has(fid);
    cb.addEventListener('change', () => {
      if (cb.checked) followFlight(tr);
      else unfollowFlight(fid);
    });

    td.appendChild(cb);
    tr.appendChild(td);
  }

  function scanRows() {
    ensureHeaderColumn();
    const body = getArrivalsBody();
    if (!body) return;
    Array.from(body.rows).forEach(ensureCheckbox);

    // Keep ETA data fresh for anything already followed, in case
    // the row was updated in place (delay change etc.)
    Array.from(body.rows).forEach(tr => {
      const fid = rowId(tr);
      if (fid && followed.has(fid)) {
        const rec = followed.get(fid);
        rec.eta = rowEta(tr) || rec.eta;
        rec.sch = rowSch(tr) || rec.sch;
        rec.fn  = rowFlightNo(tr) || rec.fn;
      }
    });
  }

  /* ============================================================
     NOTIFICATIONS (optional, best-effort — milestone alerts,
     since the web platform has no native progress-bar
     notification. The in-page panel below IS the progress bar.)
  ============================================================ */
  function maybePromptForAlerts() {
    if (alertsEnabled || !('Notification' in window)) return;
    if (Notification.permission === 'granted') { alertsEnabled = true; return; }
    // Don't auto-prompt aggressively; only nudge once via the panel button.
  }

  function checkAlerts(rec, remainingSec) {
    if (!alertsEnabled || Notification.permission !== 'granted') return;
    const remainingMin = Math.floor(remainingSec / 60);
    for (const threshold of ALERT_MINUTES) {
      if (remainingMin <= threshold && !rec.notified.includes(threshold)) {
        rec.notified.push(threshold);
        try {
          new Notification(`✈ ${rec.fn} — ${threshold === 0 ? 'Arriving now' : threshold + ' min out'}`, {
            body: `From ${rec.from || '–'} · ETA ${fmtIST(rec.eta)} IST`,
            tag: `ff-${rec.fid}-${threshold}`
          });
        } catch (e) { /* notifications may be blocked mid-session */ }
      }
    }
  }

  /* ============================================================
     PANEL UI
  ============================================================ */
  let panelCollapsed = false;

  function ensurePanelShell() {
    if (document.getElementById('ffPanel')) return;

    const style = document.createElement('style');
    style.textContent = `
      #ffPanel{
        position:fixed; right:14px; bottom:14px; z-index:800;
        width:300px; max-width:calc(100vw - 28px);
        background:var(--card,#1a2235); color:var(--text,#e2e8f0);
        border:1px solid var(--border,#1f2d45); border-radius:var(--radius,10px);
        box-shadow:var(--shadow,0 4px 24px rgba(0,0,0,.4));
        font-family:var(--sans,sans-serif); font-size:.75rem;
        overflow:hidden;
      }
      #ffPanel.ff-collapsed #ffPanelBody{ display:none; }
      #ffPanelHeader{
        display:flex; align-items:center; justify-content:space-between;
        padding:9px 12px; cursor:pointer; user-select:none;
        background:var(--surface,#111827); border-bottom:1px solid var(--border,#1f2d45);
        font-weight:700; font-family:var(--mono,monospace); font-size:.72rem;
      }
      #ffPanelBody{ max-height:280px; overflow-y:auto; }
      .ff-item{ padding:9px 12px; border-bottom:1px solid var(--border,#1f2d45); }
      .ff-item:last-child{ border-bottom:none; }
      .ff-item-top{ display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }
      .ff-fn{ font-family:var(--mono,monospace); font-weight:700; color:var(--accent2,#06b6d4); }
      .ff-remove{ cursor:pointer; color:var(--muted,#64748b); font-size:.85rem; padding:0 4px; }
      .ff-remove:hover{ color:var(--red,#ef4444); }
      .ff-meta{ display:flex; justify-content:space-between; color:var(--muted,#64748b); font-size:.66rem; margin-bottom:5px; }
      .ff-bar-track{ height:6px; border-radius:99px; background:var(--border,#1f2d45); overflow:hidden; }
      .ff-bar-fill{ height:100%; border-radius:99px; background:var(--accent,#3b82f6); transition:width .5s ease; }
      .ff-bar-fill.ff-soon{ background:var(--yellow,#f59e0b); }
      .ff-bar-fill.ff-due{ background:var(--red,#ef4444); }
      .ff-empty{ padding:16px 12px; text-align:center; color:var(--muted,#64748b); font-size:.7rem; }
      #ffAlertBtn{
        width:100%; padding:8px; border:none; border-top:1px solid var(--border,#1f2d45);
        background:var(--accent,#3b82f6); color:#fff; font-weight:600; font-size:.7rem; cursor:pointer;
      }
      #ffAlertBtn.ff-on{ background:var(--green,#10b981); }
      #ffBadge{
        background:var(--accent,#3b82f6); color:#fff; border-radius:99px;
        padding:1px 7px; font-size:.65rem; margin-left:6px;
      }
    `;
    document.head.appendChild(style);

    const panel = document.createElement('div');
    panel.id = 'ffPanel';
    panel.innerHTML = `
      <div id="ffPanelHeader">
        <span>🔔 Tracked Flights <span id="ffBadge">0</span></span>
        <span id="ffToggleIcon">▾</span>
      </div>
      <div id="ffPanelBody">
        <div id="ffPanelList"></div>
        <button id="ffAlertBtn">🔔 Enable Alerts</button>
      </div>
    `;
    document.body.appendChild(panel);

    document.getElementById('ffPanelHeader').addEventListener('click', () => {
      panelCollapsed = !panelCollapsed;
      panel.classList.toggle('ff-collapsed', panelCollapsed);
      document.getElementById('ffToggleIcon').textContent = panelCollapsed ? '▸' : '▾';
    });

    document.getElementById('ffAlertBtn').addEventListener('click', async () => {
      if (!('Notification' in window)) {
        toast('Notifications not supported on this browser');
        return;
      }
      const perm = await Notification.requestPermission();
      alertsEnabled = perm === 'granted';
      document.getElementById('ffAlertBtn').textContent = alertsEnabled ? '✓ Alerts Enabled' : '🔔 Enable Alerts';
      document.getElementById('ffAlertBtn').classList.toggle('ff-on', alertsEnabled);
      toast(alertsEnabled ? 'Milestone alerts enabled' : 'Alerts blocked');
    });
  }

  function renderPanel() {
    ensurePanelShell();
    const list = document.getElementById('ffPanelList');
    const badge = document.getElementById('ffBadge');
    if (!list || !badge) return;

    badge.textContent = followed.size;

    if (followed.size === 0) {
      list.innerHTML = `<div class="ff-empty">Select a flight in the Arrivals table to track it here.</div>`;
      return;
    }

    const now = Math.floor(Date.now() / 1000);
    const items = Array.from(followed.values()).sort((a, b) => (a.eta || a.sch) - (b.eta || b.sch));

    list.innerHTML = items.map(rec => {
      const eta = rec.eta || rec.sch || now;
      const total = Math.max(eta - rec.startedAt, 60); // avoid divide-by-zero
      const elapsed = now - rec.startedAt;
      let pct = Math.min(100, Math.max(0, (elapsed / total) * 100));
      const remainingSec = Math.max(0, eta - now);

      checkAlerts(rec, remainingSec);

      let barClass = '';
      if (remainingSec <= 0) { pct = 100; barClass = 'ff-due'; }
      else if (remainingSec <= 15 * 60) barClass = 'ff-soon';

      return `
        <div class="ff-item" data-fid="${rec.fid}">
          <div class="ff-item-top">
            <span class="ff-fn">${rec.fn || '–'}</span>
            <span class="ff-remove" data-remove="${rec.fid}" title="Stop tracking">✕</span>
          </div>
          <div class="ff-meta">
            <span>${rec.from ? 'From ' + rec.from : ''}</span>
            <span>ETA ${fmtIST(eta)} · ${fmtRemaining(remainingSec)}</span>
          </div>
          <div class="ff-bar-track">
            <div class="ff-bar-fill ${barClass}" style="width:${pct.toFixed(1)}%"></div>
          </div>
        </div>`;
    }).join('');

    list.querySelectorAll('[data-remove]').forEach(el => {
      el.addEventListener('click', () => unfollowFlight(el.getAttribute('data-remove')));
    });

    saveStore(); // persist any notified[] updates from checkAlerts()
  }

  /* ============================================================
     INIT
  ============================================================ */
  function init() {
    loadStore();
    ensurePanelShell();
    renderPanel();
    scanRows();
    setInterval(scanRows, SCAN_MS);
    setInterval(renderPanel, TICK_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
