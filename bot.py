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

# AYARLAR
SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "AMD",
    "NFLX", "PLTR", "UBER", "COIN", "SHOP", "SNOW", "JPM", "V", "MA", "DIS", "ONDS", "RKLB", "IREN"
]
STOP_LOSS_PCT = 0.03   # %3 Zarar Kes
TAKE_PROFIT_PCT = 0.06 # %6 Kar Al
TRADE_PCT = 0.10       # Kasadaki nakdin %10'u ile işlem yap

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1+rs))

async def process_symbol(symbol, bot, cash_to_spend):
    try:
        bars = api.get_bars(symbol, '1Hour', limit=50).df
        if bars.empty: 
            print(f"⚠️ {symbol} için veri çekilemedi!")
            return

        bars['SMA_5'] = bars['close'].rolling(5).mean()
        bars['SMA_20'] = bars['close'].rolling(20).mean()
        
        last_close = bars['close'].iloc[-1]
        last_sma5 = bars['SMA_5'].iloc[-1]
        last_sma20 = bars['SMA_20'].iloc[-1]

        # LOG: Terminale yazdırıyoruz (GitHub Actions -> Logs kısmında göreceksin)
        print(f"Sembol: {symbol} | Fiyat: {last_close} | SMA5: {last_sma5:.2f} | SMA20: {last_sma20:.2f}")

        # Basit Kontrol: SMA5 > SMA20 ise al (Kesişme beklemeden)
        if last_sma5 > last_sma20:
            qty = int(cash_to_spend / last_close) # TAM ADET TESTİ
            if qty > 0:
                print(f"✅ {symbol} için ALIM EMRİ GÖNDERİLİYOR... Adet: {qty}")
                api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
            else:
                print(f"❌ {symbol} çok pahalı, {cash_to_spend}$ ile 1 adet bile alınamıyor.")
        else:
            print(f"ℹ️ {symbol} için strateji uygun değil (SMA5 < SMA20)")

    except Exception as e:
        print(f"🚨 {symbol} HATASI: {str(e)}")

        
        # 1. MEVCUT POZİSYON KONTROLÜ (Stop Loss / Take Profit)
        if position:
            entry_price = float(position.avg_entry_price)
            current_pl_pct = (last_close - entry_price) / entry_price
            
            if current_pl_pct <= -STOP_LOSS_PCT:
                api.submit_order(symbol=symbol, qty=position.qty, side='sell', type='market', time_in_force='gtc')
                signal_msg = f"🛑 ZARAR KES (Stop Loss) yapıldı! Kayıp: %{current_pl_pct*100:.2f}"
            elif current_pl_pct >= TAKE_PROFIT_PCT:
                api.submit_order(symbol=symbol, qty=position.qty, side='sell', type='market', time_in_force='gtc')
                signal_msg = f"💰 KAR AL (Take Profit) yapıldı! Kazanç: %{current_pl_pct*100:.2f}"
            elif last_sma5 < last_sma20: # Teknik sat sinyali
                api.submit_order(symbol=symbol, qty=position.qty, side='sell', type='market', time_in_force='gtc')
                signal_msg = f"📉 TEKNİK SAT (Trend Değişimi) yapıldı."

        # 2. YENİ ALIM SİNYALİ (Eğer pozisyon yoksa)
        elif not position:
            if last_sma5 > last_sma20:
                qty = cash_to_spend / last_close
                if qty > 0:
                    api.submit_order(
                        symbol=symbol,
                        qty=round(qty, 2),
                        side='buy',
                        type='market',
                        time_in_force='gtc'
                    )
                    signal_msg = f"🚀 YENİ ALIM! Hedef: +%{TAKE_PROFIT_PCT*100}, Stop: -%{STOP_LOSS_PCT*100}"

        # Telegram Bildirimi (Sadece işlem olduğunda)
        if signal_msg:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})
            ax1.plot(bars.index, bars['close'], label='Fiyat', color='black')
            ax1.plot(bars.index, bars['SMA_5'], label='SMA 5', color='orange')
            ax1.plot(bars.index, bars['SMA_20'], label='SMA 20', color='blue')
            ax1.set_title(f"{symbol} İşlem Detayı")
            ax1.legend()
            ax2.plot(bars.index, bars['RSI'], label='RSI', color='purple')
            ax2.axhline(70, color='red', linestyle='--'); ax2.axhline(30, color='green', linestyle='--')
            
            buf = io.BytesIO(); plt.savefig(buf, format='png'); buf.seek(0)
            msg = f"🔔 *{symbol}*\n{signal_msg}\nFiyat: ${last_close:.2f}\nRSI: {last_rsi:.2f}"
            await bot.send_photo(chat_id=CHAT_ID, photo=buf, caption=msg, parse_mode='Markdown')
            plt.close()

    except Exception as e:
        print(f"{symbol} hatası: {e}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    account = api.get_account()
    cash_to_spend = float(account.cash) * TRADE_PCT
    
    for symbol in SYMBOLS:
        await process_symbol(symbol, bot, cash_to_spend)
        await asyncio.sleep(1)
    
    updated_acc = api.get_account()
    msg = f"✅ Tarama bitti.\nToplam Equity: ${float(updated_acc.equity):,.2f}\nNakit: ${float(updated_acc.cash):,.2f}"
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(main())
