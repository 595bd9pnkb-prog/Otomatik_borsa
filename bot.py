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

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "AMD", "NFLX", "PLTR", "UBER", "COIN", "SHOP", "SNOW", "JPM", "V", "MA", "DIS", "ONDS", "RKLB", "IREN"]
TRADE_PCT = 0.10

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

def log_to_sheets(data):
    try:
        if not GOOGLE_JSON:
            print("⚠️ GOOGLE_SHEETS_JSON eksik!")
            return
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_info = json.loads(GOOGLE_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Borsa_Log").sheet1
        sheet.append_row(data)
        print(f"✅ Sheets Kaydı Başarılı: {data[1]}")
    except Exception as e:
        print(f"🚨 Sheets Hatası: {e}")

async def process_symbol(symbol, bot, cash_to_spend):
    try:
        # Veri çekme (1 Dakikalık)
        bars = api.get_bars(symbol, '1Min', limit=50).df
        if bars.empty: return

        # Hesaplamalar
        bars['SMA_FAST'] = bars['close'].rolling(3).mean()
        bars['SMA_SLOW'] = bars['close'].rolling(8).mean()
        bars.dropna(inplace=True)

        if len(bars) < 1: return

        last_close = float(bars['close'].iloc[-1])
        last_fast = float(bars['SMA_FAST'].iloc[-1])
        last_slow = float(bars['SMA_SLOW'].iloc[-1])
        tarih = pd.Timestamp.now(tz='Europe/Istanbul').strftime('%Y-%m-%d %H:%M')

        # Mevcut pozisyonu kontrol et
        position = None
        try:
            position = api.get_position(symbol)
        except:
            position = None

        # ALIM MANTIĞI: Pozisyon yoksa ve hızlı yavaşı yukarı kestiyse
        if position is None and last_fast > last_slow:
            qty = int(cash_to_spend / last_close)
            if qty > 0:
                print(f"🚀 {symbol} ALIM EMRİ: {qty} adet")
                api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
                log_to_sheets([tarih, symbol, "ALIM", last_close, qty, last_close*qty, last_fast, last_slow, 0])
                await bot.send_message(chat_id=CHAT_ID, text=f"🚀 *{symbol}* ALINDI\nFiyat: ${last_close:.2f}\nAdet: {qty}", parse_mode='Markdown')

        # SATIŞ MANTIĞI: Pozisyon varsa ve hızlı yavaşı aşağı kestiyse
        elif position is not None and last_fast < last_slow:
            qty = int(position.qty)
            if qty > 0:
                print(f"📉 {symbol} SATIŞ EMRİ: {qty} adet")
                api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                log_to_sheets([tarih, symbol, "SATIS", last_close, qty, last_close*qty, last_fast, last_slow, 0])
                await bot.send_message(chat_id=CHAT_ID, text=f"📉 *{symbol}* SATILDI\nFiyat: ${last_close:.2f}\nAdet: {qty}", parse_mode='Markdown')

    except Exception as e:
        print(f"🚨 {symbol} Hatası: {str(e)}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        acc = api.get_account()
        cash_to_spend = float(acc.cash) * TRADE_PCT
        print(f"💰 Kasa: ${float(acc.cash):.2f} | İşlem Başı: ${cash_to_spend:.2f}")
        
        for s in SYMBOLS:
            await process_symbol(s, bot, cash_to_spend)
            await asyncio.sleep(1) # Rate limit koruması
        
        print("✅ Tarama Bitti.")
    except Exception as e:
        print(f"🚨 Ana Hata: {e}")

if __name__ == "__main__":
    asyncio.run(main())
