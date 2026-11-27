# -*- coding: utf-8 -*-
"""Flask Blueprint — NKB Asistall Altın + Nasdaq paper trading (mock UI)."""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, redirect, render_template_string, request, session

from . import prices as price_svc
from .wallet import PaperStore

TZ_TR = timezone(timedelta(hours=3))

bp = Blueprint("nkb_paper", __name__, url_prefix="/z/piyasa")

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATE_PATH = os.environ.get(
    "NKB_PAPER_STATE",
    os.path.join(_BASE, "nkb_paper_state.json"),
)
_store = PaperStore(_STATE_PATH)


def _require_secret():
    """Asistall /z secret katmanı; standalone'da NKB_PAPER_OPEN=1 ile açık."""
    if os.environ.get("NKB_PAPER_OPEN", "").strip() in ("1", "true", "yes"):
        return None
    if not session.get("logged_in"):
        return redirect("/login")
    if session.get("access_tier") != "secret":
        # Ana panel kullanıcısına /z gibi 404 hissi
        from flask import abort

        abort(404)
    return None


HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NKB Asistall · Paper</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root{
  --bg:#050505; --panel:#111111; --card:#1A1A1A; --line:#2A2A2A;
  --gold:#D4AF37; --gold2:#E8C547; --text:#F2F2F2; --muted:#9CA3AF;
  --up:#22C55E; --down:#EF4444; --side:#0D0D0D;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;
  background-image:radial-gradient(ellipse at 20% 0%,rgba(212,175,55,.08),transparent 45%),
    radial-gradient(ellipse at 80% 100%,rgba(212,175,55,.05),transparent 40%)}
.app{display:grid;grid-template-columns:220px 1fr 300px;min-height:100vh}
@media(max-width:1100px){.app{grid-template-columns:1fr}.sidebar,.ticket{display:none}.mobile-nav{display:flex!important}}
.sidebar{background:var(--side);border-right:1px solid var(--line);padding:22px 14px;display:flex;flex-direction:column}
.brand{color:var(--gold);font-weight:700;font-size:1.15rem;letter-spacing:.02em;margin-bottom:28px;padding:0 8px}
.brand small{display:block;color:var(--muted);font-weight:500;font-size:.7rem;margin-top:4px}
.nav a{display:flex;align-items:center;gap:10px;padding:11px 12px;border-radius:10px;color:var(--muted);
  text-decoration:none;font-size:.9rem;font-weight:500;margin-bottom:4px;transition:.15s}
.nav a:hover{background:#1a1a1a;color:var(--text)}
.nav a.active{background:rgba(212,175,55,.18);color:var(--gold)}
.nav svg{width:18px;height:18px;opacity:.85}
.side-foot{margin-top:auto;padding:12px 8px;font-size:.65rem;color:#666;line-height:1.4}
.main{padding:18px 20px 28px;overflow:auto}
.top-cards{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
@media(max-width:700px){.top-cards{grid-template-columns:1fr}}
.qcard{background:linear-gradient(180deg,#1c1c1c,#141414);border:1px solid var(--line);border-radius:14px;padding:16px 18px;cursor:pointer;transition:.15s}
.qcard:hover,.qcard.on{border-color:rgba(212,175,55,.45);box-shadow:0 0 0 1px rgba(212,175,55,.15)}
.qcard .sym{font-size:.78rem;color:var(--gold);font-weight:600;letter-spacing:.04em}
.qcard .px{font-size:1.65rem;font-weight:700;font-family:'JetBrains Mono',monospace;margin:6px 0 4px}
.qcard .chg{font-size:.85rem;font-weight:600;font-family:'JetBrains Mono',monospace}
.qcard .chg.up{color:var(--up)}.qcard .chg.down{color:var(--down)}
.qmeta{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px;font-size:.72rem;color:var(--muted)}
.qmeta b{color:var(--text);font-weight:600;font-family:'JetBrains Mono',monospace}
.chart-box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px 8px;margin-bottom:16px}
.chart-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:10px}
.chart-head .title{font-weight:700;font-size:1rem}
.spot{font-size:.65rem;background:rgba(212,175,55,.15);color:var(--gold);padding:3px 8px;border-radius:999px;font-weight:700}
.live-px{font-family:'JetBrains Mono',monospace;font-weight:600}
.tfs{display:flex;gap:4px;margin-left:auto;flex-wrap:wrap}
.tfs button{background:transparent;border:1px solid transparent;color:var(--muted);padding:5px 9px;border-radius:7px;
  cursor:pointer;font-size:.75rem;font-weight:600}
.tfs button.on{background:rgba(212,175,55,.15);color:var(--gold);border-color:rgba(212,175,55,.3)}
#chart{height:340px;width:100%}
.pos-box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.pos-box h3{font-size:.95rem;margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th{text-align:left;color:var(--muted);font-weight:600;padding:8px 6px;border-bottom:1px solid var(--line);font-size:.72rem}
td{padding:10px 6px;border-bottom:1px solid #222;font-family:'JetBrains Mono',monospace;font-size:.78rem}
.badge-al{background:rgba(34,197,94,.15);color:var(--up);padding:3px 8px;border-radius:6px;font-weight:700;font-size:.7rem}
.badge-sat{background:rgba(239,68,68,.15);color:var(--down);padding:3px 8px;border-radius:6px;font-weight:700;font-size:.7rem}
.pnl-up{color:var(--up)}.pnl-down{color:var(--down)}
.pos-foot{display:flex;justify-content:space-between;align-items:center;margin-top:12px;padding-top:10px;border-top:1px solid var(--line)}
.pos-foot .tot{font-weight:700;font-family:'JetBrains Mono',monospace}
.btn-x{background:transparent;border:1px solid #333;color:var(--muted);border-radius:6px;padding:4px 8px;cursor:pointer;font-size:.7rem}
.btn-x:hover{border-color:var(--down);color:var(--down)}
.ticket{background:var(--side);border-left:1px solid var(--line);padding:18px 16px;display:flex;flex-direction:column;gap:12px}
.ticket h2{font-size:1rem;display:flex;align-items:center;justify-content:space-between;gap:8px}
.paper-badge{display:inline-flex;align-items:center;gap:5px;background:rgba(212,175,55,.15);color:var(--gold);
  font-size:.65rem;font-weight:700;padding:4px 9px;border-radius:999px;letter-spacing:.03em}
.side-tog{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.side-tog button{padding:12px;border-radius:10px;border:1px solid var(--line);background:#171717;color:var(--muted);
  font-weight:700;cursor:pointer;font-size:.9rem}
.side-tog button.on-buy{background:linear-gradient(180deg,var(--gold2),var(--gold));color:#111;border-color:var(--gold)}
.side-tog button.on-sell{background:#2a1515;color:var(--down);border-color:rgba(239,68,68,.4)}
.field label{display:block;font-size:.72rem;color:var(--muted);margin-bottom:6px}
.field input,.field select{width:100%;background:#171717;border:1px solid var(--line);border-radius:9px;
  color:var(--text);padding:11px 12px;font-size:.9rem;font-family:'JetBrains Mono',monospace}
.otype{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.otype button{padding:9px;border-radius:8px;border:1px solid var(--line);background:#171717;color:var(--muted);cursor:pointer;font-weight:600;font-size:.8rem}
.otype button.on{background:rgba(212,175,55,.18);color:var(--gold);border-color:rgba(212,175,55,.35)}
.est{font-size:.75rem;color:var(--muted);line-height:1.7}
.est b{color:var(--text);font-family:'JetBrains Mono',monospace}
.btn-submit{margin-top:auto;width:100%;padding:14px;border:none;border-radius:11px;
  background:linear-gradient(180deg,var(--gold2),var(--gold));color:#111;font-weight:800;font-size:.95rem;cursor:pointer}
.btn-submit:hover{filter:brightness(1.05)}
.banner{background:rgba(212,175,55,.1);border:1px solid rgba(212,175,55,.25);color:var(--gold2);
  border-radius:10px;padding:8px 12px;font-size:.75rem;margin-bottom:14px;font-weight:600}
.panel-view{display:none}.panel-view.on{display:block}
.wallet-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.wcard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.wcard .lbl{font-size:.7rem;color:var(--muted)}.wcard .val{font-size:1.2rem;font-weight:700;font-family:'JetBrains Mono',monospace;margin-top:6px}
.log-list{list-style:none}.log-list li{padding:10px 0;border-bottom:1px solid #222;font-size:.8rem;color:var(--muted)}
.log-list .ts{color:#666;font-family:'JetBrains Mono',monospace;font-size:.7rem;margin-right:8px}
.mobile-nav{display:none;gap:8px;padding:10px;overflow:auto;border-bottom:1px solid var(--line);background:var(--side)}
.mobile-nav a{white-space:nowrap;color:var(--muted);text-decoration:none;font-size:.8rem;padding:6px 10px;border-radius:8px}
.mobile-nav a.active{background:rgba(212,175,55,.18);color:var(--gold)}
.src{font-size:.65rem;color:#555;margin-top:8px}
.back{color:var(--muted);font-size:.75rem;text-decoration:none}.back:hover{color:var(--gold)}
.empty{color:#666;padding:20px;text-align:center;font-size:.85rem}
</style>
</head>
<body>
<div class="mobile-nav">
  <a href="#" data-nav="piyasa" class="active">Piyasa</a>
  <a href="#" data-nav="pozisyonlar">Pozisyonlar</a>
  <a href="#" data-nav="emirler">Emirler</a>
  <a href="#" data-nav="cuzdan">Cüzdan</a>
  <a href="#" data-nav="risk">Risk</a>
  <a href="#" data-nav="log">Log</a>
</div>
<div class="app">
  <aside class="sidebar">
    <div class="brand">NKB Asistall<small>Paper / Demo · gerçek para yok</small></div>
    <nav class="nav">
      <a href="#" data-nav="piyasa" class="active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/></svg>
        Piyasa</a>
      <a href="#" data-nav="pozisyonlar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18"/></svg>
        Pozisyonlar</a>
      <a href="#" data-nav="emirler">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>
        Emirler</a>
      <a href="#" data-nav="cuzdan">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="14" rx="2"/><path d="M2 10h20"/><circle cx="16" cy="14" r="1.5"/></svg>
        Cüzdan</a>
      <a href="#" data-nav="risk">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l9 18H3L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>
        Risk</a>
      <a href="#" data-nav="log">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h12v16H4z"/><path d="M8 8h4M8 12h6M8 16h5"/></svg>
        Log</a>
    </nav>
    <div class="side-foot">
      <a class="back" href="/z/botlar">← Kripto botlar (SHORT MG8)</a><br>
      © 2026 NKB Asistall. Paper trading — broker / lisanslı bahis yok.
    </div>
  </aside>

  <main class="main">
    <div class="banner">PAPER / DEMO — Canlı fiyatlar Yahoo Finance üzerinden; emirler sanal cüzdana yazılır. Gerçek para, broker veya lisanslı bahis yok.</div>

    <section id="view-piyasa" class="panel-view on">
      <div class="top-cards">
        <div class="qcard on" id="card-XAUUSD" data-sym="XAUUSD">
          <div class="sym">XAU/USD</div>
          <div class="px" id="px-XAUUSD">—</div>
          <div class="chg" id="chg-XAUUSD">—</div>
          <div class="qmeta">
            <span>Günlük Düşük <b id="lo-XAUUSD">—</b></span>
            <span>Günlük Yüksek <b id="hi-XAUUSD">—</b></span>
            <span>Önceki Kapanış <b id="prev-XAUUSD">—</b></span>
          </div>
        </div>
        <div class="qcard" id="card-NASDAQ" data-sym="NASDAQ">
          <div class="sym">NASDAQ</div>
          <div class="px" id="px-NASDAQ">—</div>
          <div class="chg" id="chg-NASDAQ">—</div>
          <div class="qmeta">
            <span>Günlük Düşük <b id="lo-NASDAQ">—</b></span>
            <span>Günlük Yüksek <b id="hi-NASDAQ">—</b></span>
            <span>Önceki Kapanış <b id="prev-NASDAQ">—</b></span>
          </div>
        </div>
      </div>

      <div class="chart-box">
        <div class="chart-head">
          <span class="title" id="chart-sym">XAU/USD</span>
          <span class="spot">SPOT</span>
          <span class="live-px" id="chart-px">—</span>
          <span class="chg" id="chart-chg">—</span>
          <span style="color:var(--muted);font-size:.75rem" id="clock"></span>
          <div class="tfs">
            <button data-tf="1D" class="on">1D</button>
            <button data-tf="5D">5D</button>
            <button data-tf="1H">1H</button>
            <button data-tf="4H">4H</button>
            <button data-tf="1W">1W</button>
            <button data-tf="1M">1M</button>
          </div>
        </div>
        <div id="chart"></div>
        <div class="src" id="price-src">Kaynak: Yahoo Finance chart API</div>
      </div>

      <div class="pos-box">
        <h3>Açık Pozisyonlar</h3>
        <div id="pos-table-wrap"></div>
      </div>
    </section>

    <section id="view-pozisyonlar" class="panel-view">
      <div class="pos-box"><h3>Tüm Açık Pozisyonlar</h3><div id="pos-table-wrap-2"></div></div>
    </section>
    <section id="view-emirler" class="panel-view">
      <div class="pos-box"><h3>Emirler</h3><div id="orders-wrap"></div></div>
    </section>
    <section id="view-cuzdan" class="panel-view">
      <div class="wallet-grid" id="wallet-grid"></div>
      <p style="margin-top:14px"><button class="btn-x" id="btn-reset" type="button">Paper cüzdanı sıfırla (100.000 USD)</button></p>
    </section>
    <section id="view-risk" class="panel-view">
      <div class="pos-box">
        <h3>Risk (Paper)</h3>
        <div class="est" id="risk-box" style="margin-top:8px"></div>
      </div>
    </section>
    <section id="view-log" class="panel-view">
      <div class="pos-box"><h3>İşlem Logu</h3><ul class="log-list" id="log-list"></ul></div>
    </section>
  </main>

  <aside class="ticket">
    <h2>Emir Paneli <span class="paper-badge">🛡 PAPER TRADING</span></h2>
    <div class="side-tog">
      <button type="button" id="btn-buy" class="on-buy">▲ Al</button>
      <button type="button" id="btn-sell">▼ Sat</button>
    </div>
    <div class="field">
      <label>Sembol</label>
      <select id="sym-select">
        <option value="XAUUSD">XAU/USD</option>
        <option value="NASDAQ">NASDAQ</option>
      </select>
    </div>
    <div class="field">
      <label>Lot Miktarı</label>
      <input id="lots" type="number" min="0.01" step="0.01" value="1.00">
    </div>
    <div class="field">
      <label>Emir Türü</label>
      <div class="otype">
        <button type="button" id="ot-mkt" class="on">Piyasa</button>
        <button type="button" id="ot-lim">Limit</button>
      </div>
    </div>
    <div class="field" id="limit-wrap" style="display:none">
      <label>Limit Fiyat</label>
      <input id="limit-px" type="number" step="0.01">
    </div>
    <div class="field">
      <label>Tahmini Giriş Fiyatı</label>
      <input id="est-entry" type="text" readonly>
    </div>
    <div class="est">
      Tahmini Maliyet (USD): <b id="est-cost">—</b><br>
      Marjin Gereksinimi (USD): <b id="est-margin">—</b>
    </div>
    <button class="btn-submit" id="btn-order" type="button">Emir Gir</button>
  </aside>
</div>
<script>
const API = {{ api_base|tojson }};
let activeSym = 'XAUUSD';
let activeTf = '1D';
let side = 'buy';
let orderType = 'market';
let quotes = {};
let chart, series;

function fmt(n, d=2){
  if(n==null || isNaN(n)) return '—';
  return Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
}
function clsPnl(v){ return v>=0 ? 'pnl-up' : 'pnl-down'; }
function sign(v){ return (v>=0?'+':'') + fmt(v); }

function tickClock(){
  const now = new Date();
  const tr = new Date(now.toLocaleString('en-US',{timeZone:'Europe/Istanbul'}));
  const pad = x=>String(x).padStart(2,'0');
  document.getElementById('clock').textContent =
    pad(tr.getHours())+':'+pad(tr.getMinutes())+':'+pad(tr.getSeconds())+' (UTC+3)';
}
setInterval(tickClock, 1000); tickClock();

document.querySelectorAll('[data-nav]').forEach(a=>{
  a.addEventListener('click', e=>{
    e.preventDefault();
    const id = a.getAttribute('data-nav');
    document.querySelectorAll('[data-nav]').forEach(x=>x.classList.toggle('active', x.getAttribute('data-nav')===id));
    document.querySelectorAll('.panel-view').forEach(v=>v.classList.toggle('on', v.id==='view-'+id));
  });
});

document.querySelectorAll('.qcard').forEach(c=>{
  c.addEventListener('click', ()=>{
    activeSym = c.dataset.sym;
    document.querySelectorAll('.qcard').forEach(x=>x.classList.toggle('on', x===c));
    document.getElementById('sym-select').value = activeSym;
    refreshEstimate();
    loadCandles();
  });
});

document.querySelectorAll('.tfs button').forEach(b=>{
  b.addEventListener('click', ()=>{
    activeTf = b.dataset.tf;
    document.querySelectorAll('.tfs button').forEach(x=>x.classList.toggle('on', x===b));
    loadCandles();
  });
});

document.getElementById('btn-buy').onclick = ()=>{
  side='buy';
  document.getElementById('btn-buy').className='on-buy';
  document.getElementById('btn-sell').className='';
};
document.getElementById('btn-sell').onclick = ()=>{
  side='sell';
  document.getElementById('btn-sell').className='on-sell';
  document.getElementById('btn-buy').className='';
};
document.getElementById('ot-mkt').onclick = ()=>{
  orderType='market';
  document.getElementById('ot-mkt').classList.add('on');
  document.getElementById('ot-lim').classList.remove('on');
  document.getElementById('limit-wrap').style.display='none';
};
document.getElementById('ot-lim').onclick = ()=>{
  orderType='limit';
  document.getElementById('ot-lim').classList.add('on');
  document.getElementById('ot-mkt').classList.remove('on');
  document.getElementById('limit-wrap').style.display='block';
};
document.getElementById('sym-select').onchange = (e)=>{
  activeSym = e.target.value;
  document.querySelectorAll('.qcard').forEach(x=>x.classList.toggle('on', x.dataset.sym===activeSym));
  refreshEstimate(); loadCandles();
};
document.getElementById('lots').oninput = refreshEstimate;

function initChart(){
  const el = document.getElementById('chart');
  chart = LightweightCharts.createChart(el, {
    layout:{ background:{type:'solid', color:'#1A1A1A'}, textColor:'#9CA3AF' },
    grid:{ vertLines:{color:'#242424'}, horzLines:{color:'#242424'} },
    rightPriceScale:{ borderColor:'#2A2A2A' },
    timeScale:{ borderColor:'#2A2A2A', timeVisible:true },
    crosshair:{ mode:0 },
  });
  series = chart.addCandlestickSeries({
    upColor:'#D4AF37', downColor:'#8B7355', borderUpColor:'#E8C547',
    borderDownColor:'#6B5B3E', wickUpColor:'#D4AF37', wickDownColor:'#8B7355'
  });
  new ResizeObserver(()=>{ chart.applyOptions({width:el.clientWidth, height:el.clientHeight}); }).observe(el);
}

async function loadQuotes(){
  const r = await fetch(API+'/api/quotes');
  const j = await r.json();
  quotes = j.quotes || {};
  ['XAUUSD','NASDAQ'].forEach(sym=>{
    const q = quotes[sym]; if(!q) return;
    document.getElementById('px-'+sym).textContent = fmt(q.price, sym==='XAUUSD'?2:2);
    const el = document.getElementById('chg-'+sym);
    el.textContent = sign(q.change)+' ('+sign(q.change_pct)+'%)';
    el.className = 'chg ' + (q.change>=0?'up':'down');
    document.getElementById('lo-'+sym).textContent = fmt(q.day_low);
    document.getElementById('hi-'+sym).textContent = fmt(q.day_high);
    document.getElementById('prev-'+sym).textContent = fmt(q.previous_close);
  });
  const aq = quotes[activeSym];
  if(aq){
    document.getElementById('chart-sym').textContent = aq.display;
    document.getElementById('chart-px').textContent = fmt(aq.price);
    const cc = document.getElementById('chart-chg');
    cc.textContent = sign(aq.change_pct)+'%';
    cc.className = 'chg ' + (aq.change>=0?'up':'down');
    document.getElementById('price-src').textContent =
      'Kaynak: '+aq.source+' · Yahoo '+(aq.yahoo_symbol||'')+' · '+ (aq.short_name||'');
  }
  refreshEstimate();
  return j;
}

async function loadCandles(){
  const r = await fetch(API+'/api/candles?symbol='+encodeURIComponent(activeSym)+'&tf='+activeTf);
  const j = await r.json();
  if(!series || !j.candles) return;
  series.setData(j.candles.map(c=>({time:c.time, open:c.open, high:c.high, low:c.low, close:c.close})));
  chart.timeScale().fitContent();
}

async function loadState(){
  const r = await fetch(API+'/api/state');
  const st = await r.json();
  renderPositions(st);
  renderOrders(st);
  renderWallet(st);
  renderRisk(st);
  renderLogs(st);
}

function renderPositions(st){
  const rows = st.positions||[];
  const html = rows.length ? `
    <table><thead><tr>
      <th>Sembol</th><th>Yön</th><th>Lot</th><th>Giriş</th><th>Anlık</th><th>P/L (USD)</th><th>P/L (%)</th><th></th>
    </tr></thead><tbody>
    ${rows.map(p=>`<tr>
      <td>${p.display||p.symbol}</td>
      <td><span class="${p.side==='buy'?'badge-al':'badge-sat'}">${p.side==='buy'?'Al':'Sat'}</span></td>
      <td>${fmt(p.lots,2)}</td>
      <td>${fmt(p.entry)}</td>
      <td>${fmt(p.current)}</td>
      <td class="${clsPnl(p.pnl)}">${sign(p.pnl)}</td>
      <td class="${clsPnl(p.pnl)}">${sign(p.pnl_pct)}%</td>
      <td><button class="btn-x" data-close="${p.id}">Kapat</button></td>
    </tr>`).join('')}
    </tbody></table>
    <div class="pos-foot"><span style="color:var(--muted);font-size:.8rem">Paper pozisyonlar</span>
      <span class="tot ${clsPnl(st.unrealized_pnl||0)}">Toplam P/L (USD): ${sign(st.unrealized_pnl||0)}</span></div>`
    : '<div class="empty">Açık pozisyon yok — sağdan paper emir girin.</div>';
  document.getElementById('pos-table-wrap').innerHTML = html;
  document.getElementById('pos-table-wrap-2').innerHTML = html;
  document.querySelectorAll('[data-close]').forEach(b=>{
    b.onclick = async ()=>{
      if(!confirm('Pozisyonu paper fiyatla kapat?')) return;
      const r = await fetch(API+'/api/close',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:b.dataset.close})});
      const j = await r.json();
      if(!j.ok){ alert(j.error||'Hata'); return; }
      await loadState();
    };
  });
}

function renderOrders(st){
  const rows = st.orders||[];
  document.getElementById('orders-wrap').innerHTML = rows.length ? `
    <table><thead><tr><th>ID</th><th>Sembol</th><th>Yön</th><th>Lot</th><th>Tür</th><th>Fiyat</th><th>Durum</th><th>Zaman</th></tr></thead>
    <tbody>${rows.map(o=>`<tr>
      <td>${o.id}</td><td>${o.display||o.symbol}</td>
      <td><span class="${o.side==='buy'?'badge-al':'badge-sat'}">${o.side==='buy'?'Al':'Sat'}</span></td>
      <td>${fmt(o.lots,2)}</td><td>${o.type}</td>
      <td>${fmt(o.fill_price||o.limit_price)}</td><td>${o.status}</td><td>${o.created_at||''}</td>
    </tr>`).join('')}</tbody></table>` : '<div class="empty">Henüz emir yok.</div>';
}

function renderWallet(st){
  const cards = [
    ['Bakiye (USD)', st.balance],
    ['Equity', st.equity],
    ['Gerçekleşen P/L', st.realized_pnl],
    ['Açık P/L', st.unrealized_pnl],
    ['Kullanılan Marjin', st.used_margin],
    ['Serbest Marjin', st.free_margin],
  ];
  document.getElementById('wallet-grid').innerHTML = cards.map(([l,v])=>`
    <div class="wcard"><div class="lbl">${l}</div><div class="val ${typeof v==='number' && (l.includes('P/L')) ? clsPnl(v):''}">${fmt(v)}</div></div>`).join('');
}

function renderRisk(st){
  document.getElementById('risk-box').innerHTML = `
    Paper mod · kaldıraç simülasyonu (XAU ~10x, Nasdaq ~20x).<br>
    Equity: <b>${fmt(st.equity)}</b> · Kullanılan marjin: <b>${fmt(st.used_margin)}</b> ·
    Serbest: <b>${fmt(st.free_margin)}</b><br>
    Gerçek broker, para transferi veya lisanslı bahis yok.`;
}

function renderLogs(st){
  const logs = st.logs||[];
  document.getElementById('log-list').innerHTML = logs.length
    ? logs.map(l=>`<li><span class="ts">${l.ts||''}</span>${l.msg||''}</li>`).join('')
    : '<li>Log boş</li>';
}

async function refreshEstimate(){
  const lots = parseFloat(document.getElementById('lots').value||'0');
  const q = quotes[activeSym];
  const px = q ? q.price : 0;
  document.getElementById('est-entry').value = px ? fmt(px) : '—';
  if(!px || !lots){ document.getElementById('est-cost').textContent='—'; document.getElementById('est-margin').textContent='—'; return; }
  const r = await fetch(API+'/api/estimate?symbol='+activeSym+'&lots='+lots+'&price='+px);
  const j = await r.json();
  document.getElementById('est-cost').textContent = fmt(j.notional);
  document.getElementById('est-margin').textContent = fmt(j.margin);
}

document.getElementById('btn-order').onclick = async ()=>{
  const lots = parseFloat(document.getElementById('lots').value||'0');
  const body = {symbol:activeSym, side, lots, type:orderType};
  if(orderType==='limit') body.limit_price = parseFloat(document.getElementById('limit-px').value||'0');
  const r = await fetch(API+'/api/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j = await r.json();
  if(!j.ok){ alert(j.error||'Emir reddedildi'); return; }
  await loadState();
};

document.getElementById('btn-reset').onclick = async ()=>{
  if(!confirm('Tüm paper pozisyonlar silinip bakiye 100.000 USD olsun mu?')) return;
  await fetch(API+'/api/reset',{method:'POST'});
  await loadState();
};

(async function boot(){
  initChart();
  await loadQuotes();
  await loadCandles();
  await loadState();
  setInterval(async ()=>{ await loadQuotes(); await loadState(); }, 10000);
  setInterval(loadCandles, 60000);
})();
</script>
</body>
</html>
'''


@bp.route("/")
def index():
    gate = _require_secret()
    if gate is not None:
        return gate
    return render_template_string(HTML, api_base="/z/piyasa")


@bp.route("/api/quotes")
def api_quotes():
    gate = _require_secret()
    if gate is not None:
        return gate
    try:
        data = price_svc.fetch_all_quotes()
        data["server_time"] = datetime.now(TZ_TR).strftime("%Y-%m-%d %H:%M:%S")
        data["tz"] = "Europe/Istanbul (UTC+3)"
        return jsonify(data)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"quotes": {}, "errors": {"all": str(exc)}}), 502


@bp.route("/api/candles")
def api_candles():
    gate = _require_secret()
    if gate is not None:
        return gate
    symbol = request.args.get("symbol", "XAUUSD")
    tf = request.args.get("tf", "1D")
    try:
        return jsonify(price_svc.fetch_candles(symbol, tf))
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc), "candles": []}), 502


@bp.route("/api/state")
def api_state():
    gate = _require_secret()
    if gate is not None:
        return gate
    try:
        quotes = price_svc.fetch_all_quotes().get("quotes") or {}
    except Exception:  # noqa: BLE001
        quotes = {}
    return jsonify(_store.snapshot(quotes))


@bp.route("/api/estimate")
def api_estimate():
    gate = _require_secret()
    if gate is not None:
        return gate
    try:
        return jsonify(
            _store.estimate(
                request.args.get("symbol", "XAUUSD"),
                float(request.args.get("lots", 1)),
                float(request.args.get("price", 0)),
            )
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@bp.route("/api/order", methods=["POST"])
def api_order():
    gate = _require_secret()
    if gate is not None:
        return gate
    body = request.get_json(force=True, silent=True) or {}
    symbol = body.get("symbol", "XAUUSD")
    side = body.get("side", "buy")
    lots = float(body.get("lots") or 0)
    otype = (body.get("type") or "market").lower()
    try:
        q = price_svc.fetch_quote(symbol)
        price = float(q["price"])
        result = _store.place_market(
            symbol=symbol,
            side=side,
            lots=lots,
            price=price,
            order_type=otype,
            limit_price=body.get("limit_price"),
        )
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.route("/api/close", methods=["POST"])
def api_close():
    gate = _require_secret()
    if gate is not None:
        return gate
    body = request.get_json(force=True, silent=True) or {}
    pid = body.get("id")
    try:
        st = _store.snapshot({})
        pos = next((p for p in st.get("positions") or [] if p["id"] == pid), None)
        if not pos:
            raise ValueError("Pozisyon yok")
        q = price_svc.fetch_quote(pos["symbol"])
        return jsonify(_store.close_position(pid, float(q["price"])))
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.route("/api/reset", methods=["POST"])
def api_reset():
    gate = _require_secret()
    if gate is not None:
        return gate
    return jsonify({"ok": True, "state": _store.reset()})
