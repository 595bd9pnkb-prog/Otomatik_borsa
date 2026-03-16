import yfinance as yf
import pandas as pd

symbols = [
"ONDS","ASTS","RKLB","IONQ","SOFI",
"HOOD","PLTR","RBLX","OPEN","UPST"
]

def scan(symbol):

    df = yf.download(symbol,period="3mo",interval="1d")

    if len(df) < 60:
        return

    avg_volume = df["Volume"].mean()

    last = df.iloc[-1]

    volume_spike = last["Volume"] > avg_volume * 5

    breakout = last["Close"] > df["Close"].rolling(60).max().iloc[-2]

    price = last["Close"]

    if volume_spike and breakout and price < 20:

        print(f"""
🚀 POTENTIAL RUNNER

Symbol: {symbol}
Price: {price}

Volume Spike: YES
Breakout: YES
""")

for s in symbols:
    scan(s)
