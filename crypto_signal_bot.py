import ccxt
import pandas as pd
import time
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
import requests
from datetime import datetime

from db import SessionLocal
from models import TradeSignal

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import TradeSignal, Base

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

TELEGRAM_TOKEN = '7926616723:AAEceR0CDRXchNmOkw8vrInDXjQ40e3n_-A'
CHAT_ID = '425700500'

exchange = ccxt.binance()
symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'MATIC/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LTC/USDT']

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
        return None

    if (
        df['MA_short'].iloc[-2] < df['MA_long'].iloc[-2] and
        df['MA_short'].iloc[-1] > df['MA_long'].iloc[-1]
    ):
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

    avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
    current_volume = df['volume'].iloc[-1]
    breakout_price = df['high'].iloc[-1] * breakout_multiplier
    current_price = df['close'].iloc[-1]

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
    ema_short = df['close'].ewm(span=9, adjust=False).mean()
    ema_long = df['close'].ewm(span=21, adjust=False).mean()
    rsi = calculate_rsi(df['close'], 14)
    current_price = df['close'].iloc[-1]
    macd = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    signal_line = macd.ewm(span=9, adjust=False).mean()

    if (
        ema_short.iloc[-2] < ema_long.iloc[-2] and
        ema_short.iloc[-1] > ema_long.iloc[-1] and
        rsi.iloc[-1] < 75
    ):
        return "BUY", "RSI + EMA Crossover"

    elif (
        ema_short.iloc[-2] > ema_long.iloc[-2] and
        ema_short.iloc[-1] < ema_long.iloc[-1] and
        rsi.iloc[-1] > 25
    ):
        return "SELL", "RSI + EMA Crossover"

    sr_signal = support_resistance_strategy(df)
    if sr_signal:
        return sr_signal["signal"], sr_signal["strategy"]

    recent_high = df['high'][:-1].max()
    breakout_price = recent_high * 1.005
    avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
    current_volume = df['volume'].iloc[-1]
    if current_price > breakout_price and current_volume > avg_volume * 1.2:
        return "BUY", "Breakout + Volume Spike"
    elif current_price < breakout_price and current_volume > avg_volume * 1.2:
        return "SELL", "Breakout + Volume Spike"

    ma_short = df['close'].rolling(window=20).mean()
    ma_long = df['close'].rolling(window=50).mean()
    if ma_short.iloc[-2] < ma_long.iloc[-2] and ma_short.iloc[-1] > ma_long.iloc[-1]:
        return "BUY", "MA Crossover"
    elif ma_short.iloc[-2] > ma_long.iloc[-2] and ma_short.iloc[-1] < ma_long.iloc[-1]:
        return "SELL", "MA Crossover"

    if macd.iloc[-2] < signal_line.iloc[-2] and macd.iloc[-1] > signal_line.iloc[-1]:
        return "BUY", "MACD Signal Cross"
    elif macd.iloc[-2] > signal_line.iloc[-2] and macd.iloc[-1] < signal_line.iloc[-1]:
        return "SELL", "MACD Signal Cross"

    return None

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

def scan_market():
    for symbol in symbols:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            signal = apply_strategy(df)
            if signal:
                price = df['close'].iloc[-1]
                action, strategy_name = signal if isinstance(signal, tuple) else (signal, "RSI + EMA Crossover")
                message = f"\ud83d\udea8 Signal: {action} {symbol} at {price:.2f} | Strategy: {strategy_name}"
                send_telegram_message(message)
                save_signal(symbol, action, price, strategy_name)
        except Exception as e:
            print(f"Error checking {symbol}: {str(e)}")

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    while True:
        scan_market()
        time.sleep(300)
