import os
import alpaca_trade_api as tradeapi

# API BİLGİLERİ (GitHub Secrets'tan alır)
ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')

# API BAĞLANTISI
api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

def force_reset():
    try:
        print("🚀 Sıfırlama işlemi başlatılıyor...")
        
        # 1. Tüm açık emirleri iptal et
        api.cancel_all_orders()
        print("✅ Tüm bekleyen emirler iptal edildi.")

        # 2. Tüm açık pozisyonları kapat (Hepsini sat)
        api.close_all_positions()
        print("✅ Tüm açık pozisyonlar piyasa fiyatından satıldı.")
        
        # 3. Hesap bilgilerini kontrol et
        account = api.get_account()
        print(f"💰 İşlem Tamam! Güncel Nakit: ${account.cash}")
        print("⚠️ Not: Alpaca Paper Trading'de tam $100.000'a dönmek için arayüz şarttır.")
        print("Ancak bu kod elindeki 'hayalet' hisseleri temizledi, artık botun düzgün çalışacak.")

    except Exception as e:
        print(f"🚨 Hata oluştu: {e}")

if __name__ == "__main__":
    force_reset()
