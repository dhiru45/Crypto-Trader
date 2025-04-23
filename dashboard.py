import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import TradeSignal, Base
from datetime import datetime
import os
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

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

# Preprocess for model
model_df = df.copy()
model_df['timestamp'] = pd.to_datetime(model_df['timestamp'], utc=True)
model_df['price_diff'] = model_df['price'].diff()
model_df['future_price'] = model_df['price'].shift(-1)
model_df['price_change'] = model_df['future_price'] - model_df['price']
model_df['target'] = model_df['price_change'].apply(lambda x: 1 if x > 0 else 0)

# --- New Features ---
model_df['rolling_std'] = model_df['price'].rolling(window=14).std()

# PnL per trade (BUY -> SELL)
pnl_per_trade = []
open_position = None
for i in range(len(model_df) - 1):
    entry = model_df.iloc[i]
    exit_ = model_df.iloc[i + 1]
    if entry['signal'] == "BUY" and exit_['signal'] == "SELL" and entry['symbol'] == exit_['symbol']:
        pnl = exit_['price'] - entry['price']
        pnl_per_trade.append(pnl)
    else:
        pnl_per_trade.append(np.nan)

model_df['pnl_per_trade'] = pnl_per_trade + [np.nan]*(len(model_df) - len(pnl_per_trade))
model_df = model_df[['price_diff', 'rolling_std', 'pnl_per_trade', 'target']].dropna()

X = model_df[['price_diff', 'rolling_std', 'pnl_per_trade']]
y = model_df['target']


# Train/Test Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

# Train enhanced model using Gradient Boosting
clf = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
clf.fit(X_train, y_train)

# Evaluation
y_pred = clf.predict(X_test)
st.subheader("🤖 AI Model Evaluation")
st.text(classification_report(y_test, y_pred))

# Paper trading simulation
st.subheader("💰 Paper Trading Simulation")
paper_cash = 10000
positions = []
paper_trades = []
error_logs = []
for i in range(len(model_df)):
    row = model_df.iloc[i]
    try:
        prediction = clf.predict([row[['price_diff', 'rolling_std', 'pnl_per_trade']]])[0]
    except Exception as e:
        error_logs.append(f"Prediction failed at {row['timestamp']} → {e}")
        continue
    if prediction == 1 and not positions:
        positions.append((row['timestamp'], row['price']))
    elif prediction == 0 and positions:
        entry_time, entry_price = positions.pop(0)
        pnl = row['price'] - entry_price
        paper_cash += pnl
        paper_trades.append({
            "entry_time": entry_time,
            "exit_time": row['timestamp'],
            "entry_price": entry_price,
            "exit_price": row['price'],
            "pnl": pnl,
            "balance": paper_cash
        })

if paper_trades:
    pt_df = pd.DataFrame(paper_trades)
    st.dataframe(pt_df)
    st.write(f"Final Balance: ${paper_cash:.2f}")

if error_logs:
    st.subheader("⚠️ Prediction Errors Log")
    with st.expander("View Prediction Errors"):
        for log in error_logs:
            st.write(log)

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
