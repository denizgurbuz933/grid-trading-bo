import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pytz

TRT = pytz.timezone('Europe/Istanbul')

class GridStrategy:
    def __init__(self):
        self.grids = {}
        self.grid_info = {}
    
    def get_all_futures_coins(self):
        try:
            url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
            response = requests.get(url, timeout=10)
            data = response.json()
            coins = [s['symbol'] for s in data['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING' and s['contractType'] == 'PERPETUAL']
            return coins
        except:
            return []
    
    def get_current_prices(self):
        try:
            url = 'https://fapi.binance.com/fapi/v1/ticker/price'
            response = requests.get(url, timeout=10)
            return {item['symbol']: float(item['price']) for item in response.json()}
        except:
            return {}
    
    def get_klines(self, symbol, interval='5m', limit=500):
        try:
            url = 'https://fapi.binance.com/fapi/v1/klines'
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            response = requests.get(url, params=params, timeout=10)
            return response.json()
        except:
            return []
    
    def calculate_grid(self, symbol, num_grids=10):
        try:
            klines = self.get_klines(symbol, '5m', 500)
            if not klines or len(klines) < 100:
                return False
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            price_min = min(lows)
            price_max = max(highs)
            price_range = price_max - price_min
            if price_range / price_min < 0.02:
                return False
            grid_size = price_range / num_grids
            grids = [price_min + (i * grid_size) for i in range(num_grids + 1)]
            self.grids[symbol] = grids
            self.grid_info[symbol] = {'min': price_min, 'max': price_max, 'size': grid_size, 'range_pct': (price_range / price_min) * 100, 'updated': datetime.now(TRT).isoformat()}
            return True
        except:
            return False
    
    def get_grid_level(self, symbol, price):
        if symbol not in self.grids:
            return None
        grids = self.grids[symbol]
        for i in range(len(grids) - 1):
            if grids[i] <= price < grids[i + 1]:
                return i
        if price >= grids[-1]:
            return len(grids) - 2
        return 0
    
    def should_buy(self, symbol, price, holdings):
        grid_level = self.get_grid_level(symbol, price)
        if grid_level is None:
            return False, -1
        key = f"{symbol}_g{grid_level}"
        if key in holdings:
            return False, grid_level
        return True, grid_level
    
    def should_sell(self, symbol, price, holdings):
        current_grid = self.get_grid_level(symbol, price)
        if current_grid is None:
            return []
        sells = []
        for key, pos in list(holdings.items()):
            if not key.startswith(f"{symbol}_"):
                continue
            buy_grid = pos.get('grid_level', 0)
            if current_grid > buy_grid:
                buy_price = pos['entry_price']
                profit_pct = (price - buy_price) / buy_price
                if profit_pct > 0.003:
                    sells.append({'key': key, 'symbol': symbol, 'buy_price': buy_price, 'sell_price': price, 'buy_grid': buy_grid, 'sell_grid': current_grid, 'profit_pct': profit_pct, 'amount': pos['amount'], 'entry_time': pos['entry_time']})
        return sells
