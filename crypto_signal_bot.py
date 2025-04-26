# crypto_signal_bot.py
import os, time
from datetime import datetime
from timezone_utils import IST


import ccxt, pandas as pd, requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import engine, SessionLocal
from models import Base, TradeSignal, TradeLog
from strategies import ALL_STRATEGIES, trend_ema, ma89_trend
from paper_trader import PaperTrader

# ─── CONSTANTS ───────────────────────────────────────────────────────────────
LOOKBACK = 200
exchange = ccxt.binance()
symbols  = [
    'BTC/USDT','ETH/USDT','BNB/USDT','MATIC/USDT','SOL/USDT',
    'XRP/USDT','DOGE/USDT','ADA/USDT','AVAX/USDT','LTC/USDT'
]

TELEGRAM_TOKEN = '7926616723:AAEceR0CDRXchNmOkw8vrInDXjQ40e3n_-A'
CHAT_ID        = '425700500'


# create tables
Base.metadata.create_all(bind=engine)

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id":CHAT_ID,"text":text})
    print(f"Telegram status: {resp.status_code}")

def fetch_ohlcv(symbol: str, timeframe='15m', limit=LOOKBACK+2) -> pd.DataFrame:
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df    = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    # convert to IST
    df['timestamp'] = df['timestamp'].dt.tz_convert(IST)
    return df.set_index('timestamp')

def save_signal(symbol, action, price, strategy):
    db = SessionLocal()
    db.add(TradeSignal(
      symbol=symbol, signal=action, price=price,
      strategy=strategy, timestamp=datetime.now(IST)
    ))
    db.commit(); db.close()

def save_trade_entry(ts: dict):
    db = SessionLocal()
    db.add(TradeLog(
      symbol      = ts['symbol'],
      action      = ts['action'],
      entry_time  = ts['entry_time'],
      entry_price = ts['entry_price'],
      stop_loss   = ts['stop_loss'],
      take_profit = ts['take_profit'],
      status      = 'open',
      reason      = ts.get('strategy') or ts.get('reason')
    ))
    db.commit(); db.close()

def monitor_open_trades():
    db = SessionLocal()
    for t in db.query(TradeLog).filter(TradeLog.status=='open'):
        price = float(exchange.fetch_ticker(t.symbol)['last'])
        pnl   = (price - t.entry_price) if t.action=='BUY' else (t.entry_price - price)
        if price >= t.take_profit or price <= t.stop_loss:
            t.exit_time  = datetime.now(IST)
            t.exit_price = price
            t.pnl        = pnl
            t.status     = 'closed'
            db.commit()
            send_telegram_message(
              f"✅ Closed {t.action} {t.symbol}@{price:.2f} PnL={pnl:.2f}"
            )
    db.close()

def scan_market():                                                            #####  Scan Market
    for symbol in symbols:
        # print the scan start time in IST
        now_ist = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')
        print(f"\n🔍 {symbol} @ {now_ist}")
        try:
            df = fetch_ohlcv(symbol)

            # 1) Rule-based strategies
            for strat_fn in ALL_STRATEGIES:
                print(f"   ↳ testing rule: {strat_fn.__name__}")
                res = strat_fn(df)
                if res:
                    action, name = res
                    price = float(df['close'].iloc[-1])
                    print(f"   ↳ {name} → {action}@{price:.2f}")
                    send_telegram_message(f"🚨 {action} {symbol}@{price:.2f} | {name}")
                    save_signal(symbol, action, price, name)
                    break
            else:
                print("   ↳ no rule-based entry")

            # 2) Trend-EMA entry
            print("   ↳ applying TrendEMA logic…")
            te = trend_ema(df, symbol=symbol, lookback=LOOKBACK)
            if te:
                ep, sl, tp = te['entry_price'], te['stop_loss'], te['take_profit']
                print(f"   ↳ TrendEMA → BUY@{ep:.2f} SL{sl:.2f} TP{tp:.2f}")
                send_telegram_message(f"🔍 BUY {symbol}@{ep:.2f} StopLoss: {sl:.2f} Target: {tp:.2f}")
                save_trade_entry(te)
                trade_id = paper.open_trade(te)

            else:
                print("   ↳ no TrendEMA entry")

            # 3) 89-MA Trend entry
            print("   ↳ applying MA89Trend logic…")
            ma89 = ma89_trend(df, symbol=symbol)
            if ma89:
                ep, sl, tp = ma89['entry_price'], ma89['stop_loss'], ma89['take_profit']
                print(f"   ↳ MA89Trend → BUY@{ep:.2f} SL{sl:.2f} TP{tp:.2f}")
                send_telegram_message(f"89 MA - BUY {symbol}@{ep:.2f} StopLoss :{sl:.2f} Target :{tp:.2f}")
                save_trade_entry(ma89)
                trade_id = paper.open_trade(ma89)

            else:
                print("   ↳ no MA89Trend entry")

        except Exception as e:
            print(f"⚠️ Error scanning {symbol}: {e}")                  #####  Scan Market Close 

if __name__ == "__main__":
    print("🚀 Starting Crypto Signal Bot")
    print("🚀 Starting Crypto Signal Bot (paper trading mode)")
    paper = PaperTrader(starting_balance=10_000.0)
    while True:
        scan_market()
        monitor_open_trades()
        time.sleep(150)
