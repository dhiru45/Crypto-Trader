# strategies/support_resistance.py
import pandas as pd
from .common import calculate_rsi

def signal(df: pd.DataFrame):
    price = df['close'].iloc[-1]
    rsi   = calculate_rsi(df['close'], 14)

    support    = df['low'].rolling(10).min().iloc[-2]
    resistance = df['high'].rolling(10).max().iloc[-2]

    if abs(price - support)/support < 0.005 and rsi.iloc[-1] < 30:
        return "BUY",  "SupportBounce_RSI"
    if abs(price - resistance)/resistance < 0.005 and rsi.iloc[-1] > 70:
        return "SELL", "ResistanceBounce_RSI"
    return None
