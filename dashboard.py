import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import TradeSignal, Base
from datetime import datetime
from db import SessionLocal

# Set up SQLAlchemy connection
import os
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Streamlit config
# Create tables if they don't exist               ##
Base.metadata.create_all(bind=engine)             ##
st.set_page_config(page_title="Crypto Signal Dashboard", layout="wide")
st.title("📈 Crypto Trade Signal Dashboard")

# Load data
session = SessionLocal()
signals = session.query(TradeSignal).order_by(TradeSignal.timestamp.desc()).all()
session.close()

# Convert to DataFrame
df = pd.DataFrame([{
    "timestamp": s.timestamp,
    "symbol": s.symbol,
    "signal": s.signal,
    "price": s.price,
    "strategy": s.strategy
} for s in signals])

if df.empty:
    st.warning("No signals found in the database.")
    st.stop()

# Symbol filter
symbols = df['symbol'].unique().tolist()
selected_symbol = st.selectbox("🔍 Filter by Symbol", ["All"] + symbols)

if selected_symbol != "All":
    df = df[df['symbol'] == selected_symbol]
# Calculate PnL for each signal
st.subheader("💵 Signal Performance (Simple PnL)")
pnl_data = []
for i in range(len(df) - 1):
    entry = df.iloc[i]
    exit_ = df.iloc[i + 1]
    if entry['symbol'] == exit_['symbol'] and entry['signal'] == "BUY":
        pnl = exit_['price'] - entry['price']
        pnl_data.append({
            "symbol": entry['symbol'],
            "entry_price": entry['price'],
            "exit_price": exit_['price'],
            "pnl": pnl,
            "entry_time": entry['timestamp'],
            "exit_time": exit_['timestamp']
        })

if pnl_data:
    pnl_df = pd.DataFrame(pnl_data)
    st.dataframe(pnl_df.style.applymap(
        lambda x: 'color: green' if isinstance(x, (int, float)) and x > 0 else 'color: red', subset=['pnl']
    ))
    st.write(f"Average PnL per trade: {pnl_df['pnl'].mean():.2f}")
else:
    st.info("Not enough data to calculate PnL.")

# Latest Signals Table
st.subheader("📋 Latest Trade Signals")
st.dataframe(df.head(50))

# Daily Summary
st.subheader("📆 Daily Summary")
df['date'] = pd.to_datetime(df['timestamp']).dt.date
daily_summary = df.groupby(['date', 'signal']).size().unstack(fill_value=0)
st.bar_chart(daily_summary)

# Chart
if not df.empty:
    chart_df = df[['timestamp', 'price']].copy()
    chart_df['timestamp'] = pd.to_datetime(chart_df['timestamp'])
    chart_df.set_index('timestamp', inplace=True)
    st.line_chart(chart_df)

st.caption("Built with ❤️ using Streamlit")
