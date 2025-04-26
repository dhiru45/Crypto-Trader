# strategies/ma89_trend.py

import numpy as np
import pandas as pd
from .common import calculate_rsi

def signal(df: pd.DataFrame, symbol: str):
    # need at least 89+2 bars
    if len(df) < 91:
        return None

    # --- 1) compute SMA(9) and WMA(89) ---
    df['sma9'] = df['close'].rolling(window=9).mean()

    period = 89
    weights = np.arange(1, period+1)
    def wma(x):
        # x is an array of the last 89 closes
        return np.dot(x, weights) / weights.sum()

    df['wma89'] = df['close']\
        .rolling(window=period)\
        .apply(wma, raw=True)

    # make sure the last two WMA(89) values exist
    prev_close = df['close'].iat[-2]
    curr_close = df['close'].iat[-1]
    prev_wma89 = df['wma89'].iat[-2]
    curr_wma89 = df['wma89'].iat[-1]
    if pd.isna(prev_wma89) or pd.isna(curr_wma89):
        return None

    # --- 2) reference candle: crosses from below → above wma89 ---
    crossed = (prev_close <= prev_wma89) and (curr_close > curr_wma89)
    if not crossed:
        return None

    # --- 3) RSI check at that moment ---
    rsi = calculate_rsi(df['close'], 14).iat[-1]
    if rsi <= 50:
        return None

    # --- 4) entry on next candle breaking the ref high ---
    ref_high = df['high'].iat[-1]
    ref_low  = df['low'].iat[-1]
    ref_time = df.index[-1]
    # find next bar
    next_time = df.index[-1] + pd.Timedelta(minutes=15)
    if next_time not in df.index:
        return None
    nxt = df.loc[next_time]
    if nxt['high'] <= ref_high:
        return None

    entry_price = float(nxt['close'])
    # SL = max(ref_low, entry_price * 0.99)
    stop_loss   = float(max(ref_low, entry_price * 0.99))
    # TP = entry_price * 1.05 (5% gain)
    take_profit = float(entry_price * 1.05)

    return {
        "symbol":      symbol,
        "action":      "BUY",
        "entry_time":  next_time,
        "entry_price": entry_price,
        "stop_loss":   stop_loss,
        "take_profit": take_profit,
        "strategy":    "MA89Trend"
    }
