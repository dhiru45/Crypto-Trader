# strategies/__init__.py
from .rsi_ema            import signal as rsi_ema
from .support_resistance import signal as support_resistance
from .breakout_volume    import signal as breakout_volume
from .ma_crossover       import signal as ma_crossover
from .trend_ema          import signal as trend_ema
from .ma89_trend         import signal as ma89_trend

ALL_STRATEGIES = [
    rsi_ema,
    support_resistance,
    breakout_volume,
    ma_crossover,
]
