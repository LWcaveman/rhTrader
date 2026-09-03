from datetime import datetime
from pathlib import Path
import pandas as pd

# Master column schema: Setup data -> Execution status -> Outcome metrics
COLUMNS_ORDER = [
    "Date",
    "Logged At",
    "Ticker",
    "Status",
    "Entry",
    "Shares",
    "Capital",
    "Risk ($)",
    "Stop Alert",
    "Breakeven (+1R)",
    "Target (2R)",
    "Runner (3R)",
    "Fill Price",
    "Exit Date",
    "Exit Price",
    "Realized R",
    "Notes",
]


def log_alerts_to_csv(alerts: list, filename: str = "swing_alerts.csv") -> None:
    """Logs swing trade alerts to a persistent CSV file in the repository root.

    Defaults Status to 'Suggested' and reserves columns for live trade tracking.
    Automatically migrates existing CSV files if new columns are introduced.
    """
    if not alerts:
        return

    repo_dir = Path(__file__).resolve().parent
    filepath = repo_dir / filename

    today_str = datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    records = []
    for item in alerts:
        row = item.copy()
        row["Date"] = today_str
        row["Logged At"] = timestamp_str
        row["Status"] = "Suggested"
        row["Fill Price"] = ""
        row["Exit Date"] = ""
        row["Exit Price"] = ""
        row["Realized R"] = ""
        row["Notes"] = ""
        records.append(row)

    df_new = pd.DataFrame(records)

    # Ensure all defined columns exist in incoming alerts
    for col in COLUMNS_ORDER:
        if col not in df_new.columns:
            df_new[col] = ""
    df_new = df_new[COLUMNS_ORDER]

    if filepath.exists() and filepath.stat().st_size > 0:
        try:
            df_existing = pd.read_csv(filepath)

            # Schema Migration: Add any missing tracking columns to older records
            updated_schema = False
            for col in COLUMNS_ORDER:
                if col not in df_existing.columns:
                    df_existing[col] = (
                        "Suggested" if col == "Status" else ""
                    )
                    updated_schema = True

            if updated_schema:
                df_existing = df_existing[COLUMNS_ORDER]
                df_existing.to_csv(filepath, index=False)

            # Deduplication check on Date and Ticker
            existing_pairs = set(
                zip(df_existing["Date"].astype(str), df_existing["Ticker"])
            )
            df_to_append = df_new[
                ~df_new.apply(
                    lambda r: (str(r["Date"]), r["Ticker"]) in existing_pairs,
                    axis=1,
                )
            ]

            if df_to_append.empty:
                print(
                    f"[Reporter] Setup already logged for today in"
                    f" {filepath.name}."
                )
                return

            df_to_append.to_csv(filepath, mode="a", header=False, index=False)
            print(
                f"[Reporter] Appended {len(df_to_append)} setup(s) to"
                f" {filepath.name}."
            )

        except Exception as e:
            df_new.to_csv(filepath, mode="a", header=False, index=False)
            print(
                f"[Reporter] Appended setup to {filepath.name} (Fallback error:"
                f" {e})."
            )
    else:
        df_new.to_csv(filepath, mode="w", header=True, index=False)
        print(
            f"[Reporter] Created new {filepath.name} and recorded"
            f" {len(df_new)} setup(s)."
        )