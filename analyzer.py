import os
import urllib.request
import urllib.parse
import json
import calendar
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

_stock_data_cache = {}
_ticker_resolution_cache = {}

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

def add_one_month(orig_date):
    """
    Adds exactly one month to a datetime object, capping at the last day 
    of the next month if the day does not exist (e.g. Jan 31 -> Feb 28).
    """
    month = orig_date.month - 1 + 1
    year = orig_date.year + month // 12
    month = month % 12 + 1
    day = min(orig_date.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day)

def detect_columns(df):
    """
    Dynamically detects the symbol/ticker column and the date column from a DataFrame.
    Returns (symbol_col, date_col).
    """
    symbol_candidates = ['ticker', 'symbol', 'company', 'stock', 'name', 'company ticker', 'code', 'company name']
    date_candidates = ['date', 'start date', 'created date', 'selected date', 'time', 'timestamp', 'date selected', 'entry date']
    
    detected_symbol = None
    detected_date = None
    
    cols_lower = [str(c).lower().strip() for c in df.columns]
    
    for cand in symbol_candidates:
        if cand in cols_lower:
            idx = cols_lower.index(cand)
            detected_symbol = df.columns[idx]
            break
            
    for cand in date_candidates:
        if cand in cols_lower:
            idx = cols_lower.index(cand)
            detected_date = df.columns[idx]
            break
            
    if not detected_symbol:
        detected_symbol = df.columns[0]
    if not detected_date:
        detected_date = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
    return detected_symbol, detected_date

def search_yahoo_symbol(query):
    """
    Queries Yahoo Finance Search API to find the most appropriate ticker symbol
    prioritizing Indian markets (NSE/BSE).
    """
    clean_query = str(query).strip()
    if not clean_query:
        return None
        
    if clean_query in _ticker_resolution_cache:
        return _ticker_resolution_cache[clean_query]
        
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(clean_query)}&quotesCount=8"
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    
    try:
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode('utf-8'))
            quotes = data.get('quotes', [])
            if quotes:
                # 1. Prioritize Indian NSE (.NS)
                for q in quotes:
                    sym = q.get('symbol', '')
                    if sym.endswith('.NS'):
                        _ticker_resolution_cache[clean_query] = sym
                        return sym
                # 2. Prioritize BSE (.BO)
                for q in quotes:
                    sym = q.get('symbol', '')
                    if sym.endswith('.BO'):
                        _ticker_resolution_cache[clean_query] = sym
                        return sym
                # 3. Fallback to top quote
                top_sym = quotes[0].get('symbol')
                _ticker_resolution_cache[clean_query] = top_sym
                return top_sym
    except Exception as e:
        pass
        
    return None

def fetch_direct_yahoo_chart(symbol, start_date, end_date):
    """
    Directly queries Yahoo Finance v8 chart API using HTTP requests
    """
    p1 = int(start_date.timestamp())
    p2 = int((end_date + timedelta(days=5)).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?period1={p1}&period2={p2}&interval=1d&events=history"
    
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
            chart = data.get('chart', {})
            result = chart.get('result', [])
            if not result:
                return pd.DataFrame()
                
            res_data = result[0]
            timestamps = res_data.get('timestamp', [])
            quote = res_data.get('indicators', {}).get('quote', [{}])[0]
            
            if not timestamps or not quote:
                return pd.DataFrame()
                
            df = pd.DataFrame({
                'Open': quote.get('open', []),
                'High': quote.get('high', []),
                'Low': quote.get('low', []),
                'Close': quote.get('close', []),
                'Volume': quote.get('volume', [])
            }, index=pd.to_datetime(timestamps, unit='s'))
            
            df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
            return df
    except Exception:
        return pd.DataFrame()

def get_stock_data_for_symbol(symbol, start_date, end_date):
    """
    Downloads historical data for a specific symbol using a 3-tier fallback strategy.
    """
    start_str = start_date.strftime('%Y-%m-%d')
    fetch_end = end_date + timedelta(days=5)
    end_str = fetch_end.strftime('%Y-%m-%d')
    cache_key = (symbol, start_str, end_str)
    
    if cache_key in _stock_data_cache:
        return _stock_data_cache[cache_key]
        
    # Tier 1: yfinance Ticker.history
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(start=start_str, end=end_str)
        if hist is not None and not hist.empty:
            if hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)
            _stock_data_cache[cache_key] = hist
            return hist
    except Exception:
        pass
        
    # Tier 2: yfinance.download
    try:
        hist = yf.download(symbol, start=start_str, end=end_str, progress=False)
        if hist is not None and not hist.empty:
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            if hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)
            _stock_data_cache[cache_key] = hist
            return hist
    except Exception:
        pass
        
    # Tier 3: Direct Yahoo Chart API
    hist = fetch_direct_yahoo_chart(symbol, start_date, end_date)
    if hist is not None and not hist.empty:
        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)
        _stock_data_cache[cache_key] = hist
        return hist
        
    return pd.DataFrame()

def resolve_and_fetch(query, start_date, end_date):
    """
    Prioritizes Indian market (.NS and .BO) before US/global tickers
    to ensure Indian stocks like SAIL, HAL, INFY, CCL resolve correctly.
    """
    raw_query = str(query).strip().upper()
    
    # Build candidate list prioritizing Indian markets
    candidates = []
    
    if raw_query.endswith('.NS') or raw_query.endswith('.BO'):
        candidates = [raw_query]
    elif '.' in raw_query:
        candidates = [raw_query]
    else:
        # Prioritize .NS (NSE India) first, then .BO (BSE India), then raw as-is (US)
        candidates = [f"{raw_query}.NS", f"{raw_query}.BO", raw_query]
        
    for sym in candidates:
        data = get_stock_data_for_symbol(sym, start_date, end_date)
        if data is not None and not data.empty:
            return sym, data
            
    # Search Yahoo as fallback
    search_sym = search_yahoo_symbol(query)
    if search_sym and search_sym not in candidates:
        data = get_stock_data_for_symbol(search_sym, start_date, end_date)
        if data is not None and not data.empty:
            return search_sym, data
            
    return raw_query, pd.DataFrame()

def analyze_single_record(ticker_query, start_date_val, target_up_pct, target_down_pct, baseline_type='open'):
    """
    Analyzes a single stock entry over a 1-month window from start_date_val.
    """
    if isinstance(start_date_val, str):
        try:
            start_date = pd.to_datetime(start_date_val)
        except Exception:
            return {
                "Resolved Ticker": ticker_query,
                "Status": "Invalid Date",
                "Details": f"Could not parse date: {start_date_val}"
            }
    else:
        start_date = start_date_val
        
    if pd.isnull(start_date):
        return {
            "Resolved Ticker": ticker_query,
            "Status": "Invalid Date",
            "Details": "Date is missing or null"
        }
        
    end_date = add_one_month(start_date)
    
    resolved_symbol, hist = resolve_and_fetch(ticker_query, start_date, end_date)
    
    if hist is None or hist.empty:
        return {
            "Resolved Ticker": resolved_symbol,
            "Status": "No Data Found",
            "Details": f"No market data available for '{ticker_query}' on {start_date.strftime('%Y-%m-%d')}"
        }
        
    if hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)
        
    window_data = hist.loc[start_date:end_date]
    
    if window_data.empty:
        return {
            "Resolved Ticker": resolved_symbol,
            "Status": "No Data in Window",
            "Details": f"No active trading days in [{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}]"
        }
        
    actual_start_date = window_data.index[0]
    first_day_data = window_data.iloc[0]
    
    if str(baseline_type).lower() == 'close':
        baseline_price = float(first_day_data['Close'])
    else:
        baseline_price = float(first_day_data['Open'])
        
    if pd.isnull(baseline_price) or baseline_price <= 0:
        return {
            "Resolved Ticker": resolved_symbol,
            "Status": "Invalid Baseline",
            "Details": f"Invalid baseline price ({baseline_price})"
        }
        
    target_up_price = baseline_price * (1 + float(target_up_pct) / 100.0)
    target_down_price = baseline_price * (1 - float(target_down_pct) / 100.0)
    
    status = "Neither Hit (Expired)"
    hit_date = None
    days_to_hit = None
    final_close_price = float(window_data.iloc[-1]['Close'])
    
    for current_date, row in window_data.iterrows():
        daily_high = float(row['High'])
        daily_low = float(row['Low'])
        
        up_hit = daily_high >= target_up_price
        down_hit = daily_low <= target_down_price
        
        if up_hit and down_hit:
            status = "Both Hit Same Day"
            hit_date = current_date
            days_to_hit = (current_date - actual_start_date).days
            break
        elif up_hit:
            status = "Target Up Hit"
            hit_date = current_date
            days_to_hit = (current_date - actual_start_date).days
            break
        elif down_hit:
            status = "Target Down Hit"
            hit_date = current_date
            days_to_hit = (current_date - actual_start_date).days
            break
            
    actual_start_str = actual_start_date.strftime('%Y-%m-%d')
    hit_date_str = hit_date.strftime('%Y-%m-%d') if hit_date else "N/A"
    
    return {
        "Resolved Ticker": resolved_symbol,
        "Actual Start Date": actual_start_str,
        "Baseline Price": round(baseline_price, 2),
        "Target Up Price": round(target_up_price, 2),
        "Target Down Price": round(target_down_price, 2),
        "Status": status,
        "Date Hit": hit_date_str,
        "Days to Hit": days_to_hit if days_to_hit is not None else "N/A",
        "End Price": round(final_close_price, 2) if status == "Neither Hit (Expired)" else "N/A"
    }

def analyze_dataframe(df, symbol_col, date_col, target_up_pct, target_down_pct, baseline_type='open'):
    """
    Processes the DataFrame, deduplicating identical same-day entries,
    resolving symbols, and generating the full backtest report.
    """
    working_df = df.copy()
    
    working_df[symbol_col] = working_df[symbol_col].astype(str).str.strip()
    
    # Flexible date parser that handles both Day-First and standard formats
    working_df[date_col] = pd.to_datetime(working_df[date_col], errors='coerce', dayfirst=True)
    
    working_df = working_df.dropna(subset=[symbol_col, date_col])
    
    # Deduplicate same-day entries
    initial_count = len(working_df)
    working_df = working_df.drop_duplicates(subset=[symbol_col, date_col])
    final_count = len(working_df)
    
    if initial_count != final_count:
        print(f"Deduplicated {initial_count - final_count} duplicate company-date entries.")
        
    results_list = []
    
    for idx, row in working_df.iterrows():
        raw_ticker = row[symbol_col]
        date_val = row[date_col]
        
        res = analyze_single_record(raw_ticker, date_val, target_up_pct, target_down_pct, baseline_type)
        
        combined_res = {
            "Original Ticker": raw_ticker,
            "Original Date": date_val.strftime('%Y-%m-%d'),
            **res
        }
        results_list.append(combined_res)
        
    return pd.DataFrame(results_list)
