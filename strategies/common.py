# strategies/common.py
import pandas as pd

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.where(delta>0,0).rolling(period).mean()
    loss  = -delta.where(delta<0,0).rolling(period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))
