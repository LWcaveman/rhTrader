from datetime import datetime
from pathlib import Path
import pandas as pd


def log_alerts_to_csv(alerts: list, filename: str = "swing_alerts.csv") -> None:
    """Appends active swing alerts to a persistent CSV file in the repository root.

    Prevents duplicate entries if the scanner is run multiple times on the same
    day.
    """
    if not alerts:
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Add timestamp and date tracking
    records = []
    for item in alerts:
        row = item.copy()
        row["Date"] = today_str
        row["Logged At"] = timestamp_str
        records.append(row)

    df_new = pd.DataFrame(records)

    # Reorder columns so Date and Ticker lead the sheet
    leading_cols = ["Date", "Logged At", "Ticker"]
    other_cols = [c for c in df_new.columns if c not in leading_cols]
    df_new = df_new[leading_cols + other_cols]

    filepath = Path(filename)

    if filepath.exists() and filepath.stat().st_size > 0:
        try:
            df_existing = pd.read_csv(filepath)

            # Deduplication: Skip if ticker has already been recorded today
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
                    f"[Reporter] All {len(alerts)} setup(s) already logged for"
                    f" today in {filename}."
                )
                return

            # Append new records without writing headers again
            df_to_append.to_csv(filepath, mode="a", header=False, index=False)
            print(
                f"[Reporter] Appended {len(df_to_append)} new setup(s) to"
                f" {filename}."
            )

        except Exception as e:
            # Fallback append if CSV read fails
            df_new.to_csv(filepath, mode="a", header=False, index=False)
            print(
                f"[Reporter] Appended {len(df_new)} setup(s) to {filename}"
                f" (Fallback: {e})."
            )
    else:
        # Create new file with header
        df_new.to_csv(filepath, mode="w", header=True, index=False)
        print(
            f"[Reporter] Created new {filename} and recorded {len(df_new)}"
            " setup(s)."
        )