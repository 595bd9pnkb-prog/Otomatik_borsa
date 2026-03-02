import os, asyncio, pandas as pd, matplotlib.pyplot as plt, io
import alpaca_trade_api as tradeapi
from telegram import Bot

# API BİLGİLERİ
ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "AMD", "NFLX", "PLTR", "UBER", "COIN", "SHOP", "SNOW", "JPM", "V", "MA", "DIS", "ONDS", "RKLB", "IREN"]
TRADE_PCT = 0.10

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

async def process_symbol(symbol, bot, cash_to_spend):
    print(f"--- {symbol} ANALİZ EDİLİYOR ---")
    try:
        # ÇÖZÜM: '1Hour' yerine '1Min' kullanarak veri boşluğu hatasını gideriyoruz
        bars = api.get_bars(symbol, '1Min', limit=50).df
        if bars.empty: return

        # Kısa vadeli SMA değerleri (Dakikalıkta hızlı tepki için 3 ve 8)
        bars['SMA_FAST'] = bars['close'].rolling(3).mean()
        bars['SMA_SLOW'] = bars['close'].rolling(8).mean()
        bars.dropna(inplace=True)

        if len(bars) < 1:
            print(f"⚠️ {symbol} için veri yetersiz.")
            return

        last_close = bars['close'].iloc[-1]
        last_fast = bars['SMA_FAST'].iloc[-1]
        last_slow = bars['SMA_SLOW'].iloc[-1]
        
        print(f"Fiyat: {last_close} | Hızlı: {last_fast:.2f} | Yavaş: {last_slow:.2f}")

        position = None
        try: position = api.get_position(symbol)
        except: pass

        signal_msg = ""
        # ALIM: Hızlı ortalama yavaşı yukarı kestiğinde
        if not position and last_fast > last_slow:
            qty = int(cash_to_spend / last_close)
            if qty > 0:
                api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
                signal_msg = "🚀 DAKİKALIK ALIM YAPILDI!"
        
        # SATIŞ: Hızlı ortalama yavaşın altına düştüğünde
        elif position and last_fast < last_slow:
            api.submit_order(symbol=symbol, qty=position.qty, side='sell', type='market', time_in_force='gtc')
            signal_msg = "📉 DAKİKALIK SATIŞ YAPILDI!"

        if signal_msg:
            msg = f"🔔 *{symbol}*\n{signal_msg}\nFiyat: ${last_close:.2f}"
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')

    except Exception as e: print(f"🚨 {symbol} HATASI: {e}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    acc = api.get_account()
    cash_to_spend = float(acc.cash) * TRADE_PCT
    for s in SYMBOLS:
        await process_symbol(s, bot, cash_to_spend)
        await asyncio.sleep(0.5)
    print("✅ Tarama Bitti.")

if __name__ == "__main__": asyncio.run(main())
