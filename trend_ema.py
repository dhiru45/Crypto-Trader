# strategies/trend_ema.py
import numpy as np
import pandas as pd

def signal(df: pd.DataFrame,
           symbol: str,
           threshold: float = 0.10,
           lookback: int = 200,
           ema_spans: tuple = (5,20,89,200)):
    if len(df) < lookback + 2:
        return None

    # compute EMAs
    for span in ema_spans:
        df[f'ema{span}'] = df['close'].ewm(span=span, adjust=False).mean()

    # fit trendline on 3 highest peaks
    recent = df.iloc[-(lookback+1):-1]
    peaks  = recent['high'].nlargest(3)
    print(f"↳ Peaks for trendline: {peaks.to_dict()}")
    if peaks.size < 3:
        return None
    x = peaks.index.astype(np.int64)
    y = peaks.values
    m, b = np.polyfit(x,y,1)
    print(f"↳ Fitted trendline y = {m:.6e}·x + {b:.2f}")

    # 3) Check EMA convergence at the latest bar
    curr = df.iloc[-1]
    curr_price = curr['close']
    ema_vals  = {span: curr[f'ema{span}'] for span in ema_spans}
    ema_dists = {span: abs(ema_vals[span] - curr_price) / curr_price for span in ema_spans}
    print(f"↳ Current price: {curr_price:.4f}")
    print(f"↳ EMA values: {ema_vals}")
    print(f"↳ EMA distances: {ema_dists}")
    cond1 = all(d < threshold for d in ema_dists.values())
    print(f"↳ EMA convergence <{threshold*100:.1f}%? {cond1}")
    if not cond1:
        return None

    # 4) Find reference candle that crosses trendline
    reference_idx = None
    # Pre‐compute the previous‐close series
    prev_close_series = df['close'].shift(1)

    for idx in sorted(recent.index):
        # Option A: using shift
        prev_close = prev_close_series.loc[idx]
        curr_close = df.loc[idx, 'close']

        # Option B: using Timedelta
        # prev_time  = idx - pd.Timedelta(minutes=15)
        # if prev_time not in df.index:
        #     continue
        # prev_close = df.loc[prev_time, 'close']
        # curr_close = df.loc[idx,       'close']

        trend_prev = m * idx.value + b
        trend_curr = m * idx.value + b
        crossed    = (prev_close < trend_prev) and (curr_close > trend_curr)

        #print(
        #    f"   ↳ bar {idx}  prev_close={prev_close:.4f}  "
        #    f"trend={trend_prev:.4f}  →  curr_close={curr_close:.4f}  "
        #    f"trend={trend_curr:.4f}  →  crossed? {crossed}"
        #)
        if crossed:
            reference_idx = idx
            break

    if reference_idx is None:
        print("↳ no crossing found in lookback")
        return None
    
    # **NOW** bind 'ref' so we can use it below
    ref = df.loc[reference_idx]

    # print out the reference-candle details
    print(
        f"↳ Reference candle at {ref.name} "
        f"(high={ref['high']:.4f}, low={ref['low']:.4f}, close={ref['close']:.4f})"
    )

    # 5) Verify EMAs support the breakout
    ema_ref = {span: ref[f'ema{span}'] for span in ema_spans}
    print(f"↳ EMA at ref candle: {ema_ref}")
    if any(ema_ref[span] >= ref['close'] for span in ema_spans):
        print("↳ EMAs not all below ref close → abort")
        return None

    # 6) Entry on next bar if it breaks reference high
    next_time = reference_idx + pd.Timedelta(minutes=15)
    if next_time not in df.index:
        print(f"↳ no next bar at {next_time}")
        return None

    nxt = df.loc[next_time]
    print(f"↳ Next bar @ {next_time}: high={nxt['high']:.4f}, close={nxt['close']:.4f}")
    if nxt['high'] <= ref['high']:
        print("↳ Next bar did not break ref high")
        return None

    # 7) Compute SL / TP
    entry_price  = float(nxt['close'])
    stop_loss    = float(ref['low'])
    ref_len      = float(ref['high'] - ref['low'])
    take_profit  = float(entry_price + 2 * ref_len)
    print(f"↳ Entry at {entry_price:.4f}, SL={stop_loss:.4f}, TP={take_profit:.4f}")

    return {
        'symbol':      symbol,
        'action':      'BUY',
        'entry_time':  next_time,
        'entry_price': entry_price,
        'stop_loss':   stop_loss,
        'take_profit': take_profit,
        'reason':      '3-peak trendline + EMA convergence + breakout'
    }
