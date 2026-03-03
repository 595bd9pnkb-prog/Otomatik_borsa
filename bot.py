import os, asyncio, pandas as pd, json, gspread
from oauth2client.service_account import ServiceAccountCredentials
import alpaca_trade_api as tradeapi
from telegram import Bot

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
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_info = json.loads(GOOGLE_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        # Dosyayı aç ve İLK sayfayı seç (İsimden bağımsız)
        sheet = client.open("Borsa_Log").get_worksheet(0)
        sheet.append_row(data)
        print(f"✅ Tabloya eklendi: {data[1]}")
    except Exception as e:
        print(f"🚨 Tablo Yazma Hatası: {e}")

async def process_symbol(symbol, bot, cash_to_spend):
    try:
        bars = api.get_bars(symbol, '1Min', limit=50).df
        if bars.empty: return

        bars['SMA_FAST'] = bars['close'].rolling(3).mean()
        bars['SMA_SLOW'] = bars['close'].rolling(8).mean()
        bars.dropna(inplace=True)
        
        last_close = float(bars['close'].iloc[-1])
        last_fast = float(bars['SMA_FAST'].iloc[-1])
        last_slow = float(bars['SMA_SLOW'].iloc[-1])
        tarih = pd.Timestamp.now(tz='Europe/Istanbul').strftime('%Y-%m-%d %H:%M')

        try:
            position = api.get_position(symbol)
            qty_held = int(position.qty)
        except:
            qty_held = 0

        # ALIM SİNYALİ
        if qty_held == 0 and last_fast > last_slow:
            qty_to_buy = int(cash_to_spend / last_close)
            if qty_to_buy > 0:
                # ÖNCE TABLOYA YAZ VE MESAJ AT (Garanti yöntem)
                log_to_sheets([tarih, symbol, "ALIM", last_close, qty_to_buy, last_close*qty_to_buy, last_fast, last_slow, 0])
                await bot.send_message(chat_id=CHAT_ID, text=f"🚀 *{symbol}* Sinyali Yakalandı\nFiyat: ${last_close}")
                # SONRA EMİR GÖNDER (Para yetmezse bile üstteki işlemler yapılmış olur)
                try:
                    api.submit_order(symbol=symbol, qty=qty_to_buy, side='buy', type='market', time_in_force='gtc')
                except Exception as e:
                    print(f"⚠️ {symbol} Borsaya iletilemedi (Bakiye yetersiz olabilir): {e}")

        # SATIŞ SİNYALİ
        elif qty_held > 0 and last_fast < last_slow:
            log_to_sheets([tarih, symbol, "SATIS", last_close, qty_held, last_close*qty_held, last_fast, last_slow, 0])
            await bot.send_message(chat_id=CHAT_ID, text=f"📉 *{symbol}* Satış Sinyali\nFiyat: ${last_close}")
            try:
                api.submit_order(symbol=symbol, qty=qty_held, side='sell', type='market', time_in_force='gtc')
            except Exception as e:
                print(f"⚠️ {symbol} Satılamadı: {e}")

    except Exception as e:
        print(f"🚨 {symbol} Hatası: {e}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    # Bakiye kontrolünü ve harcamayı manuel sabitleyelim ki log dolsun
    cash_to_spend = 10000 # Test için her hisseye 10 bin dolarlık bütçe ayır
    for s in SYMBOLS:
        await process_symbol(s, bot, cash_to_spend)
        await asyncio.sleep(1)
    print("✅ Tarama Bitti.")

if __name__ == "__main__":
    asyncio.run(main())
