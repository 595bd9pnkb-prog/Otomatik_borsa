import os, asyncio, pandas as pd, json, gspread
from oauth2client.service_account import ServiceAccountCredentials
import alpaca_trade_api as tradeapi
from telegram import Bot

ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
GOOGLE_JSON = os.getenv('GOOGLE_SHEETS_JSON')

SYMBOLS = ["AAPL","MSFT","NVDA","AMZN","META","TSLA","AMD","PLTR","COIN","RKLB"]

TRADE_PCT = 0.10
STOP_LOSS_PCT = 0.02
TAKE_PROFIT_PCT = 0.05

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url='https://paper-api.alpaca.markets')

def calculate_rsi(df, period=14):

    delta = df['close'].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period).mean()
    avg_loss = loss.ewm(alpha=1/period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100/(1+rs))


async def process_symbol(symbol, bot, cash_to_spend):

    try:

        bars = api.get_bars(symbol,'5Min',limit=120).df

        if len(bars) < 50:
            return

        bars['EMA9'] = bars['close'].ewm(span=9).mean()
        bars['EMA21'] = bars['close'].ewm(span=21).mean()
        bars['RSI'] = calculate_rsi(bars)

        avg_volume = bars['volume'].mean()

        last = bars.iloc[-1]

        price = float(last['close'])
        ema9 = float(last['EMA9'])
        ema21 = float(last['EMA21'])
        rsi = float(last['RSI'])

        if avg_volume < 500000:
            return

        try:
            position = api.get_position(symbol)
            qty_held = int(position.qty)
            entry_price = float(position.avg_entry_price)
        except:
            qty_held = 0
            entry_price = 0

        # BUY SIGNAL
        if qty_held == 0 and ema9 > ema21 and rsi < 70:

            qty = int(cash_to_spend / price)

            if qty > 0:

                sl = price * (1 - STOP_LOSS_PCT)
                tp = price * (1 + TAKE_PROFIT_PCT)

                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"🚀 BUY {symbol}\nPrice:{price}\nRSI:{rsi:.1f}\nSL:{sl:.2f}\nTP:{tp:.2f}"
                )

                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side='buy',
                    type='market',
                    time_in_force='gtc'
                )

        # SELL SIGNAL
        elif qty_held > 0:

            sl = entry_price * (1 - STOP_LOSS_PCT)
            tp = entry_price * (1 + TAKE_PROFIT_PCT)

            reason = ""

            if price <= sl:
                reason = "STOP LOSS"

            elif price >= tp:
                reason = "TAKE PROFIT"

            elif ema9 < ema21:
                reason = "EMA CROSS"

            if reason:

                profit = (price-entry_price)*qty_held

                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"📉 SELL {symbol}\nReason:{reason}\nP/L:${profit:.2f}"
                )

                api.submit_order(
                    symbol=symbol,
                    qty=qty_held,
                    side='sell',
                    type='market',
                    time_in_force='gtc'
                )

    except Exception as e:
        print(f"{symbol} error {e}")


async def main():

    bot = Bot(token=TELEGRAM_TOKEN)

    acc = api.get_account()

    cash = float(acc.cash)

    cash_to_spend = cash * TRADE_PCT

    for s in SYMBOLS:

        await process_symbol(s,bot,cash_to_spend)

        await asyncio.sleep(0.3)

if __name__ == "__main__":

    asyncio.run(main())
