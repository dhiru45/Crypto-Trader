# strategies/ma_crossover.py
import pandas as pd

def signal(df: pd.DataFrame, short_w: int = 20, long_w: int = 50):
    ma_short = df['close'].rolling(short_w).mean()
    ma_long  = df['close'].rolling(long_w).mean()

    if ma_short.iloc[-2] < ma_long.iloc[-2] and ma_short.iloc[-1] > ma_long.iloc[-1]:
        return "BUY",  "MA Crossover"
    if ma_short.iloc[-2] > ma_long.iloc[-2] and ma_short.iloc[-1] < ma_long.iloc[-1]:
        return "SELL", "MA Crossover"
    return None
