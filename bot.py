import os
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
import io
import alpaca_trade_api as tradeapi
from telegram import Bot

# API ve Gizli Bilgiler
ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "AMD",
    "NFLX", "PLTR", "UBER", "COIN", "SHOP", "SNOW", "JPM", "V", "MA", "DIS", "ONDS", "RKLB", "IREN"
]

STOP_LOSS_PCT = 0.03   
TAKE_PROFIT_PCT = 0.06 
TRADE_PCT = 0.10       

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1+rs))

async def process_symbol(symbol, bot, cash_to_spend):
    print(f"--- {symbol} ANALİZ EDİLİYOR ---")
    try:
        # 1. Veri Çekme
        bars = api.get_bars(symbol, '1Hour', limit=50).df
        if bars.empty:
            print(f"⚠️ {symbol} için veri boş geldi!")
            return

        # 2. Teknik Hesaplamalar
        bars['SMA_5'] = bars['close'].rolling(5).mean()
        bars['SMA_20'] = bars['close'].rolling(20).mean()
        bars['RSI'] = calculate_rsi(bars['close'])

        last_close = bars['close'].iloc[-1]
        last_sma5 = bars['SMA_5'].iloc[-1]
        last_sma20 = bars['SMA_20'].iloc[-1]
        last_rsi = bars['RSI'].iloc[-1]
        
        print(f"Fiyat: {last_close} | SMA5: {last_sma5:.2f} | SMA20: {last_sma20:.2f} | RSI: {last_rsi:.2f}")

        # 3. Mevcut Pozisyonu Kontrol Et
        position = None
        try:
            position = api.get_position(symbol)
        except:
            pass

        signal_msg = ""
        
        # 4. SATIŞ MANTIĞI (Pozisyon Varsa)
        if position:
            entry_price = float(position.avg_entry_price)
            current_pl_pct = (last_close - entry_price) / entry_price
            print(f"Mevcut Pozisyon: %{current_pl_pct*100:.2f} kâr/zarar")

            if current_pl_pct <= -STOP_LOSS_PCT:
                api.submit_order(symbol=symbol, qty=position.qty, side='sell', type='market', time_in_force='gtc')
                signal_msg = f"🛑 ZARAR KES! Kayıp: %{current_pl_pct*100:.2f}"
            elif current_pl_pct >= TAKE_PROFIT_PCT:
                api.submit_order(symbol=symbol, qty=position.qty, side='sell', type='market', time_in_force='gtc')
                signal_msg = f"💰 KAR AL! Kazanç: %{current_pl_pct*100:.2f}"
            elif last_sma5 < last_sma20:
                api.submit_order(symbol=symbol, qty=position.qty, side='sell', type='market', time_in_force='gtc')
                signal_msg = f"📉 TREND DEĞİŞTİ, SATILDI."

        # 5. ALIM MANTIĞI (Pozisyon Yoksa)
        else:
            # Şimdilik sadece SMA5 > SMA20 ise al diyoruz (Test için kesişme şartını kaldırdık)
            if last_sma5 > last_sma20:
                qty = int(cash_to_spend / last_close) # Güvenli olması için küsuratsız adet
                if qty > 0:
                    print(f"✅ ALIM YAPILIYOR: {qty} Adet")
                    api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
                    signal_msg = f"🚀 ALIM YAPILDI! Hedef: +%{TAKE_PROFIT_PCT*100}"
                else:
                    print("❌ Bakiye 1 adet almaya yetmiyor.")

        # 6. Telegram Bildirimi
        if signal_msg:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})
            ax1.plot(bars.index, bars['close'], label='Fiyat', color='black')
            ax1.plot(bars.index, bars['SMA_5'], label='SMA 5', color='orange')
            ax1.plot(bars.index, bars['SMA_20'], label='SMA 20', color='blue')
            ax1.legend(); ax1.set_title(f"{symbol} İşlem")
            ax2.plot(bars.index, bars['RSI'], color='purple'); ax2.axhline(70, color='red'); ax2.axhline(30, color='green')
            
            buf = io.BytesIO(); plt.savefig(buf, format='png'); buf.seek(0)
            await bot.send_photo(chat_id=CHAT_ID, photo=buf, caption=f"🔔 *{symbol}*\n{signal_msg}", parse_mode='Markdown')
            plt.close()

    except Exception as e:
        print(f"🚨 {symbol} HATASI: {str(e)}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    acc = api.get_account()
    cash_to_spend = float(acc.cash) * TRADE_PCT
    print(f"Cüzdan: {acc.cash} | İşlem Başına Nakit: {cash_to_spend}")

    for symbol in SYMBOLS:
        await process_symbol(symbol, bot, cash_to_spend)
        await asyncio.sleep(1)

    final_acc = api.get_account()
    msg = f"✅ Tarama Bitti.\nEquity: ${float(final_acc.equity):,.2f}\nNakit: ${float(final_acc.cash):,.2f}"
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(main())
