import os, json, time, requests
from datetime import datetime, timedelta
import pytz
from strategy_checker import GridStrategy

TELEGRAM_TOKEN = "8249026121:AAHb6aRgH3y2MSUd-tFNboqtZc6gWOeOKTA"
TELEGRAM_CHAT_ID = "1158736282"
TRADE_AMOUNT = 50
NUM_GRIDS = 10
CHECK_INTERVAL = 10
GRID_UPDATE_DAYS = 7
TRT = pytz.timezone('Europe/Istanbul')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSITIONS_FILE = os.path.join(BASE_DIR, "positions.json")
TRADES_FILE = os.path.join(BASE_DIR, "trades.json")
GRID_FILE = os.path.join(BASE_DIR, "grid_config.json")

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass

def load_json(filepath, default):
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f: return json.load(f)
    except: pass
    return default

def save_json(filepath, data):
    with open(filepath, 'w') as f: json.dump(data, f, indent=2, default=str)

def fmt(num):
    if abs(num) >= 1: return f"{num:.2f}"
    elif abs(num) >= 0.01: return f"{num:.4f}"
    return f"{num:.6f}"

class GridBot:
    def __init__(self):
        self.strategy = GridStrategy()
        self.positions = load_json(POSITIONS_FILE, {})
        self.trades = load_json(TRADES_FILE, [])
        self.grid_config = load_json(GRID_FILE, {'last_update': None, 'coins': []})
        self.hourly_stats = {'buys': 0, 'sells': 0, 'profit': 0, 'last_report': datetime.now(TRT)}
        self.active_coins = []
    
    def initialize_grids(self, force=False):
        now = datetime.now(TRT)
        last_update = self.grid_config.get('last_update')
        need_update = force or not last_update
        if last_update and not force:
            try:
                last_dt = datetime.fromisoformat(last_update)
                if last_dt.tzinfo is None: last_dt = TRT.localize(last_dt)
                if (now - last_dt).days >= GRID_UPDATE_DAYS: need_update = True
            except: need_update = True
        
        if not need_update:
            for coin in self.grid_config.get('coins', []):
                self.strategy.grids[coin['symbol']] = coin['grids']
                self.strategy.grid_info[coin['symbol']] = coin['info']
            self.active_coins = list(self.strategy.grids.keys())
            print(f"Mevcut gridler yuklendi: {len(self.active_coins)} coin")
            return
        
        send_telegram("🔄 <b>Grid Güncelleme Başladı</b>")
        all_coins = self.strategy.get_all_futures_coins()
        coins_data = []
        for i, symbol in enumerate(all_coins):
            if self.strategy.calculate_grid(symbol, NUM_GRIDS):
                self.active_coins.append(symbol)
                coins_data.append({'symbol': symbol, 'grids': self.strategy.grids[symbol], 'info': self.strategy.grid_info[symbol]})
            if (i + 1) % 50 == 0: print(f"Islendi: {i + 1}/{len(all_coins)}")
            time.sleep(0.1)
        
        self.grid_config = {'last_update': now.isoformat(), 'coins': coins_data}
        save_json(GRID_FILE, self.grid_config)
        send_telegram(f"✅ <b>Grid Güncelleme Tamamlandı</b>\n\n📊 Aktif Coin: {len(self.active_coins)}\n📈 Grid: {NUM_GRIDS}\n💰 İşlem: ${TRADE_AMOUNT}")
    
    def process_buy(self, symbol, price, grid_level):
        key = f"{symbol}_g{grid_level}"
        now = datetime.now(TRT)
        amount = TRADE_AMOUNT / price
        self.positions[key] = {'symbol': symbol, 'entry_price': price, 'amount': amount, 'grid_level': grid_level, 'entry_time': now.isoformat(), 'trade_amount_usd': TRADE_AMOUNT}
        save_json(POSITIONS_FILE, self.positions)
        self.hourly_stats['buys'] += 1
        info = self.strategy.grid_info.get(symbol, {})
        send_telegram(f"🟢 <b>ALIŞ</b>\n\n📌 {symbol}\n💰 Fiyat: {fmt(price)}\n📊 Grid: {grid_level + 1}/{NUM_GRIDS}\n💵 ${TRADE_AMOUNT}\n📈 Range: %{info.get('range_pct', 0):.1f}\n⏰ {now.strftime('%H:%M:%S')}")
    
    def process_sell(self, sell_info):
        key, symbol = sell_info['key'], sell_info['symbol']
        buy_price, sell_price = sell_info['buy_price'], sell_info['sell_price']
        amount, buy_grid, sell_grid = sell_info['amount'], sell_info['buy_grid'], sell_info['sell_grid']
        now = datetime.now(TRT)
        gross_pnl = (sell_price - buy_price) * amount
        commission = TRADE_AMOUNT * 0.0008
        net_pnl = gross_pnl - commission
        grid_diff = sell_grid - buy_grid
        
        self.trades.append({'symbol': symbol, 'entry_price': buy_price, 'exit_price': sell_price, 'amount': amount, 'pnl_usdt': net_pnl, 'pnl_pct': sell_info['profit_pct'] * 100, 'buy_grid': buy_grid, 'sell_grid': sell_grid, 'grid_diff': grid_diff, 'entry_time': sell_info['entry_time'], 'exit_time': now.isoformat(), 'trade_amount_usd': TRADE_AMOUNT})
        save_json(TRADES_FILE, self.trades)
        if key in self.positions: del self.positions[key]
        save_json(POSITIONS_FILE, self.positions)
        self.hourly_stats['sells'] += 1
        self.hourly_stats['profit'] += net_pnl
        emoji = "🟢" if net_pnl > 0 else "🔴"
        send_telegram(f"🔵 <b>SATIŞ</b>\n\n📌 {symbol}\n💰 Alış: {fmt(buy_price)}\n💰 Satış: {fmt(sell_price)}\n\n📊 Grid: {buy_grid + 1} → {sell_grid + 1} (+{grid_diff})\n📈 %{sell_info['profit_pct'] * 100:.2f}\n\n{emoji} Kar: ${net_pnl:.2f}\n⏰ {now.strftime('%H:%M:%S')}")
    
    def send_hourly_report(self):
        now = datetime.now(TRT)
        today_str = now.strftime('%Y-%m-%d')
        today_trades = [t for t in self.trades if t.get('exit_time', '').startswith(today_str)]
        today_pnl = sum(t.get('pnl_usdt', 0) for t in today_trades)
        total_pnl = sum(t.get('pnl_usdt', 0) for t in self.trades)
        send_telegram(f"📊 <b>Saatlik Rapor</b>\n⏰ {now.strftime('%Y-%m-%d %H:%M')}\n\n<b>Son 1 Saat:</b>\n🟢 Alış: {self.hourly_stats['buys']}\n🔵 Satış: {self.hourly_stats['sells']}\n💰 Kar: ${self.hourly_stats['profit']:.2f}\n\n<b>Bugün:</b>\n📈 İşlem: {len(today_trades)}\n💵 Kar: ${today_pnl:.2f}\n\n<b>Genel:</b>\n📊 Pozisyon: {len(self.positions)}\n💰 Toplam: ${total_pnl:.2f}\n🪙 Coin: {len(self.active_coins)}")
        self.hourly_stats = {'buys': 0, 'sells': 0, 'profit': 0, 'last_report': now}
    
    def run(self):
        print("GRID BOT BASLATILIYOR")
        self.initialize_grids()
        if not self.active_coins:
            send_telegram("❌ Aktif coin yok!")
            return
        send_telegram(f"🚀 <b>Grid Bot Başladı!</b>\n\n📊 5dk Grafik\n🪙 {len(self.active_coins)} Coin\n💰 ${TRADE_AMOUNT}/işlem\n📈 {NUM_GRIDS} Grid\n🔄 {GRID_UPDATE_DAYS} günde güncelleme")
        last_hour = datetime.now(TRT).hour
        
        while True:
            try:
                now = datetime.now(TRT)
                if now.hour != last_hour:
                    self.send_hourly_report()
                    last_hour = now.hour
                    last_update = self.grid_config.get('last_update')
                    if last_update:
                        try:
                            last_dt = datetime.fromisoformat(last_update)
                            if last_dt.tzinfo is None: last_dt = TRT.localize(last_dt)
                            if (now - last_dt).days >= GRID_UPDATE_DAYS: self.initialize_grids(force=True)
                        except: pass
                
                prices = self.strategy.get_current_prices()
                if not prices:
                    time.sleep(5)
                    continue
                
                for symbol in self.active_coins:
                    if symbol not in prices: continue
                    price = prices[symbol]
                    for sell_info in self.strategy.should_sell(symbol, price, self.positions):
                        self.process_sell(sell_info)
                    should_buy, grid_level = self.strategy.should_buy(symbol, price, self.positions)
                    if should_buy:
                        self.process_buy(symbol, price, grid_level)
                
                time.sleep(CHECK_INTERVAL)
            except KeyboardInterrupt:
                send_telegram("⏹ Bot durduruldu.")
                break
            except Exception as e:
                print(f"Hata: {e}")
                time.sleep(30)

if __name__ == "__main__":
    GridBot().run()
