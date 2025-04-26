# strategies/rsi_ema.py
import pandas as pd
from .common import calculate_rsi

def signal(df: pd.DataFrame):
    ema_short = df['close'].ewm(span=9, adjust=False).mean()
    ema_long  = df['close'].ewm(span=21,adjust=False).mean()
    rsi       = calculate_rsi(df['close'], 14)

    if ema_short.iloc[-2] < ema_long.iloc[-2] and ema_short.iloc[-1] > ema_long.iloc[-1] and rsi.iloc[-1] < 70:
        return "BUY",  "RSI + EMA Crossover"
    if ema_short.iloc[-2] > ema_long.iloc[-2] and ema_short.iloc[-1] < ema_long.iloc[-1] and rsi.iloc[-1] > 30:
        return "SELL", "RSI + EMA Crossover"
    return None
