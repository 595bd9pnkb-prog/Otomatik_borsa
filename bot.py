import os, asyncio, pandas as pd, json, gspread
from oauth2client.service_account import ServiceAccountCredentials
import alpaca_trade_api as tradeapi
from telegram import Bot

# API VE GİZLİ BİLGİLER
ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
GOOGLE_JSON = os.getenv('GOOGLE_SHEETS_JSON')

# AYARLAR
SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "AMD", "NFLX", "PLTR", "UBER", "COIN", "SHOP", "SNOW", "JPM", "V", "MA", "DIS", "ONDS", "RKLB", "IREN"]
TRADE_PCT = 0.10 
STOP_LOSS_PCT = 0.02
TAKE_PROFIT_PCT = 0.05
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70 # 70 üstünde alım yapma

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def log_to_sheets(data):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_info = json.loads(GOOGLE_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Borsa_Log").get_worksheet(0)
        sheet.append_row(data)
    except Exception as e:
        print(f"🚨 Tablo Yazma Hatası: {e}")

async def process_symbol(symbol, bot, cash_to_spend):
    try:
        bars = api.get_bars(symbol, '1Min', limit=100).df
        if len(bars) < 20: return

        # Teknik Göstergeler
        bars['SMA_FAST'] = bars['close'].rolling(3).mean()
        bars['SMA_SLOW'] = bars['close'].rolling(8).mean()
        bars['RSI'] = calculate_rsi(bars, RSI_PERIOD)
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

        was_sold = False

        # 1. SATIŞ KONTROLÜ
        if qty_held > 0:
            sl_price = entry_price * (1 - STOP_LOSS_PCT)
            tp_price = entry_price * (1 + TAKE_PROFIT_PCT)
            
            reason = ""
            if last_fast < last_slow:
                reason = "SMA Kesişimi"
            elif last_close <= sl_price:
                reason = "STOP LOSS"
            elif last_close >= tp_price:
                reason = "TAKE PROFIT"
            elif last_rsi > 85: # Ekstra koruma: RSI uçtuysa sat
                reason = "Aşırı Alım (RSI > 85)"

            if reason != "":
                profit_loss = (last_close - entry_price) * qty_held
                log_to_sheets([tarih, symbol, "SATIS", last_close, qty_held, last_close*qty_held, f"RSI: {last_rsi:.1f}", reason, profit_loss])
                await bot.send_message(chat_id=CHAT_ID, text=f"📉 *{symbol}* SATILDI\nNeden: {reason}\nKar/Zarar: ${profit_loss:.2f}\nRSI: {last_rsi:.1f}")
                api.submit_order(symbol=symbol, qty=qty_held, side='sell', type='market', time_in_force='gtc')
                was_sold = True

        # 2. ALIM KONTROLÜ
        if qty_held == 0 and not was_sold and last_fast > last_slow:
            # Sadece RSI 70'ten küçükse al (Aşırı şişmiş kağıda girme)
            if last_rsi < RSI_OVERBOUGHT:
                qty_to_buy = int(cash_to_spend / last_close)
                if qty_to_buy > 0:
                    sl_price = last_close * (1 - STOP_LOSS_PCT)
                    tp_price = last_close * (1 + TAKE_PROFIT_PCT)
                    
                    log_to_sheets([tarih, symbol, "ALIM", last_close, qty_to_buy, last_close*qty_to_buy, f"RSI: {last_rsi:.1f}", f"SL:{sl_price:.2f} TP:{tp_price:.2f}", 0])
                    await bot.send_message(chat_id=CHAT_ID, text=f"🚀 *{symbol}* ALINDI\nFiyat: ${last_close}\nRSI: {last_rsi:.1f}\nSL: ${sl_price:.2f}\nTP: ${tp_price:.2f}")
                    api.submit_order(symbol=symbol, qty=qty_to_buy, side='buy', type='market', time_in_force='gtc')
            else:
                print(f"⏭️ {symbol} pas geçildi, RSI çok yüksek: {last_rsi:.1f}")

    except Exception as e:
        print(f"🚨 {symbol} Hatası: {e}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        acc = api.get_account()
        current_cash = float(acc.cash)
        cash_to_spend = current_cash * TRADE_PCT if current_cash > 0 else 0
        print(f"💰 Kasa: ${current_cash} | RSI Filtresi Aktif.")

        for s in SYMBOLS:
            await process_symbol(s, bot, cash_to_spend)
            await asyncio.sleep(1)
        print("✅ Tarama Bitti.")
    except Exception as e:
        print(f"🚨 Ana Hata: {e}")

if __name__ == "__main__":
    asyncio.run(main())
