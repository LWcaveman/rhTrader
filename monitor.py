from datetime import datetime
from pathlib import Path
import pandas as pd
import yfinance as yf


def parse_currency(val) -> float:
    """Safely converts currency strings (e.g.

    '$317.85') or floats to a clean float.
    """
    if pd.isna(val) or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    # Strip $, commas, and whitespace
    cleaned = str(val).replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def check_active_positions(
    filename: str = "swing_alerts.csv", include_paper: bool = False
) -> list:
    """Reads swing_alerts.csv, checks intraday quotes for all active trades,

    and outputs risk/target execution alerts.

    :param filename: CSV alert tracking file name.
    :param include_paper: If True, evaluates both 'Live' and 'Paper' trades.
    :return: List of alert dictionaries triggered during the check.
    """
    repo_dir = Path(__file__).resolve().parent
    filepath = repo_dir / filename

    if not filepath.exists() or filepath.stat().st_size == 0:
        print(f"[Monitor] Tracking file not found: {filepath}")
        return []

    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"[Monitor] Error reading {filename}: {e}")
        return []

    if "Status" not in df.columns or "Ticker" not in df.columns:
        print(f"[Monitor] CSV missing required 'Status' or 'Ticker' columns.")
        return []

    # Filter for active positions
    valid_statuses = ["Live"]
    if include_paper:
        valid_statuses.append("Paper")

    active_mask = df["Status"].isin(valid_statuses)
    active_df = df[active_mask].copy()

    if active_df.empty:
        print(
            f"[Monitor] No positions currently marked as"
            f" {'/'.join(valid_statuses)} in {filename}."
        )
        return []

    tickers = active_df["Ticker"].unique().tolist()
    print(
        f"[Monitor] Checking {len(tickers)} active position(s):"
        f" {', '.join(tickers)}..."
    )

    # Fetch live quotes
    quotes = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            price = t.fast_info.get("lastPrice", None)
            if price is None:
                # Fallback to 1-day 1-minute candle if fast_info is delayed
                hist = t.history(period="1d", interval="1m")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            if price:
                quotes[ticker] = round(float(price), 2)
        except Exception as err:
            print(f"[Monitor] Could not fetch live quote for {ticker}: {err}")

    alerts = []
    print("\n" + "=" * 75)
    print(
        f"INTRADAY POSITION MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 75)

    for idx, row in active_df.iterrows():
        ticker = row["Ticker"]
        status = row["Status"]
        current_price = quotes.get(ticker)

        if not current_price:
            print(f"[{status}] {ticker}: Unable to retrieve live market quote.")
            continue

        entry = parse_currency(
            row["Fill Price"] if row.get("Fill Price") else row["Entry"]
        )
        stop = parse_currency(row["Stop Alert"])
        r1_be = parse_currency(row["Breakeven (+1R)"])
        r2_target = parse_currency(row["Target (2R)"])
        r3_runner = parse_currency(row["Runner (3R)"])
        risk_per_share = (
            round(entry - stop, 2) if (entry and stop) else (entry * 0.02)
        )

        # Calculate current gain/loss and R-multiple
        pnl_dollars = round(current_price - entry, 2)
        pnl_pct = round((pnl_dollars / entry) * 100, 2) if entry else 0.0
        current_r = (
            round(pnl_dollars / risk_per_share, 2) if risk_per_share > 0 else 0.0
        )

        r_str = f"+{current_r}R" if current_r >= 0 else f"{current_r}R"
        pnl_str = f"+${pnl_dollars:.2f}" if pnl_dollars >= 0 else f"-${abs(pnl_dollars):.2f}"

        print(
            f"\n[{status}] {ticker} | Price: ${current_price:.2f} | Entry:"
            f" ${entry:.2f} | P&L: {pnl_str} ({pnl_pct}%, {r_str})"
        )

        # Trigger logic
        action = None
        urgency = "INFO"

        if current_price <= stop:
            action = f"🚨 STOP HIT: Price (${current_price:.2f}) dropped to or below Stop (${stop:.2f}). Close position."
            urgency = "CRITICAL"
        elif current_price >= r3_runner and r3_runner > 0:
            action = f"🎯 3R RUNNER REACHED: Price (${current_price:.2f}) hit Runner target (${r3_runner:.2f}). Lock in remaining profits."
            urgency = "TAKE_PROFIT"
        elif current_price >= r2_target and r2_target > 0:
            action = f"🎯 2R TARGET REACHED: Price (${current_price:.2f}) hit Profit Target (${r2_target:.2f}). Sell 75% and trail stop."
            urgency = "TAKE_PROFIT"
        elif current_price >= r1_be and r1_be > 0:
            action = f"🛡️ 1R BREAKEVEN HIT: Price (${current_price:.2f}) passed +1R (${r1_be:.2f}). MOVE STOP TO BREAKEVEN (${entry:.2f})."
            urgency = "ADJUST_STOP"
        else:
            action = f"Holding in range. Buffer to Stop: -${round(current_price - stop, 2):.2f} | Distance to +1R: +${round(r1_be - current_price, 2):.2f}"

        print(f"  └─ Action: {action}")

        if urgency != "INFO":
            alerts.append({
                "ticker": ticker,
                "status": status,
                "urgency": urgency,
                "price": current_price,
                "action": action,
            })

    print("=" * 75 + "\n")
    return alerts


if __name__ == "__main__":
    # When run directly, check both Live trades and Paper trades
    check_active_positions(include_paper=True)