import ccxt
import pandas as pd
import time
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
import requests

#import sqlite3
from datetime import datetime

from db import SessionLocal
from models import TradeSignal

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import TradeSignal, Base

DATABASE_URL = os.getenv("DATABASE_URL")  # This will be loaded from environment variable
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables if they don't exist (run only once, or keep it here for simplicity)
Base.metadata.create_all(bind=engine)

# --- Initialize SQLite DB ---
#def init_db():
 #   conn = sqlite3.connect("trade_signals.db")
  #  cursor = conn.cursor()
   # cursor.execute("""
    #    CREATE TABLE IF NOT EXISTS signals (
     #       id INTEGER PRIMARY KEY AUTOINCREMENT,
      #      symbol TEXT,
       #     signal TEXT,
       #     price REAL,
       #     strategy TEXT,
       #     timestamp TEXT
       # )
    #""")
    #conn.commit()
    #conn.close()

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




def ma_crossover_strategy(df, short_window=20, long_window=50):
    df['MA_short'] = df['close'].rolling(window=short_window).mean()
    df['MA_long'] = df['close'].rolling(window=long_window).mean()

    if df['MA_short'].isnull().any() or df['MA_long'].isnull().any():
        return None  # Not enough data yet

    if (
        df['MA_short'].iloc[-2] < df['MA_long'].iloc[-2] and
        df['MA_short'].iloc[-1] > df['MA_long'].iloc[-1]
    ):
        print("✅ MA Crossover Buy Signal")
        return {
            'strategy': 'MA Crossover',
            'signal': 'buy',
            'price': df['close'].iloc[-1],
            'details': f'Short MA ({short_window}) crossed above Long MA ({long_window})'
        }

    elif (
        df['MA_short'].iloc[-2] > df['MA_long'].iloc[-2] and
        df['MA_short'].iloc[-1] < df['MA_long'].iloc[-1]
    ):
        print("❌ MA Crossover Sell Signal")
        return {
            'strategy': 'MA Crossover',
            'signal': 'sell',
            'price': df['close'].iloc[-1],
            'details': f'Short MA ({short_window}) crossed below Long MA ({long_window})'
        }

    return None





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
    # --- Indicators ---
    ema_short = df['close'].ewm(span=9, adjust=False).mean()
    ema_long = df['close'].ewm(span=21, adjust=False).mean()
    rsi = calculate_rsi(df['close'], 14)
    current_price = df['close'].iloc[-1]
    macd = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()  # MACD Line
    signal_line = macd.ewm(span=9, adjust=False).mean()  # Signal Line
    
    print(f"Price: {current_price:.2f}, EMA9: {ema_short.iloc[-1]:.2f}, EMA21: {ema_long.iloc[-1]:.2f}, RSI: {rsi.iloc[-1]:.2f}")

    # --- Strategy 1: EMA Crossover + RSI
    if (
        ema_short.iloc[-2] < ema_long.iloc[-2] and
        ema_short.iloc[-1] > ema_long.iloc[-1] and
        rsi.iloc[-1] < 75
    ):
        print("🔹 EMA crossover + RSI < 75: BUY signal")
        return "BUY", "RSI + EMA Crossover"

    elif (
        ema_short.iloc[-2] > ema_long.iloc[-2] and
        ema_short.iloc[-1] < ema_long.iloc[-1] and
        rsi.iloc[-1] > 25
    ):
        print("🔹 EMA crossover + RSI > 25: SELL signal")
        return "SELL", "RSI + EMA Crossover"

    # --- Strategy 2: Support/Resistance Bounce (with RSI filter)
    sr_signal = support_resistance_strategy(df)
    if sr_signal:
        print(f"🔹 Support/Resistance Bounce Signal: {sr_signal}")
        return sr_signal["signal"], sr_signal["strategy"]

    # --- Strategy 3: Breakout with Volume Spike
    recent_high = df['high'][:-1].max()
    breakout_price = recent_high * 1.005  # reduced from 1.02
    avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
    current_volume = df['volume'].iloc[-1]

    print(f"Breakout target: {breakout_price:.2f}, Current price: {current_price:.2f}, Avg vol: {avg_volume:.2f}, Current vol: {current_volume:.2f}")

    if current_price > breakout_price and current_volume > avg_volume * 1.2:
        print("🔹 Breakout + Volume Spike: BUY signal")
        return "BUY", "Breakout + Volume Spike"

    elif current_price < breakout_price and current_volume > avg_volume * 1.2:
        print("🔹 Breakdown + Volume Spike: SELL signal")
        return "SELL", "Breakout + Volume Spike"

    # --- Strategy 4: Moving Average Crossover
    # Calculate short and long-term moving averages
    ma_short = df['close'].rolling(window=20).mean()
    ma_long = df['close'].rolling(window=50).mean()

    # Check for MA crossover
    if ma_short.iloc[-2] < ma_long.iloc[-2] and ma_short.iloc[-1] > ma_long.iloc[-1]:
        print("🔹 MA Crossover: BUY signal")
        return "BUY", "MA Crossover"

    elif ma_short.iloc[-2] > ma_long.iloc[-2] and ma_short.iloc[-1] < ma_long.iloc[-1]:
        print("🔹 MA Crossover: SELL signal")
        return "SELL", "MA Crossover"
    
        # --- Strategy 4: MACD Signal Cross
    if macd.iloc[-2] < signal_line.iloc[-2] and macd.iloc[-1] > signal_line.iloc[-1]:
        print("🔹 MACD cross above Signal: BUY signal")
        return "BUY", "MACD Signal Cross"
    
    elif macd.iloc[-2] > signal_line.iloc[-2] and macd.iloc[-1] < signal_line.iloc[-1]:
        print("🔹 MACD cross below Signal: SELL signal")
        return "SELL", "MACD Signal Cross"

    print("No valid strategy signal detected.")
    return None











## Saving Signals into the Database for Dashboaard 
def save_signal(symbol, signal_type, price, strategy):
    db = SessionLocal()
    try:
        new_signal = TradeSignal(
            symbol=symbol,
            signal=signal_type,
            price=price,
            strategy=strategy,
            timestamp=datetime.now()
        )
        db.add(new_signal)
        db.commit()
    except Exception as e:
        db.rollback()
        print("DB error:", e)
    finally:
        db.close()


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
    Base.metadata.create_all(bind=engine)  # This ensures tables exist
    while True:
        print("\n🔁 Running market scan...")
        scan_market()
        time.sleep(300)  # Every 5 minutes

    
