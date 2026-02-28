import os
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
import io
import alpaca_trade_api as tradeapi
from telegram import Bot

# GitHub Secrets verileri
ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# İzleme Listesi
SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "AMD",
    "NFLX", "PLTR", "UBER", "COIN", "SHOP", "SNOW", "JPM", "V", "MA", "DIS", "ONDS", "RKLB", "IREN"
]

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

async def process_symbol(symbol, bot):
    try:
        # Veri çekme (Saatlik periyot)
        bars = api.get_bars(symbol, '1Hour', limit=50).df
        if bars.empty: return

        # Teknik Göstergeler (SMA 5 ve SMA 20)
        bars['SMA_5'] = bars['close'].rolling(5).mean()
        bars['SMA_20'] = bars['close'].rolling(20).mean()
        
        last_close = bars['close'].iloc[-1]
        prev_sma5 = bars['SMA_5'].iloc[-2]
        last_sma5 = bars['SMA_5'].iloc[-1]
        last_sma20 = bars['SMA_20'].iloc[-1]

        # STRATEJİ: Golden Cross (Kısa vade uzun vadeyi yukarı keserse)
        signal = None
        if last_sma5 > last_sma20 and prev_sma5 <= last_sma20:
            signal = "🚀 ALIM SİNYALİ (Golden Cross)"
            # api.submit_order(symbol=symbol, qty=1, side='buy', type='market', time_in_force='gtc')
        elif last_sma5 < last_sma20 and prev_sma5 >= last_sma20:
            signal = "📉 SATIŞ SİNYALİ (Death Cross)"
            # api.submit_order(symbol=symbol, qty=1, side='sell', type='market', time_in_force='gtc')

        # Sadece sinyal varsa mesaj gönder
        if signal:
            plt.figure(figsize=(10, 5))
            plt.plot(bars.index, bars['close'], label='Fiyat', color='black', alpha=0.7)
            plt.plot(bars.index, bars['SMA_5'], label='SMA 5', color='orange')
            plt.plot(bars.index, bars['SMA_20'], label='SMA 20', color='blue')
            plt.title(f"{symbol} - {signal}")
            plt.legend()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            
            msg = f"🔔 *{symbol}* - {signal}\nFiyat: ${last_close:.2f}"
            await bot.send_photo(chat_id=CHAT_ID, photo=buf, caption=msg, parse_mode='Markdown')
            plt.close()

    except Exception as e:
        print(f"{symbol} hatası: {e}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    print(f"{len(SYMBOLS)} hisse taranıyor...")
    
    # Tüm hisseleri sırayla işle
    for symbol in SYMBOLS:
        await process_symbol(symbol, bot)
        await asyncio.sleep(1) # API limitlerine takılmamak için kısa bir bekleme

    # Genel portföy özeti gönder
    account = api.get_account()
    summary = f"💰 *Genel Durum*\nNakit: ${float(account.cash):,.2f}\nToplam Portföy: ${float(account.equity):,.2f}"
    await bot.send_message(chat_id=CHAT_ID, text=summary, parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(main())
