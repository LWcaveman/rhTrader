import os
from pathlib import Path
from dotenv import load_dotenv
import robin_stocks.robinhood as rh

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


def get_robinhood_balances(
    fallback_equity: float = 34.0, fallback_bp: float = 5.0
) -> dict:
    """Authenticates via cached session and returns both Total Account Equity

    (Cash + Active Positions) and Available Buying Power (Liquid Cash).
    """
    username = os.getenv("RH_USERNAME")
    password = os.getenv("RH_PASSWORD")

    if not username or not password:
        print("[RH Client] Credentials missing in .env.")
        return {"total_equity": fallback_equity, "buying_power": fallback_bp}

    try:
        # Re-uses ~/.tokens/robinhood.pickle automatically without prompting
        login_res = rh.login(
            username=username,
            password=password,
            expiresIn=2592000,
            scope="internal",
            store_session=True,
        )

        if not login_res or "access_token" not in login_res:
            print("[RH Client] Session expired or failed. Using fallbacks.")
            return {
                "total_equity": fallback_equity,
                "buying_power": fallback_bp,
            }

        # 1. Query buying power (uninvested settled cash)
        acc_profile = rh.profiles.load_account_profile()
        raw_bp = acc_profile.get("buying_power") or acc_profile.get(
            "portfolio_cash", 0.0
        )
        buying_power = round(float(raw_bp), 2)

        # 2. Query total portfolio equity (cash + open stock market value)
        port_profile = rh.profiles.load_portfolio_profile()
        raw_equity = (
            port_profile.get("equity")
            or port_profile.get("extended_hours_equity")
            or buying_power
        )
        total_equity = round(float(raw_equity), 2)

        return {"total_equity": total_equity, "buying_power": buying_power}

    except Exception as e:
        print(f"[RH Client] Connection error: {e}. Defaulting to fallbacks.")
        return {"total_equity": fallback_equity, "buying_power": fallback_bp}


if __name__ == "__main__":
    balances = get_robinhood_balances()
    print("\n" + "=" * 50)
    print("ROBINHOOD ACCOUNT SNAPSHOT")
    print("=" * 50)
    print(f"  Total Portfolio Value:   ${balances['total_equity']:.2f}")
    print(f"  Available Buying Power:  ${balances['buying_power']:.2f}")
    print("=" * 50 + "\n")