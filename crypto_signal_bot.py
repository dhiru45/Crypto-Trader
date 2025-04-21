import ccxt
import pandas as pd
import time
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
import requests

import sqlite3
from datetime import datetime

# --- Initialize SQLite DB ---
def init_db():
    conn = sqlite3.connect("trade_signals.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            signal TEXT,
            price REAL,
            strategy TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# --- Telegram Settings ---
TELEGRAM_TOKEN = '7926616723:AAEceR0CDRXchNmOkw8vrInDXjQ40e3n_-A'
CHAT_ID = '425700500'

# --- Initialize Exchange ---
exchange = ccxt.binance()
symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'MATIC/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LTC/USDT']  # You can add more

# --- Send Telegram Alert ---
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    response = requests.post(url, data=payload)
    print("Telegram response:", response.status_code, response.text)

def fetch_ohlcv(symbol, timeframe='5m', limit=100):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    print("Fetching Binance prices...")
    return df






def support_resistance_strategy(df, rsi_period=14, bounce_tolerance=0.005):
    if df is None or df.empty or len(df) < rsi_period + 2:
        return None

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    recent_lows = df['low'].rolling(10).min()
    recent_highs = df['high'].rolling(10).max()
    support = recent_lows.iloc[-2]
    resistance = recent_highs.iloc[-2]

    current_price = df['close'].iloc[-1]

    if abs(current_price - support) / support < bounce_tolerance and current_rsi < 30:
        return {"signal": "BUY", "strategy": "SupportBounce_RSI"}
    elif abs(current_price - resistance) / resistance < bounce_tolerance and current_rsi > 70:
        return {"signal": "SELL", "strategy": "ResistanceBounce_RSI"}

    return None



def breakout_volume_spike_strategy(df, volume_spike_threshold=1.5, breakout_multiplier=1.02):
    if df is None or df.empty:
        return None

    # Calculate the 20-period average volume
    avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
    current_volume = df['volume'].iloc[-1]

    # Calculate the breakout price (e.g., the last high price * breakout multiplier)
    breakout_price = df['high'].iloc[-1] * breakout_multiplier
    current_price = df['close'].iloc[-1]

    # Detect breakout and volume spike
    if current_price > breakout_price and current_volume > avg_volume * volume_spike_threshold:
        return "BUY"
    elif current_price < breakout_price and current_volume > avg_volume * volume_spike_threshold:
        return "SELL"

    return None



def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi




def apply_strategy(df):
    # Strategy 1: RSI + EMA Crossover
    ema_short = df['close'].ewm(span=9, adjust=False).mean()
    ema_long = df['close'].ewm(span=21, adjust=False).mean()
    rsi = calculate_rsi(df['close'], 14)

    if ema_short.iloc[-2] < ema_long.iloc[-2] and ema_short.iloc[-1] > ema_long.iloc[-1] and rsi.iloc[-1] < 70:
        return "BUY"
    elif ema_short.iloc[-2] > ema_long.iloc[-2] and ema_short.iloc[-1] < ema_long.iloc[-1] and rsi.iloc[-1] > 30:
        return "SELL"

    # Strategy 2: Support/Resistance Bounce with RSI filter
    signal = support_resistance_strategy(df)
    if signal:
        return signal["signal"], signal["strategy"]

    # Strategy 3: Breakout + Volume Spike
    breakout_signal = breakout_volume_spike_strategy(df)
    if breakout_signal:
        return breakout_signal, "Breakout + Volume Spike"

    return None








## Saving Signals into the Database for Dashboaard 
def save_signal(symbol, signal_type, price, strategy_name):
    conn = sqlite3.connect("trade_signals.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO signals (symbol, signal, price, strategy, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (symbol, signal_type, price, strategy_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()


## Scanning Market to find the trades
def scan_market():
    print("Fetching Binance prices...")

    for symbol in symbols:
        try:
            print(f"\n⏳ Checking {symbol}...")
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            print("Running strategy...")
            signal = apply_strategy(df)

            if signal:
                price = df['close'].iloc[-1]

                # Check if signal is a tuple (new strategy format)
                if isinstance(signal, tuple):
                    action, strategy_name = signal
                else:
                    action = signal
                    strategy_name = "RSI + EMA Crossover"

                message = f"🚨 Signal: {action} {symbol} at {price:.2f} | Strategy: {strategy_name}"
                send_telegram_message(message)
                print("✅ Signal sent:", message)
                save_signal(symbol, action, price, strategy_name)

            else:
                print("No signal for", symbol)

        except Exception as e:
            print(f"⚠️ Error checking {symbol}: {str(e)}")

    print("\n✅ Market scan complete.")


if __name__ == "__main__":
    init_db()
    while True:
        print("\n🔁 Running market scan...")
        scan_market()
        time.sleep(300)  # Every 5 minutes

    
