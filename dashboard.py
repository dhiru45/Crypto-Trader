import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
from models import Base, TradeSignal, TradeLog
from datetime import timezone, timedelta, datetime

# India Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# ──────────────────────────────────────────────────────────────────────────────
# 1) DATABASE SETUP
# ──────────────────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("Environment variable DATABASE_URL is not set.")
    st.stop()

engine = (
    create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    if DATABASE_URL.startswith("sqlite")
    else create_engine(DATABASE_URL)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ensure tables exist
Base.metadata.create_all(bind=engine)

# ──────────────────────────────────────────────────────────────────────────────
# 2) STREAMLIT LAYOUT
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="📊 Crypto Bot Dashboard", layout="wide")
st.title("📊 Crypto Signal & Trade Dashboard")
st.write("Last updated (IST):", datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z"))

# ──────────────────────────────────────────────────────────────────────────────
# 3) QUERY YOUR DATA
# ──────────────────────────────────────────────────────────────────────────────

db = SessionLocal()
# all signals, newest first
signals = db.query(TradeSignal).order_by(TradeSignal.timestamp.desc()).all()
# all trades, newest first
trades  = db.query(TradeLog)  .order_by(TradeLog.entry_time.desc()).all()
db.close()

# ──────────────────────────────────────────────────────────────────────────────
# 4) SHOW RAW SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

if signals:
    st.subheader("🔔 Raw Trade Signals")
    sig_df = pd.DataFrame([{
        "ID": s.id,
        "Time (IST)": s.timestamp.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "Symbol": s.symbol,
        "Action": s.signal,
        "Price": s.price,
        "Strategy": s.strategy
    } for s in signals])
    st.dataframe(sig_df)
else:
    st.info("No signals yet.")

# ──────────────────────────────────────────────────────────────────────────────
# 5) SHOW PAPER TRADES
# ──────────────────────────────────────────────────────────────────────────────

if trades:
    st.subheader("💼 Paper Trades Log")
    trades_df = pd.DataFrame([{
        "ID":           t.id,
        "Entry Time":   t.entry_time.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "Exit Time":    (t.exit_time  .astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")
                          if t.exit_time else "—"),
        "Symbol":       t.symbol,
        "Action":       t.action,
        "Entry Price":  t.entry_price,
        "Exit Price":   (t.exit_price if t.exit_price else "—"),
        "Stop-Loss":    t.stop_loss,
        "Take-Profit":  t.take_profit,
        "PnL":          (f"{t.pnl:.2f}" if t.pnl is not None else "—"),
        "Status":       t.status,
        "Reason":       t.reason
    } for t in trades])
    st.dataframe(trades_df)
else:
    st.info("No paper trades yet.")

# ──────────────────────────────────────────────────────────────────────────────
# 6) SIMPLE METRICS
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("📈 High-Level Metrics")
col1, col2 = st.columns(2)

with col1:
    total_signals = len(signals)
    st.metric("Total Signals", total_signals)

    by_strat = sig_df["Strategy"].value_counts().rename_axis("Strategy").reset_index(name="Count")
    st.bar_chart(by_strat.set_index("Strategy")["Count"])

with col2:
    total_trades = len(trades_df)
    st.metric("Total Trades", total_trades)

    # basic PnL
    closed = trades_df[trades_df["Status"] == "closed"]
    if not closed.empty:
        avg_pnl = closed["PnL"].astype(float).mean()
        win_rate = (closed["PnL"].astype(float) > 0).mean() * 100
        st.metric("Avg PnL per trade", f"{avg_pnl:.2f}")
        st.metric("Win Rate", f"{win_rate:.1f}%")
    else:
        st.write("No closed trades to summarize.")

# ──────────────────────────────────────────────────────────────────────────────
# 7) OPTIONAL: DEDUPE HINT FOR YOUR BOT
# ──────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    ---
    **👷‍♂️ Note for your bot**  
    To avoid duplicate signals for the same open position, you can:
    1. Check `TradeLog` for any `status='open'` on that symbol before issuing a new entry.  
    2. Or, once you save a `TradeSignal` for a symbol+strategy, only allow the next signal after you see a closing trade for that symbol.  
    """
)
