"""const.py - Strategy parameters, risk settings, and ticker watchlists."""

# Risk & Allocation Rules
DEFAULT_RISK_PER_TRADE = 0.02  # 2.0% risk budget per trade
MAX_ALLOCATION_PCT = 0.50  # After account is over $100 Max 50% of account equity per position
MAX_ALLOCATION_PCT_MICO= 1 # Only one Trade while account is below $100
MIN_POSITION_DOLLARS = 5.00  # Minimum dollar amount Robinhood allows
ACCOUNT_100 = 100.0

# Strategy Moving Averages
EMA_FAST = 20
SMA_SLOW = 50

# Fallback Values if Offline / Unauthenticated
FALLBACK_EQUITY = 34.00
FALLBACK_BUYING_POWER = 5.00

# 69-Ticker Liquid Watchlist
WATCHLIST = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLV",
    "XLE",
    "XLI",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "JPM",
    "V",
    "MA",
    "UNH",
    "JNJ",
    "PG",
    "HD",
    "COST",
    "ABBV",
    "MRK",
    "CVX",
    "XOM",
    "AMD",
    "NFLX",
    "ADBE",
    "CRM",
    "QCOM",
    "INTU",
    "TXN",
    "NOW",
    "ISRG",
    "CAT",
    "GE",
    "IBM",
    "BA",
    "HON",
    "AMAT",
    "LRCX",
    "BKNG",
    "BLK",
    "GS",
    "MS",
    "MCD",
    "SBUX",
    "NKE",
    "LOW",
    "TJX",
    "WMT",
    "TGT",
    "DE",
    "RTX",
    "LMT",
    "NEE",
    "SO",
    "DUK",
    "PLTR",
    "UBER",
    "ABNB",
    "SNOW",
    "PANW",
    "CRWD",
    "SMCI",
]