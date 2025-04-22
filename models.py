from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TradeSignal(Base):
    __tablename__ = 'signals'
    __table_args__ = {'schema': 'public'}  # Force public schema

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String)
    signal = Column(String)
    price=Column(price)
    strategy = Column(String)
    timestamp = Column(DateTime)
