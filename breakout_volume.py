# strategies/breakout_volume.py
import pandas as pd

def signal(df: pd.DataFrame, vol_thresh: float = 1.2, breakout_mult: float = 1.005):
    price         = df['close'].iloc[-1]
    recent_high   = df['high'][:-1].max()
    breakout_price= recent_high * breakout_mult
    avg_vol       = df['volume'].rolling(20).mean().iloc[-1]
    cur_vol       = df['volume'].iloc[-1]

    if price > breakout_price and cur_vol > avg_vol * vol_thresh:
        return "BUY",  "Breakout + Volume Spike"
    if price < breakout_price and cur_vol > avg_vol * vol_thresh:
        return "SELL", "Breakout + Volume Spike"
    return None
