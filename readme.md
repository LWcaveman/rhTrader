Markdown

# rhTrader

A systematic, low-screen-time swing trading scanner built in Python. It identifies daily pullback opportunities off 20 EMA and 50 SMA support shelves across a curated liquid watchlist, verifies technical reversal triggers, enforces an anti-chase extension ceiling, and logs active setups into a persistent tracking CSV.

---

## Project Structure

```text
rhTrader/
├── .venv/              # Local virtual environment (ignored by git)
├── reporter.py         # Appends and deduplicates alerts into CSV
├── rhTrader.py         # Core technical scanner and position sizing logic
├── requirements.txt    # Required Python dependencies
└── swing_alerts.csv    # Generated trade log

Prerequisites

    Python 3.10+

    git

Setup Instructions
1. Clone or Open the Repository
Bash

cd ~/rhTrader

2. Create and Activate the Virtual Environment
Bash

# Create the virtual environment
python3 -m venv .venv

# Activate it (Linux / macOS / zsh / bash)
source venv/bin/activate

(Optional) If using Windows PowerShell:
PowerShell

.venv\Scripts\Activate.ps1

3. Create requirements.txt

Create a requirements.txt file in the root directory with the following packages:
Plaintext

pandas>=2.0.0
requests>=2.31.0
yfinance>=0.2.38

4. Install Dependencies
Bash

pip install --upgrade pip
pip install -r requirements.txt

Usage
Run the Scanner

Run the scanner either post-market (after 4:15 PM ET) or pre-market (before 9:15 AM ET) to ensure full, finalized daily candle data:
Bash

python rh-tader.py