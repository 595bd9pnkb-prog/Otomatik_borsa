async def process_symbol(symbol, bot, cash_to_spend):
    try:
        bars = api.get_bars(symbol, '1Min', limit=50).df
        if bars.empty: return

        # Teknik Analiz
        bars['SMA_FAST'] = bars['close'].rolling(3).mean()
        bars['SMA_SLOW'] = bars['close'].rolling(8).mean()
        bars.dropna(inplace=True)
        
        last_close = float(bars['close'].iloc[-1])
        last_fast = float(bars['SMA_FAST'].iloc[-1])
        last_slow = float(bars['SMA_SLOW'].iloc[-1])
        tarih = pd.Timestamp.now(tz='Europe/Istanbul').strftime('%Y-%m-%d %H:%M')

        # Pozisyon Kontrolü
        try:
            position = api.get_position(symbol)
            qty_held = int(position.qty)
            entry_price = float(position.avg_entry_price)
        except:
            qty_held = 0
            entry_price = 0

        # --- SATIŞ KONTROLÜ (ÖNCE BURASI ÇALIŞIR) ---
        was_sold = False # Bu döngüde satıldı mı kontrolü
        if qty_held > 0:
            sl_price = entry_price * (1 - STOP_LOSS_PCT)
            tp_price = entry_price * (1 + TAKE_PROFIT_PCT)
            
            reason = ""
            if last_fast < last_slow:
                reason = "SMA Kesişimi (Teknik)"
            elif last_close <= sl_price:
                reason = "STOP LOSS (Zarar Durdur)"
            elif last_close >= tp_price:
                reason = "TAKE PROFIT (Kâr Al)"

            if reason != "":
                profit_loss = (last_close - entry_price) * qty_held
                log_to_sheets([tarih, symbol, "SATIS", last_close, qty_held, last_close*qty_held, last_fast, last_slow, profit_loss, reason])
                
                msg = (f"📉 *{symbol}* SATILDI\n❓ Neden: {reason}\n💵 Fiyat: ${last_close:.2f}\n📊 Kar/Zarar: ${profit_loss:.2f}")
                await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                api.submit_order(symbol=symbol, qty=qty_held, side='sell', type='market', time_in_force='gtc')
                was_sold = True # Satış yapıldı, bu turda bir daha alma!

        # --- ALIM KONTROLÜ ---
        # Eğer elimizde yoksa VE bu turda az önce satmadıysak VE teknik "AL" diyorsa
        if qty_held == 0 and not was_sold and last_fast > last_slow:
            if cash_to_spend <= 0: return
            
            # Ekstra Güvenlik: Son satılan fiyatın üzerinde miyiz kontrolü eklenebilir
            qty_to_buy = int(cash_to_spend / last_close)
            if qty_to_buy > 0:
                sl_price = last_close * (1 - STOP_LOSS_PCT)
                tp_price = last_close * (1 + TAKE_PROFIT_PCT)
                
                log_to_sheets([tarih, symbol, "ALIM", last_close, qty_to_buy, last_close*qty_to_buy, last_fast, last_slow, 0, f"SL: {sl_price:.2f}", f"TP: {tp_price:.2f}"])
                msg = (f"🚀 *{symbol}* ALINDI\n💰 Fiyat: ${last_close:.2f}\n🛑 SL: ${sl_price:.2f}\n🎯 TP: ${tp_price:.2f}")
                await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                api.submit_order(symbol=symbol, qty=qty_to_buy, side='buy', type='market', time_in_force='gtc')

    except Exception as e:
        print(f"🚨 {symbol} Hatası: {e}")
