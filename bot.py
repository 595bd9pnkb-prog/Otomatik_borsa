import os, asyncio, pandas as pd, json, gspread
from oauth2client.service_account import ServiceAccountCredentials
import alpaca_trade_api as tradeapi
from telegram import Bot
from datetime import datetime, timedelta

# API BİLGİLERİ (Aynı kalıyor)
ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
GOOGLE_JSON = os.getenv('GOOGLE_SHEETS_JSON')

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "AMD", "NFLX", "PLTR", "UBER", "COIN", "SHOP", "SNOW", "JPM", "V", "MA", "DIS", "ONDS", "RKLB", "IREN"]
TRADE_PCT = 0.10 
STOP_LOSS_PCT = 0.02
TAKE_PROFIT_PCT = 0.05

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- YENİ: KISIRDÖNGÜ KORUMA FONKSİYONU ---
def can_buy_again(symbol):
    """Eğer hisse son 1 saat içinde satıldıysa tekrar alım yapmaz."""
    orders = api.list_orders(status='closed', limit=5, symbols=[symbol])
    for order in orders:
        if order.side == 'sell':
            # Satışın üzerinden ne kadar zaman geçtiğini kontrol et
            sell_time = order.filled_at
            if datetime.now(sell_time.tzinfo) - sell_time < timedelta(hours=1):
                return False
    return True

async def process_symbol(symbol, bot, cash_to_spend):
    try:
        bars = api.get_bars(symbol, '1Min', limit=100).df
        if bars.empty or len(bars) < 20: return

        bars['SMA_FAST'] = bars['close'].rolling(3).mean()
        bars['SMA_SLOW'] = bars['close'].rolling(8).mean()
        bars['RSI'] = calculate_rsi(bars, 14)
        bars.dropna(inplace=True)
        
        last_close = float(bars['close'].iloc[-1])
        last_fast = float(bars['SMA_FAST'].iloc[-1])
        last_slow = float(bars['SMA_SLOW'].iloc[-1])
        last_rsi = float(bars['RSI'].iloc[-1])
        tarih = pd.Timestamp.now(tz='Europe/Istanbul').strftime('%Y-%m-%d %H:%M')

        try:
            position = api.get_position(symbol)
            qty_held = int(position.qty)
            entry_price = float(position.avg_entry_price)
        except:
            qty_held = 0
            entry_price = 0

        # 1. SATIŞ SİNYALİ
        if qty_held > 0:
            sl_price = entry_price * (1 - STOP_LOSS_PCT)
            tp_price = entry_price * (1 + TAKE_PROFIT_PCT)
            
            reason = ""
            if last_fast < last_slow: reason = "SMA Kesişimi (Teknik)"
            elif last_close <= sl_price: reason = "STOP LOSS (Zarar Durdur)"
            elif last_close >= tp_price: reason = "TAKE PROFIT (Kâr Al)"
            elif last_rsi > 85: reason = "RSI Aşırı Şişkin"

            if reason != "":
                profit_loss = (last_close - entry_price) * qty_held
                msg = f"📉 *{symbol}* SATILDI\nNeden: {reason}\nFiyat: ${last_close:.2f}\nKar/Zarar: ${profit_loss:.2f}"
                await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                api.submit_order(symbol=symbol, qty=qty_held, side='sell', type='market', time_in_force='gtc')

        # 2. ALIM SİNYALİ (Korumalı)
        elif qty_held == 0:
            if last_fast > last_slow and last_rsi < 70:
                # KRİTİK KONTROL: Az önce sattıysak ALMA
                if can_buy_again(symbol):
                    qty_to_buy = int(cash_to_spend / last_close)
                    if qty_to_buy > 0:
                        msg = f"🚀 *{symbol}* ALINDI\nFiyat: ${last_close:.2f}\nRSI: {last_rsi:.1f}"
                        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                        api.submit_order(symbol=symbol, qty=qty_to_buy, side='buy', type='market', time_in_force='gtc')
                else:
                    print(f"⚠️ {symbol} için kısırdöngü koruması devrede. Alım pas geçildi.")

    except Exception as e:
        print(f"🚨 {symbol} Hatası: {e}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        acc = api.get_account()
        cash_to_spend = float(acc.cash) * TRADE_PCT
        for s in SYMBOLS:
            await process_symbol(s, bot, cash_to_spend)
            await asyncio.sleep(1)
    except Exception as e: print(f"🚨 Hata: {e}")

if __name__ == "__main__":
    asyncio.run(main())
