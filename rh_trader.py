from datetime import datetime
import pandas as pd
from reporter import log_alerts_to_csv
import requests
import yfinance as yf
from const import WATCHLIST

ACCOUNT_BALANCE = 30.00  # Update with your active balance
RISK_BUDGET = 0.02  # 2.0% risk per trade ($5.00 on $250)
MAX_EXTENSION_PCT = 0.015  # Max 1.5% extension above moving average
MAX_STOP_WIDTH_PCT = 0.030  # Max 3.0% stop distance ($1R)


def scan_swing_setups(watchlist, balance):
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })

    print(
        f"Fetching 2-year daily data for {len(watchlist)} watchlist tickers..."
    )
    data = yf.download(
        tickers=watchlist,
        period="2y",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        session=session,
        progress=False,
    )

    alerts = []

    for ticker in watchlist:
        try:
            df = (
                data[ticker].dropna().copy()
                if len(watchlist) > 1
                else data.dropna().copy()
            )

            if df.empty or len(df) < 200:
                continue

            # Core Indicators
            df["20_EMA"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["50_SMA"] = df["Close"].rolling(window=50).mean()
            df["200_SMA"] = df["Close"].rolling(window=200).mean()

            today = df.iloc[-1]
            prev = df.iloc[-2]

            close = float(today["Close"])
            open_p = float(today["Open"])
            low = float(today["Low"])
            high = float(today["High"])

            prev_close = float(prev["Close"])
            prev_open = float(prev["Open"])
            prev_high = float(prev["High"])
            prev_low = float(prev["Low"])

            ema20 = float(today["20_EMA"])
            sma50 = float(today["50_SMA"])
            sma200 = float(today["200_SMA"])
            prev_sma50 = float(prev["50_SMA"])

            # 1. Macro Trend Filter: Rising moving averages
            is_uptrend = (close > sma50 > sma200) and (sma50 >= prev_sma50)

            # 2. Retest Condition (Today OR Yesterday)
            touched_20_today = low <= (ema20 * 1.005) and close >= (
                ema20 * 0.99
            )
            touched_20_prev = prev_low <= (float(prev["20_EMA"]) * 1.005)
            touched_50_today = low <= (sma50 * 1.005) and close >= (
                sma50 * 0.99
            )
            touched_50_prev = prev_low <= (prev_sma50 * 1.005)

            retesting_20 = touched_20_today or touched_20_prev
            retesting_50 = touched_50_today or touched_50_prev
            retested_support = retesting_20 or retesting_50

            # 3. Confirmation Triggers
            breakout_trigger = close > prev_high
            is_engulfing = (
                prev_close < prev_open
                and open_p <= prev_close
                and close > prev_open
            )

            body = abs(close - open_p)
            lower_wick = min(open_p, close) - low
            upper_wick = high - max(open_p, close)
            is_hammer = (lower_wick >= 2 * body) and (
                upper_wick <= 0.2 * (high - low)
            )

            triggered = breakout_trigger or is_engulfing or is_hammer

            # 4. Strategy Rules Validation Block
            if is_uptrend and retested_support and triggered:
                active_ma = ema20 if retesting_20 else sma50

                # Anti-Chase Guard
                extension = (close - active_ma) / active_ma
                if extension > MAX_EXTENSION_PCT:
                    continue

                # Structural Stop Placement (0.5% below the 2-day low)
                swing_low = min(low, prev_low)
                stop_loss = round(swing_low * 0.995, 2)
                risk_per_share = round(close - stop_loss, 2)

                # Stop Width Guard
                stop_width = risk_per_share / close
                if stop_width <= 0 or stop_width > MAX_STOP_WIDTH_PCT:
                    continue

                # Position Sizing & Cash Guard
                max_risk_dollars = balance * RISK_BUDGET
                ideal_shares = max_risk_dollars / risk_per_share
                ideal_capital = ideal_shares * close

                if ideal_capital > balance:
                    shares = round(balance / close, 4)
                    actual_capital = round(shares * close, 2)
                    actual_risk_dollars = round(shares * risk_per_share, 2)
                else:
                    shares = round(ideal_shares, 4)
                    actual_capital = round(ideal_capital, 2)
                    actual_risk_dollars = round(max_risk_dollars, 2)

                # Payoff Milestones
                r1_breakeven = round(close + risk_per_share, 2)
                r2_target = round(close + (2 * risk_per_share), 2)
                r3_target = round(close + (3 * risk_per_share), 2)

                alerts.append({
                    "Ticker": ticker,
                    "Entry": f"${close:.2f}",
                    "Shares": shares,
                    "Capital": f"${actual_capital:.2f}",
                    "Risk ($)": f"${actual_risk_dollars:.2f}",
                    "Stop Alert": f"${stop_loss:.2f}",
                    "Breakeven (+1R)": f"${r1_breakeven:.2f}",
                    "Target (2R)": f"${r2_target:.2f}",
                    "Runner (3R)": f"${r3_target:.2f}",
                })

        except Exception:
            continue

    return alerts


if __name__ == "__main__":
    results = scan_swing_setups(WATCHLIST, ACCOUNT_BALANCE)
    if results:
        df_results = pd.DataFrame(results)
        print("\n=== ACTIVE SWING TRADE ALERTS ===")
        print(df_results.to_string(index=False))
        print()

        # Log results to CSV
        log_alerts_to_csv(results)

        # Check active positions
        # print("\nChecking active positions...")
        # check_active_positions(include_paper=False)
    else:
        print("\nNo valid swing pullbacks triggered today.")