from flask import Flask, render_template_string, request, redirect, url_for, session
import json, os
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'gridbot2026secret'
TRT = pytz.timezone('Europe/Istanbul')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASSWORD = "2026"

def load_json(fp, d):
    try:
        if os.path.exists(fp):
            with open(fp, 'r') as f: return json.load(f)
    except: pass
    return d

HTML = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Grid Bot</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Segoe UI,sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:#e4e4e4;min-height:100vh;padding:10px}
.container{max-width:1200px;margin:0 auto}
.header{text-align:center;padding:20px;background:rgba(255,255,255,0.05);border-radius:15px;margin-bottom:20px}
.header h1{color:#00d4ff;font-size:1.8em}
.header p{color:#888;font-size:0.9em}
.logout{position:absolute;top:10px;right:10px;background:#ff4757;color:#fff;border:none;padding:8px 15px;border-radius:5px;cursor:pointer;text-decoration:none}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:20px}
.stat{background:rgba(255,255,255,0.05);border-radius:10px;padding:15px;text-align:center}
.stat-val{font-size:1.4em;font-weight:bold;color:#00d4ff}
.stat-val.profit{color:#00ff88}.stat-val.loss{color:#ff4757}
.stat-lbl{font-size:0.8em;color:#888;margin-top:5px}
.tabs{display:flex;gap:10px;margin-bottom:15px}
.tab{flex:1;padding:12px;background:rgba(255,255,255,0.05);border:none;border-radius:8px;color:#888;cursor:pointer}
.tab.active{background:#00d4ff;color:#1a1a2e}
.section{background:rgba(255,255,255,0.03);border-radius:10px;padding:15px;display:none}
.section.active{display:block}
.section h2{color:#00d4ff;font-size:1.1em;margin-bottom:15px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:10px}
.item{background:rgba(255,255,255,0.05);border-radius:8px;padding:12px;margin-bottom:10px}
.item-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.symbol{font-weight:bold;color:#fff;font-size:1.1em}
.pnl{font-weight:bold;padding:4px 8px;border-radius:5px}
.pnl.profit{background:rgba(0,255,136,0.2);color:#00ff88}
.pnl.loss{background:rgba(255,71,87,0.2);color:#ff4757}
.details{display:grid;grid-template-columns:repeat(2,1fr);gap:5px;font-size:0.85em;color:#aaa}
.badge{display:inline-block;background:rgba(0,212,255,0.2);color:#00d4ff;padding:2px 8px;border-radius:5px;font-size:0.8em;margin-left:10px}
.refresh{position:fixed;bottom:20px;right:20px;width:50px;height:50px;border-radius:50%;background:#00d4ff;border:none;color:#1a1a2e;font-size:1.5em;cursor:pointer}
.empty{text-align:center;padding:40px;color:#666}
</style></head><body>
<a href="/logout" class="logout">Çıkış</a>
<div class="container">
<div class="header"><h1>🤖 Grid Bot Panel</h1><p>Deniz GÜRBÜZ - Finans Uzmanı</p></div>
<div class="stats">
<div class="stat"><div class="stat-val">{{coins}}</div><div class="stat-lbl">Aktif Coin</div></div>
<div class="stat"><div class="stat-val">{{pos_count}}</div><div class="stat-lbl">Açık Pozisyon</div></div>
<div class="stat"><div class="stat-val">{{trade_count}}</div><div class="stat-lbl">Toplam İşlem</div></div>
<div class="stat"><div class="stat-val {{'profit' if total>=0 else 'loss'}}">${{"%.2f"|format(total)}}</div><div class="stat-lbl">Toplam Kar</div></div>
<div class="stat"><div class="stat-val {{'profit' if today>=0 else 'loss'}}">${{"%.2f"|format(today)}}</div><div class="stat-lbl">Bugün</div></div>
<div class="stat"><div class="stat-val">%{{"%.1f"|format(rate)}}</div><div class="stat-lbl">Başarı</div></div>
</div>
<div class="tabs">
<button class="tab active" onclick="showTab('pos')">📊 Pozisyonlar</button>
<button class="tab" onclick="showTab('trades')">📈 İşlemler</button>
</div>
<div id="pos" class="section active">
<h2>Açık Pozisyonlar ({{pos_count}})</h2>
{% if positions %}{% for k,p in positions.items() %}
<div class="item"><div class="item-head"><span class="symbol">{{p.symbol}}<span class="badge">Grid {{p.grid_level+1}}</span></span></div>
<div class="details"><span>💰 {{"%.6f"|format(p.entry_price)}}</span><span>📊 {{"%.4f"|format(p.amount)}}</span><span>💵 ${{p.trade_amount_usd}}</span><span>⏰ {{p.entry_time[:16]}}</span></div></div>
{% endfor %}{% else %}<div class="empty">Açık pozisyon yok</div>{% endif %}
</div>
<div id="trades" class="section">
<h2>Son İşlemler</h2>
{% if trades %}{% for t in trades[-50:]|reverse %}
<div class="item"><div class="item-head"><span class="symbol">{{t.symbol}}<span class="badge">+{{t.grid_diff}} Grid</span></span>
<span class="pnl {{'profit' if t.pnl_usdt>=0 else 'loss'}}">${{"%.2f"|format(t.pnl_usdt)}}</span></div>
<div class="details"><span>📥 {{"%.6f"|format(t.entry_price)}}</span><span>📤 {{"%.6f"|format(t.exit_price)}}</span><span>📊 {{t.buy_grid+1}}→{{t.sell_grid+1}}</span><span>📈 %{{"%.2f"|format(t.pnl_pct)}}</span><span>⏰ {{t.exit_time[:16] if t.exit_time else ''}}</span></div></div>
{% endfor %}{% else %}<div class="empty">Henüz işlem yok</div>{% endif %}
</div></div>
<button class="refresh" onclick="location.reload()">🔄</button>
<script>
function showTab(t){document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));document.getElementById(t).classList.add('active');event.target.classList.add('active')}
setTimeout(()=>location.reload(),30000);
</script></body></html>'''

LOGIN = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Giriş</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Segoe UI,sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:#e4e4e4;min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{background:rgba(255,255,255,0.05);padding:40px;border-radius:15px;text-align:center;width:90%;max-width:350px}
h1{color:#00d4ff;margin-bottom:10px}p{color:#888;margin-bottom:30px}
input{width:100%;padding:15px;border:none;border-radius:8px;background:rgba(255,255,255,0.1);color:#fff;margin-bottom:15px;text-align:center;font-size:1.1em}
button{width:100%;padding:15px;border:none;border-radius:8px;background:#00d4ff;color:#1a1a2e;font-size:1em;font-weight:bold;cursor:pointer}
.err{color:#ff4757;margin-bottom:15px}
</style></head><body>
<div class="box"><h1>🤖 Grid Bot</h1><p>Deniz GÜRBÜZ<br>Finans Uzmanı</p>
{% if error %}<div class="err">{{error}}</div>{% endif %}
<form method="POST"><input type="password" name="password" placeholder="Şifre" required><button>Giriş Yap</button></form></div></body></html>'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('ok'):
        return redirect(url_for('index'))
    err = None
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['ok'] = True
            return redirect(url_for('index'))
        err = "Hatalı şifre!"
    return render_template_string(LOGIN, error=err)

@app.route('/logout')
def logout():
    session.pop('ok', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('ok'):
        return redirect(url_for('login'))
    positions = load_json(os.path.join(BASE_DIR, "positions.json"), {})
    trades = load_json(os.path.join(BASE_DIR, "trades.json"), [])
    grid_cfg = load_json(os.path.join(BASE_DIR, "grid_config.json"), {})
    now = datetime.now(TRT)
    today_str = now.strftime('%Y-%m-%d')
    today_trades = [t for t in trades if t.get('exit_time', '').startswith(today_str)]
    today = sum(t.get('pnl_usdt', 0) for t in today_trades)
    total = sum(t.get('pnl_usdt', 0) for t in trades)
    wins = len([t for t in trades if t.get('pnl_usdt', 0) > 0])
    rate = (wins / len(trades) * 100) if trades else 0
    coins = len(grid_cfg.get('coins', []))
    return render_template_string(HTML, positions=positions, trades=trades, pos_count=len(positions), trade_count=len(trades), total=total, today=today, rate=rate, coins=coins)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
