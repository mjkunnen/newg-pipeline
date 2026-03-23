export interface DashboardAd {
  id: string;
  type: "image" | "video";
  thumbPath: string;
  adCopy: string;
  reach: number;
  reachFormatted: string;
  reachCost: string;
  daysActive: number;
  startDate: string;
  platforms: string[];
  downloadUrl: string;
}

export interface DateEntry {
  date: string;
  adCount: number;
  videoCount: number;
  imageCount: number;
}

export function formatReach(reach: number): string {
  if (reach >= 1_000_000) return `${(reach / 1_000_000).toFixed(1)}M`;
  if (reach >= 1_000) return `${(reach / 1_000).toFixed(1)}K`;
  return String(reach);
}

export function renderDashboard(
  webhookUrl: string,
  sheetId: string,
  dates: DateEntry[],
): string {
  const datesJson = JSON.stringify(dates);

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NEWG Creative Hub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #f0ece6;
  --surface: #faf8f5;
  --card: #ffffff;
  --border: #e5e0d8;
  --border-light: #ede9e2;
  --text: #1a1714;
  --text-secondary: #7a746b;
  --text-muted: #b0a99e;
  --accent: #e04400;
  --accent-light: #fff3ee;
  --success: #1a8f4a;
  --success-light: #eef8f1;
  --success-bg: #f4fbf6;
  --warning: #c27803;
  --warning-light: #fef8ee;
  --black: #111;
  --radius: 12px;
  --radius-sm: 8px;
  --shadow: 0 1px 3px rgba(26,23,20,0.04), 0 4px 12px rgba(26,23,20,0.03);
  --shadow-hover: 0 2px 8px rgba(26,23,20,0.06), 0 8px 24px rgba(26,23,20,0.05);
  --font-body: 'DM Sans', system-ui, sans-serif;
  --font-display: 'Instrument Serif', Georgia, serif;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

.screen { display: none; min-height: 100vh; }
.screen.active { display: block; }

/* ===== LOGIN ===== */
.login {
  display: none;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px 24px;
  background: var(--surface);
}
.login.active { display: flex; }

.login-brand {
  margin-bottom: 64px;
  text-align: center;
}
.login-logo {
  font-family: var(--font-body);
  font-size: 38px;
  font-weight: 700;
  letter-spacing: 6px;
  color: var(--text);
}
.login-logo em {
  font-family: var(--font-display);
  font-style: italic;
  color: var(--accent);
  letter-spacing: 0;
}
.login-tagline {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 18px;
  color: var(--text-secondary);
  margin-top: 8px;
}
.login-prompt {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 16px;
}
.login-buttons { display: flex; flex-direction: column; gap: 10px; width: 280px; }
.login-btn {
  padding: 16px 20px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--font-body);
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: var(--shadow);
}
.login-btn:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-hover);
  transform: translateY(-1px);
}
.login-btn::after { content: '\\2192'; color: var(--text-muted); transition: color 0.2s; }
.login-btn:hover::after { color: var(--accent); }

/* ===== HEADER ===== */
.header {
  padding: 16px 24px;
  background: var(--surface);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-logo {
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--text);
}
.header-logo em {
  font-family: var(--font-display);
  font-style: italic;
  color: var(--accent);
  letter-spacing: 0;
}
.header-right { display: flex; align-items: center; gap: 12px; }
.header-user {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}
.avatar {
  width: 32px; height: 32px;
  background: var(--text);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: var(--surface);
}

/* ===== DATES ===== */
.dates-page { background: var(--bg); }
.dates-hero {
  padding: 40px 24px 24px;
  max-width: 640px;
  margin: 0 auto;
}
.dates-title {
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 400;
  color: var(--text);
  margin-bottom: 4px;
}
.dates-sub {
  font-size: 14px;
  color: var(--text-muted);
}
.dates-list {
  max-width: 640px;
  margin: 0 auto;
  padding: 0 24px 40px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.date-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
}
.date-card:hover {
  box-shadow: var(--shadow-hover);
  transform: translateY(-1px);
}
.date-card.today { border-left: 3px solid var(--accent); }
.date-card-top {
  display: flex;
  justify-content: space-between;
  align-items: start;
  margin-bottom: 8px;
}
.date-label {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}
.date-today-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  background: var(--accent-light);
  color: var(--accent);
  padding: 3px 8px;
  border-radius: 4px;
  margin-left: 10px;
}
.date-count {
  font-size: 28px;
  font-weight: 800;
  color: var(--text);
  line-height: 1;
}
.date-count span { color: var(--text-muted); font-weight: 400; font-size: 16px; }
.date-meta {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 12px;
}
.progress-track {
  height: 3px;
  background: var(--border-light);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}
.progress-fill.partial { background: var(--accent); }
.progress-fill.complete { background: var(--success); }

/* ===== DAY DETAIL ===== */
.detail-page { background: var(--bg); }
.detail-top {
  padding: 16px 24px;
  max-width: 1080px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.back-btn {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
  background: none;
  border: none;
  font-family: var(--font-body);
  display: flex;
  align-items: center;
  gap: 6px;
}
.back-btn:hover { text-decoration: underline; }
.detail-date {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}
.detail-progress {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px 20px;
}
.detail-progress-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}
.detail-progress-row strong { color: var(--accent); }

.ad-grid {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px 40px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

/* ===== AD CARD ===== */
.ad-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: all 0.2s;
  cursor: pointer;
}
.ad-card:hover { box-shadow: var(--shadow-hover); }
.ad-card.status-done { border-color: #b8e6c8; background: var(--success-bg); }
.ad-card.status-in_progress { border-color: #f5deb0; background: var(--warning-light); }

.ad-card-compact {
  display: flex;
  gap: 14px;
  padding: 16px;
}
.ad-thumb {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
  background: var(--border-light);
}
.ad-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.ad-type-badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.8px;
  padding: 2px 6px;
  border-radius: 4px;
}
.ad-type-badge.video { background: var(--accent); color: #fff; }
.ad-type-badge.image { background: rgba(255,255,255,0.9); color: var(--text-secondary); border: 1px solid var(--border); }

.ad-info { flex: 1; min-width: 0; }
.ad-info-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.ad-id { font-size: 13px; font-weight: 700; color: var(--text); }
.status-badge {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 4px;
}
.status-badge.not_started { background: #f0ece6; color: var(--text-muted); }
.status-badge.in_progress { background: #fef3e0; color: var(--warning); }
.status-badge.done { background: var(--success-light); color: var(--success); }
.ad-copy-preview {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 6px;
}
.ad-stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-muted);
}
.ad-stats strong { color: var(--text-secondary); font-weight: 600; }

/* ===== EXPANDED / MODAL ===== */
.modal-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(26,23,20,0.4);
  backdrop-filter: blur(4px);
  z-index: 200;
  padding: 24px;
  overflow-y: auto;
  justify-content: center;
  align-items: start;
}
.modal-overlay.active { display: flex; }

.modal {
  background: var(--card);
  border-radius: 16px;
  max-width: 520px;
  width: 100%;
  margin: 40px auto;
  box-shadow: 0 8px 40px rgba(26,23,20,0.12);
  overflow: hidden;
  animation: modalIn 0.25s ease;
}
@keyframes modalIn {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.modal-thumb {
  width: 100%;
  aspect-ratio: 16/10;
  background: var(--border-light);
  overflow: hidden;
  position: relative;
}
.modal-thumb img { width: 100%; height: 100%; object-fit: cover; }
.modal-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1px;
  padding: 4px 10px;
  border-radius: 6px;
}
.modal-badge.video { background: var(--accent); color: #fff; }
.modal-badge.image { background: rgba(255,255,255,0.92); color: var(--text-secondary); border: 1px solid var(--border); }

.modal-close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 32px; height: 32px;
  border-radius: 50%;
  background: rgba(255,255,255,0.9);
  border: none;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: background 0.15s;
}
.modal-close:hover { background: #fff; }

.modal-body { padding: 24px; }
.modal-copy {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text);
  margin-bottom: 16px;
}
.modal-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.modal-stat { display: flex; flex-direction: column; gap: 2px; }
.modal-stat-val { font-size: 16px; font-weight: 700; color: var(--text); }
.modal-stat-lbl { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }

.modal-platforms {
  display: flex; gap: 6px; margin-bottom: 20px; flex-wrap: wrap;
}
.plat-tag {
  font-size: 11px; font-weight: 600; padding: 4px 10px;
  border-radius: 4px; background: var(--bg); color: var(--text-secondary);
}

.modal-actions {
  display: flex; flex-direction: column; gap: 8px; margin-bottom: 24px;
}
.modal-link {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--accent);
  text-decoration: none;
  transition: all 0.15s;
}
.modal-link:hover { background: var(--accent-light); border-color: var(--accent); }
.modal-link.download-btn { background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 600; justify-content: center; }
.modal-link.download-btn:hover { background: var(--text); border-color: var(--text); }
.modal-link.disabled { color: var(--text-muted); pointer-events: none; opacity: 0.5; justify-content: center; }

.modal-divider { height: 1px; background: var(--border-light); margin: 24px 0; }

/* Status selector */
.status-selector { margin-bottom: 20px; }
.status-selector label {
  font-size: 10px; font-weight: 600; letter-spacing: 1.5px;
  text-transform: uppercase; color: var(--text-muted); display: block; margin-bottom: 8px;
}
.status-options { display: flex; gap: 6px; }
.status-opt {
  flex: 1;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--card);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  text-align: center;
  transition: all 0.15s;
  color: var(--text-secondary);
}
.status-opt:hover { border-color: var(--text-muted); }
.status-opt.active-not_started { border-color: var(--text-muted); background: var(--bg); color: var(--text); }
.status-opt.active-in_progress { border-color: var(--warning); background: var(--warning-light); color: var(--warning); }
.status-opt.active-done { border-color: var(--success); background: var(--success-light); color: var(--success); }

/* Submission form */
.submit-form { display: none; }
.submit-form.visible { display: block; }
.form-group { margin-bottom: 14px; }
.form-group label {
  font-size: 10px; font-weight: 600; letter-spacing: 1.5px;
  text-transform: uppercase; color: var(--text-muted); display: block; margin-bottom: 6px;
}
.form-input {
  width: 100%; padding: 11px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--font-body); font-size: 13px;
  color: var(--text); outline: none; transition: border-color 0.15s;
}
.form-input:focus { border-color: var(--accent); }
.form-input::placeholder { color: var(--text-muted); }

.platform-checks { display: flex; gap: 8px; }
.plat-check {
  flex: 1;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--card);
  font-family: var(--font-body); font-size: 12px; font-weight: 600;
  cursor: pointer; text-align: center;
  transition: all 0.15s; color: var(--text-muted);
  user-select: none;
}
.plat-check.selected { border-color: var(--accent); background: var(--accent-light); color: var(--accent); }

.submit-btn {
  width: 100%; padding: 14px;
  background: var(--black); border: none; border-radius: var(--radius-sm);
  color: #fff; font-family: var(--font-body);
  font-size: 14px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
  letter-spacing: 0.3px;
}
.submit-btn:hover { background: #333; }
.submit-btn:disabled { background: var(--text-muted); cursor: not-allowed; }

.submit-success {
  display: none;
  padding: 14px;
  background: var(--success-light);
  border: 1px solid #b8e6c8;
  border-radius: var(--radius-sm);
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--success);
}

.submit-error {
  display: none;
  padding: 14px;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: var(--radius-sm);
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: #dc2626;
}

/* Done summary in modal */
.done-summary {
  padding: 16px;
  background: var(--success-bg);
  border: 1px solid #b8e6c8;
  border-radius: var(--radius-sm);
}
.done-summary-row {
  display: flex; gap: 8px; align-items: start;
  font-size: 12px; color: var(--text-secondary);
  margin-bottom: 6px;
}
.done-summary-row:last-child { margin-bottom: 0; }
.done-summary-row strong { color: var(--text); font-weight: 600; min-width: 80px; }
.done-summary-row a { color: var(--accent); text-decoration: none; word-break: break-all; }
.done-summary-row a:hover { text-decoration: underline; }

@media (max-width: 700px) {
  .ad-grid { grid-template-columns: 1fr; }
  .dates-title { font-size: 28px; }
  .modal { margin: 16px auto; }
}
</style>
</head>
<body>

<!-- LOGIN -->
<div id="screen-login" class="screen login active">
  <div class="login-brand">
    <div class="login-logo">NEW<em>G</em></div>
    <div class="login-tagline">Creative Hub</div>
  </div>
  <div class="login-prompt">Who's working today?</div>
  <div class="login-buttons">
    <button class="login-btn" onclick="selectUser('Jerson')">Jerson</button>
    <button class="login-btn" onclick="selectUser('Boss')">Boss</button>
  </div>
</div>

<!-- DATES -->
<div id="screen-dates" class="screen dates-page">
  <div class="header">
    <div class="header-logo">NEW<em>G</em></div>
    <div class="header-right">
      <span class="header-user" id="header-username"></span>
      <div class="avatar" id="header-avatar"></div>
    </div>
  </div>
  <div class="dates-hero">
    <div class="dates-title">Opdrachten</div>
    <div class="dates-sub">Winning ads — dagelijks vernieuwd</div>
  </div>
  <div class="dates-list" id="dates-list"></div>
</div>

<!-- DAY DETAIL -->
<div id="screen-detail" class="screen detail-page">
  <div class="header">
    <div class="header-logo">NEW<em>G</em></div>
    <div class="header-right">
      <span class="header-user" id="detail-username"></span>
      <div class="avatar" id="detail-avatar"></div>
    </div>
  </div>
  <div class="detail-top">
    <button class="back-btn" onclick="showDates()">\u2190 Terug</button>
    <div class="detail-date" id="detail-date-label"></div>
  </div>
  <div class="detail-progress">
    <div class="detail-progress-row">
      <span>Voortgang</span>
      <strong id="detail-progress-text"></strong>
    </div>
    <div class="progress-track">
      <div class="progress-fill partial" id="detail-progress-bar" style="width:0%"></div>
    </div>
  </div>
  <div class="ad-grid" id="ad-grid"></div>
</div>

<!-- MODAL -->
<div class="modal-overlay" id="modal-overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal" id="modal-content"></div>
</div>

<script>
const ZAPIER_WEBHOOK_URL = "${webhookUrl}";
const SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/${sheetId}/gviz/tq?tqx=out:csv&sheet=Submissions";
const DATES_INDEX = ${datesJson};

let currentUser = null;
let currentDate = null;
let currentAds = [];

// ===== ROUTING =====
function route() {
  const hash = location.hash || '#/';
  const saved = localStorage.getItem('newg_user');
  if (saved && hash === '#/') {
    currentUser = saved;
    location.hash = '#/dates';
    return;
  }
  if (!saved && hash !== '#/') {
    // Allow direct deep links — auto-login as Jerson
    currentUser = 'Jerson';
    localStorage.setItem('newg_user', 'Jerson');
  } else {
    currentUser = saved;
  }

  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));

  if (hash === '#/') {
    document.getElementById('screen-login').classList.add('active');
  } else if (hash === '#/dates') {
    document.getElementById('screen-dates').classList.add('active');
    if (!sheetLoaded) loadSheetData().then(() => renderDates()); else renderDates();
    return;
  } else if (hash.startsWith('#/day/')) {
    currentDate = hash.replace('#/day/', '');
    document.getElementById('screen-detail').classList.add('active');
    loadDay(currentDate);
  }

  updateHeaders();
}

function selectUser(name) {
  localStorage.setItem('newg_user', name);
  currentUser = name;
  location.hash = '#/dates';
}

function updateHeaders() {
  if (!currentUser) return;
  const initial = currentUser[0].toUpperCase();
  document.querySelectorAll('.header-user').forEach(el => el.textContent = currentUser);
  document.querySelectorAll('.avatar').forEach(el => el.textContent = initial);
}

// ===== UTIL =====
function escapeAttr(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ===== SHARED SUBMISSIONS (Google Sheet backed) =====
let sheetSubmissions = {}; // key: "date_adId" → submission object
let sheetLoaded = false;

async function loadSheetData() {
  try {
    const resp = await fetch(SHEET_CSV_URL);
    if (!resp.ok) throw new Error('Sheet fetch failed');
    const csv = await resp.text();
    const rows = parseCSV(csv);
    // headers: editor, date, ad_id, ad_copy, original_reach, drive_link, landing_page, platforms, submitted_at, status
    if (rows.length < 2) { sheetLoaded = true; return; }
    const headers = rows[0].map(h => h.trim().toLowerCase());
    for (let i = 1; i < rows.length; i++) {
      const row = rows[i];
      if (row.length < headers.length) continue;
      const obj = {};
      headers.forEach((h, idx) => obj[h] = row[idx] || '');
      if (!obj.date || !obj.ad_id) continue;
      const key = obj.date + '_' + obj.ad_id;
      // Later rows overwrite earlier ones (latest submission wins)
      sheetSubmissions[key] = {
        editor: obj.editor,
        date: obj.date,
        ad_id: obj.ad_id,
        ad_copy: obj.ad_copy,
        original_reach: obj.original_reach,
        drive_link: obj.drive_link,
        landing_page: obj.landing_page,
        platforms: obj.platforms ? obj.platforms.split(',').map(p => p.trim()) : [],
        submitted_at: obj.submitted_at,
        status: obj.status || 'done'
      };
    }
    sheetLoaded = true;
    console.log('[sheet] Loaded ' + Object.keys(sheetSubmissions).length + ' submissions');
  } catch (err) {
    console.warn('[sheet] Failed to load submissions, falling back to localStorage:', err);
    sheetLoaded = true;
  }
}

function parseCSV(text) {
  const rows = [];
  let current = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i+1] === '"') { field += '"'; i++; }
      else if (c === '"') { inQuotes = false; }
      else { field += c; }
    } else {
      if (c === '"') { inQuotes = true; }
      else if (c === ',') { current.push(field); field = ''; }
      else if (c === '\\n' || (c === '\\r' && text[i+1] === '\\n')) {
        if (c === '\\r') i++;
        current.push(field); field = '';
        if (current.some(f => f !== '')) rows.push(current);
        current = [];
      } else { field += c; }
    }
  }
  current.push(field);
  if (current.some(f => f !== '')) rows.push(current);
  return rows;
}

// ===== STATUS (Sheet-backed with localStorage cache) =====
function getStatus(date, adId) {
  const key = date + '_' + adId;
  // Sheet submission = done
  if (sheetSubmissions[key]) return 'done';
  // Fall back to localStorage for in_progress
  return localStorage.getItem('newg_status_' + date + '_' + adId) || 'not_started';
}
function setStatus(date, adId, status) {
  localStorage.setItem('newg_status_' + date + '_' + adId, status);
}
function getSubmission(date, adId) {
  const key = date + '_' + adId;
  // Prefer Sheet data (shared across all users)
  if (sheetSubmissions[key]) return sheetSubmissions[key];
  // Fall back to localStorage (optimistic after submit)
  const raw = localStorage.getItem('newg_submission_' + date + '_' + adId);
  return raw ? JSON.parse(raw) : null;
}

function formatDateLabel(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const days = ['Zondag','Maandag','Dinsdag','Woensdag','Donderdag','Vrijdag','Zaterdag'];
  const months = ['januari','februari','maart','april','mei','juni','juli','augustus','september','oktober','november','december'];
  return days[d.getDay()] + ' ' + d.getDate() + ' ' + months[d.getMonth()] + ' ' + d.getFullYear();
}

function isToday(dateStr) {
  return dateStr === new Date().toISOString().split('T')[0];
}

function renderDates() {
  const list = document.getElementById('dates-list');
  list.innerHTML = '';

  if (DATES_INDEX.length === 1) {
    location.hash = '#/day/' + DATES_INDEX[0].date;
    return;
  }

  DATES_INDEX.forEach(entry => {
    const doneCount = getDoneCount(entry.date, entry.adCount);
    const pct = entry.adCount > 0 ? Math.round((doneCount / entry.adCount) * 100) : 0;
    const allDone = doneCount === entry.adCount;
    const today = isToday(entry.date);

    const card = document.createElement('div');
    card.className = 'date-card' + (today ? ' today' : '');
    card.onclick = () => location.hash = '#/day/' + entry.date;
    card.innerHTML = \`
      <div class="date-card-top">
        <div>
          <span class="date-label">\${formatDateLabel(entry.date)}</span>
          \${today ? '<span class="date-today-tag">Vandaag</span>' : ''}
        </div>
        <div class="date-count" style="color:\${allDone ? 'var(--success)' : 'var(--text)'}">\${doneCount}<span>/\${entry.adCount}</span></div>
      </div>
      <div class="date-meta">\${entry.adCount} ads &middot; \${entry.videoCount} video, \${entry.imageCount} image</div>
      <div class="progress-track"><div class="progress-fill \${allDone ? 'complete' : 'partial'}" style="width:\${pct}%"></div></div>
    \`;
    list.appendChild(card);
  });
}

function getDoneCount(date, total) {
  let count = 0;
  for (let i = 0; i < total; i++) {
    // Try common id patterns
    const keys = Object.keys(localStorage).filter(k => k.startsWith('newg_status_' + date + '_') && localStorage.getItem(k) === 'done');
    return keys.length;
  }
  return count;
}

// ===== DAY DETAIL =====
async function loadDay(date) {
  document.getElementById('detail-date-label').textContent = formatDateLabel(date);

  // Load shared submissions from Google Sheet (once)
  if (!sheetLoaded) {
    document.getElementById('ad-grid').innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Laden...</div>';
    await loadSheetData();
  }

  try {
    const resp = await fetch('data/' + date + '.json');
    if (!resp.ok) throw new Error('Not found');
    const data = await resp.json();
    currentAds = data.ads || data;
  } catch {
    document.getElementById('ad-grid').innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Geen data voor deze datum</div>';
    return;
  }

  renderAdGrid();
}

function renderAdGrid() {
  const grid = document.getElementById('ad-grid');
  grid.innerHTML = '';

  let doneCount = 0;
  currentAds.forEach(ad => {
    const status = getStatus(currentDate, ad.id);
    if (status === 'done') doneCount++;

    const card = document.createElement('div');
    card.className = 'ad-card status-' + status;
    card.onclick = () => openModal(ad);

    const statusLabels = { not_started: 'Not Started', in_progress: 'In Progress', done: 'Done' };

    card.innerHTML = \`
      <div class="ad-card-compact">
        <div class="ad-thumb">
          <img src="\${ad.thumbPath || ad.thumbnailUrl || ''}" alt="" onerror="this.style.display='none'">
          <div class="ad-type-badge \${ad.type}">\${ad.type.toUpperCase()}</div>
        </div>
        <div class="ad-info">
          <div class="ad-info-top">
            <span class="ad-id">\${ad.id.split('_').pop() ? '#' + (parseInt(ad.id.split('_').pop()) + 1) : ad.id}</span>
            <span class="status-badge \${status}">\${statusLabels[status]}</span>
          </div>
          <div class="ad-copy-preview">\${escapeHtml((ad.adCopy || '').slice(0, 60))}</div>
          <div class="ad-stats">
            <span><strong>\${ad.reachFormatted || formatNum(ad.reach)}</strong> reach</span>
            <span><strong>\${ad.daysActive || ad.duration || 0}d</strong> active</span>
          </div>
        </div>
      </div>
    \`;
    grid.appendChild(card);
  });

  const total = currentAds.length;
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0;
  document.getElementById('detail-progress-text').textContent = doneCount + ' / ' + total + ' klaar';
  const bar = document.getElementById('detail-progress-bar');
  bar.style.width = pct + '%';
  bar.className = 'progress-fill ' + (doneCount === total && total > 0 ? 'complete' : 'partial');
}

// ===== MODAL =====
let currentModalAd = null;
function openModal(ad) {
  currentModalAd = ad;
  const status = getStatus(currentDate, ad.id);
  const submission = getSubmission(currentDate, ad.id);
  const statusLabels = { not_started: 'Not Started', in_progress: 'In Progress', done: 'Done' };
  const platformMap = { facebook: 'Facebook', instagram: 'Instagram', messenger: 'Messenger', audience_network: 'Audience Network', threads: 'Threads' };

  const modal = document.getElementById('modal-content');
  modal.innerHTML = \`
    <div class="modal-thumb">
      <img src="\${ad.thumbPath || ad.thumbnailUrl || ''}" alt="" onerror="this.parentElement.style.background='var(--border-light)'">
      <div class="modal-badge \${ad.type}">\${ad.type.toUpperCase()}</div>
      <button class="modal-close" onclick="closeModal()">\\u00d7</button>
    </div>
    <div class="modal-body">
      <div class="modal-copy">\${escapeHtml(ad.adCopy || 'No ad copy available')}</div>
      <div class="modal-stats">
        <div class="modal-stat">
          <div class="modal-stat-val">\${ad.reachFormatted || formatNum(ad.reach)}</div>
          <div class="modal-stat-lbl">Reach</div>
        </div>
        <div class="modal-stat">
          <div class="modal-stat-val">\${ad.daysActive || ad.duration || 0}d</div>
          <div class="modal-stat-lbl">Active</div>
        </div>
        <div class="modal-stat">
          <div class="modal-stat-val">\${ad.startDate || ad.startedAt || '—'}</div>
          <div class="modal-stat-lbl">Started</div>
        </div>
      </div>
      <div class="modal-platforms">
        \${(ad.platforms || []).map(p => '<span class="plat-tag">' + (platformMap[p] || p) + '</span>').join('')}
      </div>
      <div class="modal-actions">
        \${ad.downloadUrl ? '<a class="modal-link download-btn" href="' + ad.downloadUrl + '" download>\u2B07 Download origineel (full quality)</a>' : '<span class="modal-link disabled">Geen download beschikbaar</span>'}
      </div>

      <div class="modal-divider"></div>

      <div class="status-selector">
        <label>Status</label>
        <div class="status-options">
          <button class="status-opt \${status === 'not_started' ? 'active-not_started' : ''}" onclick="changeStatus('\${ad.id}','not_started')">Not Started</button>
          <button class="status-opt \${status === 'in_progress' ? 'active-in_progress' : ''}" onclick="changeStatus('\${ad.id}','in_progress')">In Progress</button>
          <button class="status-opt \${status === 'done' ? 'active-done' : ''}" onclick="changeStatus('\${ad.id}','done')">Done</button>
        </div>
      </div>

      <div class="submit-form \${status === 'done' && !submission ? 'visible' : ''}" id="submit-form">
        <div class="form-group">
          <label>Google Drive Link</label>
          <input class="form-input" id="input-drive" placeholder="https://drive.google.com/file/..." value="">
        </div>
        <div class="form-group">
          <label>Landing Page</label>
          <input class="form-input" id="input-landing" placeholder="https://newgarments.store/..." value="">
        </div>
        <div class="form-group">
          <label>Platform</label>
          <div class="platform-checks">
            <div class="plat-check" data-plat="meta" onclick="togglePlat(this)">Meta</div>
            <div class="plat-check" data-plat="tiktok" onclick="togglePlat(this)">TikTok</div>
          </div>
        </div>
        <button class="submit-btn" onclick="submitAd('\${ad.id}')">Submit</button>
        <div class="submit-success" id="submit-success">Submitted! Je remake wordt gelaunched.</div>
        <div class="submit-error" id="submit-error">Indienen mislukt, probeer opnieuw.</div>
      </div>

      \${submission ? \`
        <div class="done-summary">
          <div class="done-summary-row"><strong>Drive</strong><a href="\${submission.drive_link}" target="_blank">\${submission.drive_link}</a></div>
          <div class="done-summary-row"><strong>Landing</strong><a href="\${submission.landing_page}" target="_blank">\${submission.landing_page}</a></div>
          <div class="done-summary-row"><strong>Platform</strong><span>\${(submission.platforms || []).join(', ')}</span></div>
        </div>
      \` : ''}
    </div>
  \`;

  document.getElementById('modal-overlay').classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
  document.body.style.overflow = '';
  renderAdGrid();
}

function changeStatus(adId, status) {
  setStatus(currentDate, adId, status);
  const ad = currentAds.find(a => a.id === adId);
  if (ad) openModal(ad);
}

function togglePlat(el) {
  el.classList.toggle('selected');
}

async function submitAd(adId) {
  const driveLink = document.getElementById('input-drive').value.trim();
  const landingPage = document.getElementById('input-landing').value.trim();
  const platforms = [...document.querySelectorAll('.plat-check.selected')].map(el => el.dataset.plat);

  if (!driveLink || !landingPage || platforms.length === 0) {
    alert('Vul alle velden in en selecteer minstens 1 platform.');
    return;
  }

  const ad = currentAds.find(a => a.id === adId);
  const payload = {
    editor: currentUser,
    date: currentDate,
    ad_id: adId,
    ad_copy: ad ? (ad.adCopy || '').slice(0, 200) : '',
    original_reach: ad ? ad.reach : 0,
    drive_link: driveLink,
    landing_page: landingPage,
    platforms: platforms.join(','),
    submitted_at: new Date().toISOString(),
    status: 'pending'
  };

  const btn = document.querySelector('.submit-btn');
  const successEl = document.getElementById('submit-success');
  const errorEl = document.getElementById('submit-error');
  btn.disabled = true;
  btn.textContent = 'Submitting...';
  successEl.style.display = 'none';
  errorEl.style.display = 'none';

  try {
    if (ZAPIER_WEBHOOK_URL && ZAPIER_WEBHOOK_URL !== '' && !ZAPIER_WEBHOOK_URL.includes('XXXXX')) {
      await fetch(ZAPIER_WEBHOOK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        mode: 'no-cors'
      });
    }

    // Optimistic update: save locally so it shows immediately
    const localSubmission = { ...payload, platforms: platforms };
    localStorage.setItem('newg_submission_' + currentDate + '_' + adId, JSON.stringify(localSubmission));
    sheetSubmissions[currentDate + '_' + adId] = localSubmission;
    setStatus(currentDate, adId, 'done');

    successEl.style.display = 'block';
    btn.style.display = 'none';

    setTimeout(() => {
      closeModal();
      openModal(currentAds.find(a => a.id === adId));
    }, 1500);
  } catch (err) {
    errorEl.style.display = 'block';
    btn.disabled = false;
    btn.textContent = 'Submit';
  }
}

// ===== HELPERS =====
function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

function formatNum(n) {
  if (!n) return '0';
  if (n >= 1000000) return (n/1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n/1000).toFixed(1) + 'K';
  return String(n);
}

function showDates() { location.hash = '#/dates'; }

// ===== INIT =====
window.addEventListener('hashchange', route);
route();
</script>
</body>
</html>`;
}
