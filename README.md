# 📈 Stock Target Backtesting Engine & Dashboard

An automated quantitative backtesting web application and CLI engine built in Python. This tool evaluates monthly stock pick recommendations to determine whether a stock reaches a specified take-profit percentage (up) or stop-loss percentage (down) first within a rolling 1-month window.

## 🚀 Key Features

- **Smart Multi-Tier Symbol Resolution**: Automatically detects and maps stock names across Indian (NSE `.NS`, BSE `.BO`) and US markets (e.g. `RELIANCE` → `RELIANCE.NS`, `Tata Motors` → `TATAMOTORS.NS`, `AAPL` → `AAPL`).
- **Calendar-Aware Window Analysis**: Accurately resolves market closure edge cases (holidays and weekends) to the first active trading day's opening price.
- **First-to-Touch (Barrier) Evaluation**: Eliminates hindsight bias by chronologically tracking daily High and Low price action to verify which threshold triggers first.
- **Same-Day Deduplication**: Cleans input CSVs and collapses redundant same-day ticker entries while independently analyzing multi-date occurrences.
- **Interactive Streamlit Web Dashboard**: Built with a clean, modern interface featuring custom status metrics, performance summary cards (Win Rate, Average Days to Hit), and a one-click CSV export.

---

## 🛠️ Tech Stack

- **Frontend / Dashboard**: Streamlit
- **Data Engineering**: Pandas, NumPy
- **Market Data APIs**: Yahoo Finance (`yfinance` + Direct Chart API Fallback)
- **Environment**: Python 3.9+

---

## 📦 Local Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/TRY26/stock-target-analyzer.git
   cd stock-target-analyzer
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Streamlit Web Dashboard**:
   ```bash
   streamlit run app.py
   ```

5. **Or run via Command Line Interface (CLI)**:
   ```bash
   python3 stock_target_analyzer.py --csv monthly_picks.csv --up 5 --down 2.5
   ```

---

## 📄 License
MIT License
