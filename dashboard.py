import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import TradeSignal, Base
from datetime import datetime
import os

# Set up SQLAlchemy connection
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Streamlit config
Base.metadata.create_all(bind=engine)
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

# Strategy-specific PnL Analysis
st.subheader("📊 Strategy-specific Performance")
pnl_data = []
for strategy in df['strategy'].unique():
    strat_df = df[df['strategy'] == strategy]
    for i in range(len(strat_df) - 1):
        entry = strat_df.iloc[i]
        exit_ = strat_df.iloc[i + 1]
        if entry['signal'] == "BUY" and entry['symbol'] == exit_['symbol']:
            pnl = exit_['price'] - entry['price']
            pnl_data.append({
                "strategy": strategy,
                "symbol": entry['symbol'],
                "entry_price": entry['price'],
                "exit_price": exit_['price'],
                "pnl": pnl,
                "entry_time": entry['timestamp'],
                "exit_time": exit_['timestamp']
            })

if pnl_data:
    pnl_df = pd.DataFrame(pnl_data)
    strat_summary = pnl_df.groupby("strategy").agg(
        trades=("pnl", "count"),
        avg_pnl=("pnl", "mean"),
        total_pnl=("pnl", "sum"),
        win_rate=("pnl", lambda x: (x > 0).sum() / len(x) * 100)
    ).reset_index()

    st.dataframe(strat_summary.style.format({"avg_pnl": "{:.2f}", "total_pnl": "{:.2f}", "win_rate": "{:.2f}%"}))

    # Filters and Download
    st.markdown("### 📥 Export PnL Data")
    with st.expander("Download Strategy PnL Report"):
        csv = pnl_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="strategy_pnl_report.csv",
            mime="text/csv"
        )

    # Chart
    st.markdown("### 📈 PnL by Strategy")
    st.bar_chart(strat_summary.set_index("strategy")["total_pnl"])

else:
    st.info("Not enough data to evaluate strategy PnL.")

# Latest Signals Table
st.subheader("📋 Latest Trade Signals")
st.dataframe(df.head(50))

# Daily Summary
st.subheader("📆 Daily Summary")
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df['date'] = df['timestamp'].dt.date
daily_summary = df.groupby(['date', 'signal']).size().unstack(fill_value=0)
st.bar_chart(daily_summary)

# Price Chart
if not df.empty:
    chart_df = df[['timestamp', 'price']].copy()
    chart_df['timestamp'] = pd.to_datetime(chart_df['timestamp'], utc=True)
    chart_df.set_index('timestamp', inplace=True)
    st.line_chart(chart_df)

st.caption("Built with ❤️ using Streamlit")
