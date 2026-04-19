/* Dual-Eye Cockpit v1.2 — Race Mode with Start/Goal Tracking */

const DATA_PATHS = {
  pelosi: 'data/pelosi_stocks.json',
  kiyohara: 'data/kiyohara_stocks.json',
  market: 'data/market_status.json',
  log: 'data/analysis_log.json'
};

async function loadJSON(path) {
  try {
    const res = await fetch(path + '?t=' + Date.now());
    if (!res.ok) throw new Error(path);
    return await res.json();
  } catch (e) {
    console.error('Load failed:', path, e);
    return null;
  }
}

// ==================== 判定ロジック ====================
function judgeScore(score) {
  if (score >= 80) return { text: 'STRONG BUY', cls: 'strong-buy', color: '#22c55e' };
  if (score >= 60) return { text: 'BUY', cls: 'buy', color: '#06b6d4' };
  if (score >= 40) return { text: 'NEUTRAL', cls: 'neutral', color: '#fbbf24' };
  if (score >= 20) return { text: 'SELL', cls: 'sell', color: '#fb923c' };
  return { text: 'STRONG SELL', cls: 'strong-sell', color: '#ef4444' };
}

function fmtPct(n) {
  if (n === null || n === undefined || isNaN(n)) return '--';
  const sign = n >= 0 ? '+' : '';
  return sign + n.toFixed(2) + '%';
}

function fmtNum(n, decimals = 2) {
  if (n === null || n === undefined || isNaN(n)) return '--';
  return n.toLocaleString('ja-JP', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

// ==================== SVG目盛り描画 ====================
function drawBigTicks() {
  const ticks = document.getElementById('bigTicks');
  if (!ticks) return;
  ticks.innerHTML = '';
  // 0〜100 を -90度 〜 +90度（計180度）にマッピング
  // SVG弧は M 40 200 A 160 160 0 0 1 360 200 (中心 200,200 半径 160)
  for (let i = 0; i <= 10; i++) {
    const angle = -180 + (i * 18); // -180 (左端) → 0 (右端) → but it's upper arc
    // 正確には上半円弧なので 左端=180度、右端=0度で補間
    const t = i / 10;
    const deg = 180 - (t * 180); // 左端180→右端0
    const rad = (deg * Math.PI) / 180;
    const r = 160;
    const cx = 200, cy = 200;
    const x1 = cx + (r - 14) * Math.cos(rad);
    const y1 = cy - (r - 14) * Math.sin(rad);
    const x2 = cx + (r + 2) * Math.cos(rad);
    const y2 = cy - (r + 2) * Math.sin(rad);
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', x1);
    line.setAttribute('y1', y1);
    line.setAttribute('x2', x2);
    line.setAttribute('y2', y2);
    line.setAttribute('stroke', i % 5 === 0 ? '#8b97b3' : '#4b5368');
    line.setAttribute('stroke-width', i % 5 === 0 ? 2 : 1);
    ticks.appendChild(line);
  }
}

function setBigNeedle(score) {
  const needle = document.getElementById('bigNeedle');
  if (!needle) return;
  const t = Math.max(0, Math.min(100, score)) / 100;
  const deg = -90 + (t * 180); // -90度(0) → 0度(50) → +90度(100)
  needle.style.transform = `rotate(${deg}deg)`;
}

function setSpeedNeedle(id, score) {
  const needle = document.getElementById(id);
  if (!needle) return;
  const t = Math.max(0, Math.min(100, score)) / 100;
  // スピードゲージは -90度 〜 +90度（180度弧）
  const deg = -90 + (t * 180);
  needle.style.transform = `rotate(${deg}deg)`;
}

function setArcProgress(id, score, max = 100) {
  const el = document.getElementById(id);
  if (!el) return;
  const t = Math.max(0, Math.min(max, score)) / max;
  // stroke-dasharray は弧の全長
  const totalLen = parseFloat(el.getAttribute('stroke-dasharray') || 125);
  el.style.strokeDashoffset = totalLen * (1 - t);
}

// ==================== 描画 ====================
function renderCockpit(market, pelosi, kiyohara) {
  if (!market) return;

  const total = market.overall_score || 0;
  const judge = judgeScore(total);

  // 総合スコア
  const scoreEl = document.getElementById('overallScore');
  animateNumber(scoreEl, total);
  setBigNeedle(total);

  const judgeEl = document.getElementById('overallJudge');
  judgeEl.textContent = judge.text;
  judgeEl.className = 'judge-badge ' + judge.cls;

  // 4分割ミニゲージ
  const fund = market.fundamental || 0;
  const tech = market.technical || 0;
  const sent = market.sentiment || 0;
  const macro = market.macro || 0;
  document.getElementById('bdFund').textContent = fund + '/30';
  document.getElementById('bdTech').textContent = tech + '/30';
  document.getElementById('bdSent').textContent = sent + '/20';
  document.getElementById('bdMacro').textContent = macro + '/20';
  setArcProgress('fundArc', fund, 30);
  setArcProgress('techArc', tech, 30);
  setArcProgress('sentArc', sent, 20);
  setArcProgress('macroArc', macro, 20);

  // 2モデル対決
  if (pelosi && pelosi.stocks && pelosi.stocks[0]) {
    const top = pelosi.stocks[0];
    document.getElementById('pelosiTop').textContent = top.code;
    animateNumber(document.getElementById('pelosiScore'), top.score);
    document.getElementById('pelosiSignal').textContent = top.signal || '';
    setSpeedNeedle('pelosiNeedle', top.score);
    setArcProgress('pelosiArc', top.score, 100);
  }
  if (kiyohara && kiyohara.stocks && kiyohara.stocks[0]) {
    const top = kiyohara.stocks[0];
    document.getElementById('kiyoharaTop').textContent = top.code;
    animateNumber(document.getElementById('kiyoharaScore'), top.score);
    document.getElementById('kiyoharaSignal').textContent = top.signal || '';
    setSpeedNeedle('kiyoharaNeedle', top.score);
    setArcProgress('kiyoharaArc', top.score, 100);
  }

  // 警告ランプ（アクション）
  const actionList = document.getElementById('actionList');
  if (market.actions && market.actions.length > 0) {
    actionList.innerHTML = market.actions.map(a =>
      `<li class="priority-${a.priority || 'mid'}">${a.text}</li>`
    ).join('');
  }

  // 主要指標
  const indexGrid = document.getElementById('indexGrid');
  if (market.indices) {
    indexGrid.innerHTML = market.indices.map(i => {
      const deltaCls = i.change >= 0 ? 'up' : 'down';
      const barWidth = Math.min(50, Math.abs(i.change) * 10);
      return `
        <div class="instrument">
          <div class="inst-label">${i.name}</div>
          <div class="inst-value">${fmtNum(i.value)}</div>
          <div class="inst-delta ${deltaCls}">${fmtPct(i.change)}</div>
          <div class="inst-bar">
            <div class="inst-bar-fill ${deltaCls}" style="width: ${barWidth}%"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  // タイムスタンプ
  if (market.timestamp) {
    const d = new Date(market.timestamp);
    const hm = d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
    document.getElementById('lastUpdate').textContent = hm;
    document.getElementById('deployTime').textContent = d.toLocaleString('ja-JP');
  }
}

// 数値を滑らかにカウントアップ
function animateNumber(el, target, duration = 1400) {
  if (!el) return;
  const startVal = parseFloat(el.textContent) || 0;
  const startTime = performance.now();
  function step(now) {
    const t = Math.min(1, (now - startTime) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(startVal + (target - startVal) * eased);
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// v1.2: ステータス判定
function getStatusInfo(progress, status) {
  if (status === 'GOAL' || progress >= 100) {
    return { cls: 'status-goal', text: '🏁 GOAL 到達', trackCls: 'goal-reached', carIcon: '🏁' };
  }
  if (progress >= 70) {
    return { cls: 'status-accelerating', text: '⚡ 加速中', trackCls: '', carIcon: '🏎️' };
  }
  if (progress >= 0) {
    return { cls: 'status-running', text: '🏃 走行中', trackCls: '', carIcon: '🏎️' };
  }
  return { cls: 'status-standby', text: '🛫 STANDBY', trackCls: 'neg', carIcon: '🚗' };
}

// v1.2: 通貨フォーマット（銘柄コードで通貨判別）
function fmtStockPrice(price, code) {
  if (price === null || price === undefined) return '--';
  if (code && code.endsWith('.T')) {
    // 日本株
    return '¥' + fmtNum(price, 0);
  }
  return '$' + fmtNum(price, 2);
}

function renderStockList(containerId, data) {
  const el = document.getElementById(containerId);
  if (!el || !data || !data.stocks) {
    if (el) el.innerHTML = '<div class="loading">データ取得中...</div>';
    return;
  }
  el.innerHTML = data.stocks.map((s, i) => {
    const rankCls = i === 0 ? 'top1' : i === 1 ? 'top2' : i === 2 ? 'top3' : '';
    const progress = s.progress || 0;
    const statusInfo = getStatusInfo(progress, s.status);

    // 車の位置（0〜100の範囲に正規化、マイナス時は左端付近）
    const carPos = progress < 0 ? 2 : Math.min(98, Math.max(2, progress));
    // バーの伸び（マイナス時は右から左へ）
    const fillWidth = progress < 0 ? Math.min(100, Math.abs(progress)) : Math.min(100, progress);
    const fillDirection = progress < 0 ? 'right: 50%; left: auto; width: ' + fillWidth + '%;' : 'width: ' + fillWidth + '%;';

    const startPrice = s.start_price !== undefined ? fmtStockPrice(s.start_price, s.code) : '--';
    const goalPrice = s.goal_price !== undefined ? fmtStockPrice(s.goal_price, s.code) : '--';
    const currentPrice = s.price !== undefined ? fmtStockPrice(s.price, s.code) : '--';

    return `
      <div class="stock-row">
        <div class="rank-chip ${rankCls}">${i + 1}</div>
        <div class="stock-main">
          <h4>${s.name}</h4>
          <span class="stock-code">${s.code}</span>
          <div class="stock-tags">
            ${(s.tags || []).map(t => `<span class="tag ${t.type || ''}">${t.label}</span>`).join('')}
          </div>
          <span class="status-chip ${statusInfo.cls}">${statusInfo.text}</span>
        </div>
        <div class="stock-score-box">
          <div class="big">${s.score}</div>
          <div class="lbl">SCORE</div>
        </div>
        <div class="race-track">
          <div class="track-labels">
            <span class="start-lbl">🏁 START</span>
            <span>${s.signal || ''}</span>
            <span class="goal-lbl">GOAL 🏆</span>
          </div>
          <div class="track-container">
            <div class="flag-marker start-flag"></div>
            <div class="track-fill ${statusInfo.trackCls}" style="${fillDirection}"></div>
            <div class="car-marker ${progress < 0 ? 'car-standby' : ''}" style="left: ${carPos}%;">${statusInfo.carIcon}</div>
            <div class="flag-marker goal-flag"></div>
            <div class="track-percent">${progress}%</div>
          </div>
          <div class="track-prices">
            <span>${startPrice}</span>
            <span class="current-price">現在: ${currentPrice}</span>
            <span>${goalPrice}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// ==================== スパークライン描画 ====================
function renderSparkline(data) {
  const svg = document.getElementById('sparkline');
  if (!svg || !data || !data.entries) return;
  const pts = data.entries.slice(0, 24).reverse(); // 左から右へ時系列
  const W = 600, H = 180;
  const maxY = 100, minY = 0;
  const padX = 30, padY = 20;
  const usableW = W - padX * 2;
  const usableH = H - padY * 2;
  const step = pts.length > 1 ? usableW / (pts.length - 1) : 0;

  // 格子線
  let grid = '';
  [20, 40, 60, 80].forEach(v => {
    const y = padY + usableH * (1 - v / maxY);
    grid += `<line x1="${padX}" y1="${y}" x2="${W - padX}" y2="${y}" stroke="#1a2540" stroke-width="1" stroke-dasharray="2,3"/>`;
    grid += `<text x="${padX - 4}" y="${y + 3}" fill="#5a6686" font-size="9" text-anchor="end" font-family="Orbitron">${v}</text>`;
  });

  // 塗りエリア
  let areaPath = `M ${padX} ${padY + usableH}`;
  pts.forEach((p, i) => {
    const x = padX + step * i;
    const y = padY + usableH * (1 - p.score / maxY);
    areaPath += ` L ${x} ${y}`;
  });
  areaPath += ` L ${padX + step * (pts.length - 1)} ${padY + usableH} Z`;

  // 線
  let linePath = '';
  pts.forEach((p, i) => {
    const x = padX + step * i;
    const y = padY + usableH * (1 - p.score / maxY);
    linePath += (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`);
  });

  // 点
  let dots = '';
  pts.forEach((p, i) => {
    const x = padX + step * i;
    const y = padY + usableH * (1 - p.score / maxY);
    const j = judgeScore(p.score);
    dots += `<circle cx="${x}" cy="${y}" r="3" fill="${j.color}" stroke="#0a0e1a" stroke-width="1.5"/>`;
  });

  svg.innerHTML = `
    <defs>
      <linearGradient id="areaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#4f7cff" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="#4f7cff" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${grid}
    <path d="${areaPath}" fill="url(#areaGrad)"/>
    <path d="${linePath}" fill="none" stroke="#4f7cff" stroke-width="2"/>
    ${dots}
  `;
}

function renderLog(data) {
  const el = document.getElementById('logList');
  if (!el || !data || !data.entries) {
    if (el) el.innerHTML = '<div class="loading">履歴を取得中...</div>';
    return;
  }
  el.innerHTML = data.entries.slice(0, 24).map(e => `
    <div class="log-item">
      <div class="log-time">${e.time}</div>
      <div class="log-bar">
        <div class="log-bar-fill" style="width: ${e.score}%"></div>
      </div>
      <div class="log-score">${e.score}</div>
      <div class="log-judge">${e.judge}</div>
    </div>
  `).join('');
}

// ==================== タブ ====================
function setupTabs() {
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.tab-panel');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      tabs.forEach(t => t.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById('tab-' + target).classList.add('active');
    });
  });
}

// ==================== リフレッシュ ====================
async function refresh() {
  const btn = document.getElementById('refreshBtn');
  btn.classList.add('spinning');

  const [market, pelosi, kiyohara, log] = await Promise.all([
    loadJSON(DATA_PATHS.market),
    loadJSON(DATA_PATHS.pelosi),
    loadJSON(DATA_PATHS.kiyohara),
    loadJSON(DATA_PATHS.log)
  ]);

  renderCockpit(market, pelosi, kiyohara);
  renderStockList('pelosiList', pelosi);
  renderStockList('kiyoharaList', kiyohara);
  renderLog(log);
  renderSparkline(log);

  setTimeout(() => btn.classList.remove('spinning'), 500);
}

// ==================== 初期化 ====================
document.addEventListener('DOMContentLoaded', () => {
  drawBigTicks();
  setupTabs();
  document.getElementById('refreshBtn').addEventListener('click', refresh);
  refresh();
});
