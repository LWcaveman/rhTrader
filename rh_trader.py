"""rh_trader.py - Daily Swing Scanner with Dynamic Robinhood Account Sizing."""

from datetime import datetime
import const
from reporter import log_alerts_to_csv
from rh_client import get_robinhood_balances
import yfinance as yf


def calculate_position_size(
    entry_price: float,
    stop_price: float,
    total_equity: float,
    buying_power: float,
) -> dict:
    """Calculates risk-budgeted fractional shares and evaluates whether

    available buying power can fund the position.
    """
    risk_per_share = round(entry_price - stop_price, 2)
    if risk_per_share <= 0:
        return None

    # 1. Total dollar risk permitted (e.g., 2% of total net worth)
    dollar_risk = round(total_equity * const.DEFAULT_RISK_PER_TRADE, 2)

    # 2. Maximum capital permitted in one position (e.g., 50% max allocation)
    # Under $100: 1 single position gets up to 100% allocation
    # At or above $100: Split across 2 concurrent positions (50% max allocation each)
    max_allocation_pct = const.MAX_ALLOCATION_PCT_MICO if total_equity < const.ACCOUNT_100 else const.MAX_ALLOCATION_PCT    
    max_capital = round(total_equity * max_allocation_pct, 2)
    
    # 3. Share sizing governed by risk: Shares = Dollar Risk / Stop Distance
    shares_by_risk = dollar_risk / risk_per_share
    required_capital = round(shares_by_risk * entry_price, 2)

    # Cap at maximum allocation if risk sizing asks for too much total capital
    if required_capital > max_capital:
        required_capital = max_capital
        shares_to_buy = round(required_capital / entry_price, 4)
        actual_risk = round(shares_to_buy * risk_per_share, 2)
    else:
        shares_to_buy = round(shares_by_risk, 4)
        actual_risk = dollar_risk

    # 4. Execution Gating: Check against uninvested liquid cash
    can_execute = (
        buying_power >= required_capital
        and required_capital >= const.MIN_POSITION_DOLLARS
    )

    return {
        "shares": shares_to_buy,
        "required_capital": required_capital,
        "actual_risk": actual_risk,
        "can_execute": can_execute,
    }


def scan_and_evaluate():
    # Fetch live balances via session token
    balances = get_robinhood_balances(
        fallback_equity=const.FALLBACK_EQUITY,
        fallback_bp=const.FALLBACK_BUYING_POWER,
    )
    total_equity = balances["total_equity"]
    buying_power = balances["buying_power"]

    print("\n" + "=" * 65)
    print(
        f"DAILY SWING SCANNER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print(
        f"Account Equity: ${total_equity:.2f} | Buying Power: ${buying_power:.2f}"
    )
    print(
        f"Risk Budget (2%): ${total_equity * const.DEFAULT_RISK_PER_TRADE:.2f} |"
        f" Max Capital per Trade: ${total_equity * const.MAX_ALLOCATION_PCT:.2f}"
    )
    print("=" * 65)

    valid_setups = []

    # Example loop processing tickers (abbreviated for demonstration)
    for ticker in const.WATCHLIST:
        # [Technical scan logic: 20 EMA, 50 SMA, engulfing/hammer triggers]
        # Assuming `setup_detected` with entry $150.00 and stop $145.00:
        entry = 150.00
        stop = 145.00
        setup_detected = False  # Set to True when your pattern matches

        if setup_detected:
            sizing = calculate_position_size(
                entry, stop, total_equity, buying_power
            )
            if not sizing:
                continue

            # Determine trade status based on buying power
            if sizing["can_execute"]:
                status = "Suggested (Funded)"
                note = f"Ready to trade. Required: ${sizing['required_capital']:.2f}"
            else:
                status = "Suggested (Needs Cash)"
                note = f"Short cash. Needs ${sizing['required_capital']:.2f}, Buying Power: ${buying_power:.2f}"

            valid_setups.append({
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Logged At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": ticker,
                "Status": status,
                "Entry": f"${entry:.2f}",
                "Shares": sizing["shares"],
                "Capital": f"${sizing['required_capital']:.2f}",
                "Risk ($)": f"${sizing['actual_risk']:.2f}",
                "Stop Alert": f"${stop:.2f}",
                "Breakeven (+1R)": f"${entry + (entry - stop):.2f}",
                "Target (2R)": f"${entry + (2 * (entry - stop)):.2f}",
                "Runner (3R)": f"${entry + (3 * (entry - stop)):.2f}",
                "Exit Date": "",
                "Exit Price": "",
                "Realized R": "",
                "Notes": note,
            })

    if valid_setups:
        print(f"\nFound {len(valid_setups)} setup(s). Logging to CSV...")
        log_alerts_to_csv(valid_setups)
    else:
        print("\nNo setups matched criteria today. Zero capital at risk.")


if __name__ == "__main__":
    scan_and_evaluate()