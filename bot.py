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
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_info = json.loads(GOOGLE_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        
        # Dosyayı isminden bulmaya çalış
        spreadsheet = client.open("Borsa_Log")
        # İlk sayfayı (hangisi olursa olsun) seç - En garantisi budur
        sheet = spreadsheet.get_worksheet(0) 
        
        sheet.append_row(data)
        print(f"✅ TABLOYA YAZILDI: {data[1]}")
    except gspread.exceptions.SpreadsheetNotFound:
        print("🚨 HATA: 'Borsa_Log' isimli dosya bulunamadı! İsim tam aynı mı?")
    except gspread.exceptions.APIError as e:
        print(f"🚨 HATA: Google API Hatası (İzin sorunu olabilir): {e}")
    except Exception as e:
        print(f"🚨 HATA: Beklenmedik bir sorun oluştu: {e}")


async def process_symbol(symbol, bot, cash_to_spend):
    try:
        bars = api.get_bars(symbol, '1Min', limit=50).df
        if bars.empty: return

        bars['SMA_FAST'] = bars['close'].rolling(3).mean()
        bars['SMA_SLOW'] = bars['close'].rolling(8).mean()
        bars.dropna(inplace=True)

        if len(bars) < 1: return

        last_close = float(bars['close'].iloc[-1])
        last_fast = float(bars['SMA_FAST'].iloc[-1])
        last_slow = float(bars['SMA_SLOW'].iloc[-1])
        tarih = pd.Timestamp.now(tz='Europe/Istanbul').strftime('%H:%M')

        # Pozisyon kontrolü
        try:
            position = api.get_position(symbol)
            qty_held = int(position.qty)
        except:
            qty_held = 0

        # ALIM MANTIĞI
        if qty_held == 0 and last_fast > last_slow:
            qty_to_buy = int(cash_to_spend / last_close)
            if qty_to_buy > 0:
                api.submit_order(symbol=symbol, qty=qty_to_buy, side='buy', type='market', time_in_force='gtc')
                log_to_sheets([tarih, symbol, "ALIM", last_close, qty_to_buy, last_close*qty_to_buy, last_fast, last_slow, 0])
                await bot.send_message(chat_id=CHAT_ID, text=f"🚀 *{symbol}* ALINDI\nFiyat: ${last_close}")

        # SATIŞ MANTIĞI
        elif qty_held > 0 and last_fast < last_slow:
            # Emir hatası olsa bile kodun devam etmesi için try-except içine aldık
            try:
                api.submit_order(symbol=symbol, qty=qty_held, side='sell', type='market', time_in_force='gtc')
                log_to_sheets([tarih, symbol, "SATIS", last_close, qty_held, last_close*qty_held, last_fast, last_slow, 0])
                await bot.send_message(chat_id=CHAT_ID, text=f"📉 *{symbol}* SATILDI\nFiyat: ${last_close}")
            except Exception as e:
                print(f"⚠️ {symbol} Satış Emri Hatası: {e}")

    except Exception as e:
        print(f"🚨 {symbol} Genel Hata: {e}")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    acc = api.get_account()
    # Kasa eksiye düştüyse alım yapmaması için kontrol
    cash = 100000
    if cash <= 0:
        print("🚨 Bakiye yetersiz veya eksi!")
        # Test amaçlı işlem yapması için nakit miktarını elle küçük bir rakam yapabilirsin
        # cash = 10000 
    
    cash_to_spend = max(0, cash * TRADE_PCT)
    print(f"💰 Kasa: ${cash} | İşlem Başı: ${cash_to_spend}")

    for s in SYMBOLS:
        await process_symbol(s, bot, cash_to_spend)
        await asyncio.sleep(1)
    print("✅ Tarama Bitti.")

if __name__ == "__main__":
    asyncio.run(main())
