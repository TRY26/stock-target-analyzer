import argparse
import sys
import os
import pandas as pd
import analyzer

def main():
    parser = argparse.ArgumentParser(description="Stock Target Percentage Breaker Backtester (CLI)")
    
    parser.add_argument(
        "--csv", 
        required=True, 
        help="Path to the input CSV file containing company symbols and dates."
    )
    parser.add_argument(
        "--up", 
        type=float, 
        default=5.0, 
        help="Target profit percentage (e.g. 5.0 for 5%%). Default: 5.0%%"
    )
    parser.add_argument(
        "--down", 
        type=float, 
        default=2.5, 
        help="Target stop loss percentage (e.g. 2.5 for 2.5%%). Default: 2.5%%"
    )
    parser.add_argument(
        "--baseline", 
        choices=["open", "close"], 
        default="open", 
        help="Baseline price type on the starting day. Default: open"
    )
    parser.add_argument(
        "--output", 
        default="backtest_results.csv", 
        help="Path to save the output CSV. Default: backtest_results.csv"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv):
        print(f"Error: Input CSV file '{args.csv}' not found.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Loading '{args.csv}'...")
    try:
        df = pd.read_csv(args.csv)
    except Exception as e:
        print(f"Error reading CSV: {e}", file=sys.stderr)
        sys.exit(1)
        
    if df.empty:
        print("Error: Input CSV file is empty.", file=sys.stderr)
        sys.exit(1)
        
    symbol_col, date_col = analyzer.detect_columns(df)
    print(f"Detected Symbol/Company column: '{symbol_col}'")
    print(f"Detected Date column: '{date_col}'")
    print(f"Parameters: Target Up = +{args.up}%, Target Down = -{args.down}%, Baseline = {args.baseline.upper()}")
    
    print("\nRunning backtest with multi-tier symbol resolution...")
    results_df = analyzer.analyze_dataframe(
        df,
        symbol_col=symbol_col,
        date_col=date_col,
        target_up_pct=args.up,
        target_down_pct=args.down,
        baseline_type=args.baseline
    )
    
    try:
        results_df.to_csv(args.output, index=False)
        print(f"\nSaved analysis output to '{args.output}'")
    except Exception as e:
        print(f"Error saving results: {e}", file=sys.stderr)
        
    print("\n" + "="*55)
    print("BACKTEST RUN SUMMARY")
    print("="*55)
    
    valid_statuses = ["Target Up Hit", "Target Down Hit", "Neither Hit (Expired)", "Both Hit Same Day"]
    valid_df = results_df[results_df["Status"].isin(valid_statuses)]
    total = len(valid_df)
    
    if total > 0:
        up_hits = len(results_df[results_df["Status"] == "Target Up Hit"])
        down_hits = len(results_df[results_df["Status"] == "Target Down Hit"])
        expire = len(results_df[results_df["Status"] == "Neither Hit (Expired)"])
        both = len(results_df[results_df["Status"] == "Both Hit Same Day"])
        
        print(f"Total Successfully Evaluated: {total}")
        print(f"🚀 Profit Target Hits (Win):  {up_hits} ({up_hits/total*100:.1f}%)")
        print(f"🛑 Stop Loss Hits (Loss):     {down_hits} ({down_hits/total*100:.1f}%)")
        print(f"⏳ Expired (Neither Hit):     {expire} ({expire/total*100:.1f}%)")
        print(f"⚠️ Both Hit on Same Day:      {both} ({both/total*100:.1f}%)")
        
        print("\nRecords Preview:")
        preview_cols = [
            "Original Ticker", "Resolved Ticker", "Original Date", 
            "Actual Start Date", "Baseline Price", "Status", "Date Hit", "Days to Hit"
        ]
        available_preview_cols = [c for c in preview_cols if c in results_df.columns]
        print(results_df[available_preview_cols].to_string(index=False))
    else:
        print("No valid ticker and date records could be verified or downloaded.")
    
    print("="*55)

if __name__ == "__main__":
    main()
