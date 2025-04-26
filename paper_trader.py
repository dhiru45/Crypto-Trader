# paper_trader.py

import requests
from datetime import datetime
from timezone_utils import IST

from sqlalchemy.exc import SQLAlchemyError

import ccxt
from db import SessionLocal
from models import TradeLog

class PaperTrader:
    def __init__(self, starting_balance: float = 10_000.0):
        self.cash = starting_balance
        self.exchange = ccxt.binance()

    def open_trade(self, signal: dict):
        """
        signal dict must include:
          symbol, action, entry_time, entry_price, stop_loss, take_profit, strategy
        """
        session = SessionLocal()
        try:
            trade = TradeLog(
                symbol      = signal['symbol'],
                action      = signal['action'],
                entry_time  = signal['entry_time'],
                entry_price = float(signal['entry_price']),
                stop_loss   = float(signal['stop_loss']),
                take_profit = float(signal['take_profit']),
                status      = "open",
                reason      = signal.get('strategy')
            )
            session.add(trade)
            session.commit()
            print(f"📒 Opened paper trade #{trade.id}: {trade.action} {trade.symbol}@{trade.entry_price:.2f}")
            return trade.id
        except SQLAlchemyError as e:
            session.rollback()
            print("❌ Failed to open paper trade:", e)
        finally:
            session.close()

    def _send_telegram(self, text: str):
        # reuse your existing Telegram settings
        from crypto_signal_bot import TELEGRAM_TOKEN, CHAT_ID
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text})

    def update_trades(self):
        """
        Scan all open trades, check current price
        and close if SL or TP is hit.
        """
        session = SessionLocal()
        try:
            open_trades = session.query(TradeLog).filter(TradeLog.status == "open").all()
            for t in open_trades:
                ticker = self.exchange.fetch_ticker(t.symbol)
                current_price = float(ticker['last'])

                # calculate PnL
                if t.action.upper() == "BUY":
                    pnl = current_price - t.entry_price
                else:
                    pnl = t.entry_price - current_price

                # check exit
                if current_price <= t.stop_loss or current_price >= t.take_profit:
                    t.exit_time  = datetime.now(timezone.utc)
                    t.exit_price = current_price
                    t.pnl        = pnl
                    t.status     = "closed"
                    session.commit()

                    # update cash balance
                    self.cash += pnl
                    print(f"📒 Closed paper trade #{t.id}: {t.action} {t.symbol}@{current_price:.2f} PnL={pnl:.2f}")
                    self._send_telegram(
                        f"✅ Paper Trade Closed #{t.id}: {t.action} {t.symbol}@{current_price:.2f}  PnL={pnl:.2f}  Balance={self.cash:.2f}"
                    )
        except Exception as e:
            session.rollback()
            print("❌ Error updating paper trades:", e)
        finally:
            session.close()
