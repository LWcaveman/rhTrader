"""rh_trader.py - Daily Swing Scanner with Dynamic Robinhood Account Sizing."""

from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import requests
import yfinance as yf

import const
from monitor import send_setup_alert
from reporter import log_alerts_to_csv
from rh_client import get_robinhood_balances

# Calibrated Guards: Allows high-beta leaders without sacrificing the 2% risk rule
MAX_EXTENSION_PCT = 0.025  # Max 2.5% extension above moving average
MAX_STOP_WIDTH_PCT = 0.050  # Max 5.0% stop distance ($1R)


def get_active_open_risk(filename: str = "swing_alerts.csv") -> dict:
  """Reads swing_alerts.csv and calculates active capital deployed

  and open dollar risk for all 'Live' positions.
  """
  csv_path = Path(__file__).resolve().parent / filename
  if not csv_path.exists() or csv_path.stat().st_size == 0:
    return {"count": 0, "open_risk": 0.0, "tickers": []}

  try:
    df = pd.read_csv(csv_path)
    if "Status" not in df.columns or "Ticker" not in df.columns:
      return {"count": 0, "open_risk": 0.0, "tickers": []}

    live_df = df[df["Status"] == "Live"].copy()
    if live_df.empty:
      return {"count": 0, "open_risk": 0.0, "tickers": []}

    total_open_risk = 0.0
    active_tickers = []

    for _, row in live_df.iterrows():
      entry_str = str(row.get("Entry", "")).replace("$", "").strip()
      stop_str = str(row.get("Stop Alert", "")).replace("$", "").strip()
      shares = float(row.get("Shares", 0.0))

      try:
        entry = float(entry_str)
        stop = float(stop_str)
        risk_per_share = max(0.0, entry - stop)
        trade_risk = round(risk_per_share * shares, 2)
      except ValueError:
        trade_risk = 0.0

      total_open_risk += trade_risk
      status_note = (
          "Breakeven ($0.00 risk)"
          if trade_risk == 0
          else f"${trade_risk:.2f} risk"
      )
      active_tickers.append(f"{row['Ticker']} ({status_note})")

    return {
        "count": len(live_df),
        "open_risk": round(total_open_risk, 2),
        "tickers": active_tickers,
    }
  except Exception:
    return {"count": 0, "open_risk": 0.0, "tickers": []}


def scan_and_evaluate():
  balances = get_robinhood_balances(
      fallback_equity=const.FALLBACK_EQUITY,
      fallback_bp=const.FALLBACK_BUYING_POWER,
  )
  total_equity = balances["total_equity"]
  buying_power = balances["buying_power"]

  max_alloc_pct = (
      const.MAX_ALLOCATION_PCT_MICO
      if total_equity < const.ACCOUNT_100
      else const.MAX_ALLOCATION_PCT
  )
  max_capital_per_trade = total_equity * max_alloc_pct

  print("\n" + "=" * 65)
  print(f"DAILY SWING SCANNER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
  print(
      f"Account Equity: ${total_equity:.2f} | Buying Power: ${buying_power:.2f}"
  )
  print(
      f"Risk Budget ({const.DEFAULT_RISK_PER_TRADE*100}%):"
      f" ${total_equity * const.DEFAULT_RISK_PER_TRADE:.2f} | Max Capital per"
      f" Trade: ${max_capital_per_trade:.2f}"
  )
  print("=" * 65)

  session = requests.Session()
  session.headers.update({
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      )
  })

  watchlist = const.WATCHLIST
  print(f"Fetching 2-year daily data for {len(watchlist)} watchlist tickers...")
  data = yf.download(
      tickers=watchlist,
      period="2y",
      interval="1d",
      group_by="ticker",
      auto_adjust=False,
      session=session,
      progress=False,
  )

  valid_setups = []

  # Capacity gating evaluated before scanning
  active_info = get_active_open_risk()
  max_positions = 1 if total_equity < const.ACCOUNT_100 else 2
  has_open_slot = active_info["count"] < max_positions

  for ticker in watchlist:
    try:
      df = (
          data[ticker].dropna().copy()
          if len(watchlist) > 1
          else data.dropna().copy()
      )

      if df.empty or len(df) < 200:
        continue

      df["20_EMA"] = df["Close"].ewm(span=const.EMA_FAST, adjust=False).mean()
      df["50_SMA"] = df["Close"].rolling(window=const.SMA_SLOW).mean()
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

      # 1. Macro Trend Filter
      is_uptrend = (close > sma50 > sma200) and (sma50 >= prev_sma50)

      # 2. Retest Condition (Today OR Yesterday)
      touched_20_today = low <= (ema20 * 1.005) and close >= (ema20 * 0.99)
      touched_20_prev = prev_low <= (float(prev["20_EMA"]) * 1.005)
      touched_50_today = low <= (sma50 * 1.005) and close >= (sma50 * 0.99)
      touched_50_prev = prev_low <= (prev_sma50 * 1.005)

      retesting_20 = touched_20_today or touched_20_prev
      retesting_50 = touched_50_today or touched_50_prev
      retested_support = retesting_20 or retesting_50

      # 3. Confirmation Triggers
      is_engulfing = (
          prev_close < prev_open and open_p <= prev_close and close > prev_open
      )

      body = abs(close - open_p)
      lower_wick = min(open_p, close) - low
      upper_wick = high - max(open_p, close)
      is_hammer = (lower_wick >= 2 * body) and (
          upper_wick <= 0.2 * (high - low)
      )

      # Breakout confirmation from original strategy
      is_break_high = (close > prev_high) and (close > open_p)

      triggered = is_engulfing or is_hammer or is_break_high

      # 4. Strategy Rules Validation Block
      if is_uptrend and retested_support and triggered:
        active_ma = ema20 if retesting_20 else sma50

        # Anti-Chase Guard (Calibrated to 2.5%)
        extension = (close - active_ma) / active_ma
        if extension > MAX_EXTENSION_PCT:
          continue

        # Structural Stop Placement (0.5% below 2-day low)
        swing_low = min(low, prev_low)
        stop_loss = round(swing_low * 0.995, 2)
        risk_per_share = round(close - stop_loss, 2)

        # Stop Width Guard (Calibrated to 5.0%)
        stop_width = risk_per_share / close
        if stop_width <= 0 or stop_width > MAX_STOP_WIDTH_PCT:
          continue

        # Dynamic Position Sizing (Fixed 2% Risk Budget)
        max_risk_dollars = total_equity * const.DEFAULT_RISK_PER_TRADE
        ideal_shares = max_risk_dollars / risk_per_share
        ideal_capital = ideal_shares * close

        if ideal_capital > max_capital_per_trade:
          actual_capital = max_capital_per_trade
          shares = round(actual_capital / close, 4)
          actual_risk_dollars = round(shares * risk_per_share, 2)
        else:
          shares = round(ideal_shares, 4)
          actual_capital = round(ideal_capital, 2)
          actual_risk_dollars = round(max_risk_dollars, 2)

        can_execute = (
            has_open_slot
            and buying_power >= actual_capital
            and actual_capital >= const.MIN_POSITION_DOLLARS
        )

        if can_execute:
          status = "Suggested (Funded)"
          note = f"Ready to trade. Required: ${actual_capital:.2f}"
        else:
          status = "Suggested (Needs Cash)"
          if not has_open_slot:
            note = (
                f"Capacity reached ({active_info['count']}/{max_positions}"
                f" active). Needs ${actual_capital:.2f}"
            )
          else:
            note = (
                f"Short cash. Needs ${actual_capital:.2f}, Buying"
                f" Power: ${buying_power:.2f}"
            )

        trigger_type = (
            "Hammer"
            if is_hammer
            else (
                "Engulfing"
                if is_engulfing
                else ("Break of High" if is_break_high else "Trigger")
            )
        )
        support_type = "20 EMA" if retesting_20 else "50 SMA"
        note += f" | {trigger_type} off {support_type}"

        r1_breakeven = round(close + risk_per_share, 2)
        r2_target = round(close + (2 * risk_per_share), 2)
        r3_target = round(close + (3 * risk_per_share), 2)

        setup_data = {
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Logged At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Ticker": ticker,
            "Status": status,
            "Entry": f"${close:.2f}",
            "Shares": shares,
            "Capital": f"${actual_capital:.2f}",
            "Risk ($)": f"${actual_risk_dollars:.2f}",
            "Stop Alert": f"${stop_loss:.2f}",
            "Breakeven (+1R)": f"${r1_breakeven:.2f}",
            "Target (2R)": f"${r2_target:.2f}",
            "Runner (3R)": f"${r3_target:.2f}",
            "Fill Price": "",
            "Exit Date": "",
            "Exit Price": "",
            "Realized R": "",
            "Notes": note,
        }

        valid_setups.append(setup_data)

        try:
          send_setup_alert(setup_data)
          print(
              f"[Scanner] Found setup for {ticker} ({trigger_type}) -> Alerted."
          )
        except NameError:
          print(
              f"[Scanner] Found setup for {ticker} ({trigger_type}) -> Logged."
          )

    except Exception:
      continue

  print("\n" + "-" * 65)
  print("PORTFOLIO EXPOSURE SUMMARY")
  print("-" * 65)
  if active_info["count"] > 0:
    print(
        f"Active Live Positions ({active_info['count']}):"
        f" {', '.join(active_info['tickers'])}"
    )
    print(f"Total Open Portfolio Risk: ${active_info['open_risk']:.2f}")
  else:
    print("Active Live Positions: None")
    print("Total Open Portfolio Risk: $0.00")

  if valid_setups:
    print(f"\nNew Setups Triggered Today: {len(valid_setups)} (Logging to CSV)")
    log_alerts_to_csv(valid_setups)
  else:
    print("\nNew Setups Triggered Today: 0 (No new capital deployed)")
  print("-" * 65 + "\n")


if __name__ == "__main__":
  scan_and_evaluate()