# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TradeSignal(Base):
    __tablename__ = "signals"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    symbol    = Column(String, nullable=False)
    signal    = Column(String, nullable=False)
    price     = Column(Float,  nullable=False)
    strategy  = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)

class TradeLog(Base):
    __tablename__ = "trades"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    symbol      = Column(String,  nullable=False)
    action      = Column(String,  nullable=False)
    entry_time  = Column(DateTime, nullable=False)
    entry_price = Column(Float,   nullable=False)
    stop_loss   = Column(Float,   nullable=False)
    take_profit = Column(Float,   nullable=False)
    exit_time   = Column(DateTime, nullable=True)
    exit_price  = Column(Float,   nullable=True)
    pnl         = Column(Float,   nullable=True)
    status      = Column(String,  nullable=False, default="open")
    reason      = Column(String,  nullable=False)
