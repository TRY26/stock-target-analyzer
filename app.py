import streamlit as st
import pandas as pd
import numpy as np
import analyzer
import io

# Set page config for a wide dashboard layout
st.set_page_config(
    page_title="Stock Target Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for modern minimalist look
st.markdown("""
    <style>
    /* Metric Card Styling */
    [data-testid="stMetricValue"] {
        font-size: 34px;
        font-weight: bold;
        color: #1e293b;
    }
    [data-testid="stMetricLabel"] {
        font-size: 15px;
        color: #64748b;
    }
    
    /* Button custom style */
    div.stButton > button {
        background-color: #8cd1a4 !important;
        color: #0f2d19 !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 10px 20px !important;
    }
    div.stButton > button:hover {
        background-color: #76bfa2 !important;
        color: #0f2d19 !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Stock Target Backtesting Dashboard")
st.markdown("Automate stock target verification with smart symbol resolution (NSE, BSE, US Markets) and multi-tier market data retrieval.")

if "results" not in st.session_state:
    st.session_state.results = None
if "df_source" not in st.session_state:
    st.session_state.df_source = None

with st.sidebar:
    st.header("BACKTEST SETTINGS")
    
    uploaded_file = st.file_uploader(
        "Upload Ticker Data (CSV)", 
        type=["csv"], 
        help="Upload a CSV with company/ticker names and dates. Indian and global stocks supported."
    )
    
    st.markdown("---")
    
    target_up = st.number_input(
        "Target Profit (%)",
        min_value=0.1,
        max_value=100.0,
        value=5.0,
        step=0.5,
        help="Percentage gain to trigger a Profit Hit."
    )
    
    target_down = st.number_input(
        "Target Stop Loss (%)",
        min_value=0.1,
        max_value=100.0,
        value=2.5,
        step=0.5,
        help="Percentage loss to trigger a Stop Loss Hit."
    )
    
    baseline_type = st.selectbox(
        "Baseline Price Type",
        options=["Open", "Close"],
        index=0,
        help="Which price on the starting day to calculate percentages from."
    )
    
    st.markdown("---")
    
    run_clicked = st.button("RUN BACKTEST", use_container_width=True)

# Main Dashboard view
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        st.session_state.df_source = df
    except Exception as e:
        st.error(f"Error loading CSV file: {e}")
        df = None

    if df is not None:
        symbol_col, date_col = analyzer.detect_columns(df)
        
        st.info(f"📁 **Detected Columns**: Ticker/Company column: `{symbol_col}` | Date column: `{date_col}`")
        
        if run_clicked:
            with st.spinner("Fetching market data with NSE priority and evaluating targets..."):
                results_df = analyzer.analyze_dataframe(
                    df, 
                    symbol_col=symbol_col, 
                    date_col=date_col, 
                    target_up_pct=target_up, 
                    target_down_pct=target_down, 
                    baseline_type=baseline_type
                )
                st.session_state.results = results_df
                st.success("Analysis complete!")
                
        if st.session_state.results is not None:
            res_df = st.session_state.results
            
            # --- SUMMARY METRICS ---
            st.subheader("Performance Summary")
            
            valid_statuses = ["Target Up Hit", "Target Down Hit", "Neither Hit (Expired)", "Both Hit Same Day"]
            valid_df = res_df[res_df["Status"].isin(valid_statuses)]
            total_trades = len(valid_df)
            
            if total_trades > 0:
                up_hits = len(res_df[res_df["Status"] == "Target Up Hit"])
                win_rate = (up_hits / total_trades) * 100
                
                hit_days = res_df[res_df["Days to Hit"].notna()]["Days to Hit"]
                hit_days_numeric = pd.to_numeric(hit_days, errors='coerce').dropna()
                avg_days = hit_days_numeric.mean() if not hit_days_numeric.empty else 0.0
            else:
                win_rate = 0.0
                avg_days = 0.0
                up_hits = 0
                
            m_col1, m_col2, m_col3 = st.columns(3)
            
            with m_col1:
                st.metric(
                    label="Win Rate (Target Up Hit)", 
                    value=f"{win_rate:.1f}%", 
                    delta=f"{up_hits} / {total_trades} hit" if total_trades > 0 else None
                )
            with m_col2:
                st.metric(
                    label="Average Days to Hit Target", 
                    value=f"{avg_days:.1f} Days" if avg_days > 0 else "N/A"
                )
            with m_col3:
                st.metric(
                    label="Total Trades Evaluated", 
                    value=str(total_trades)
                )
                
            st.markdown("---")
            
            # --- DATA TABLE WITH COLOR HIGHLIGHTING ---
            st.subheader("Detailed Backtest Results")
            
            def style_status_rows(row):
                status = str(row.get("Status", ""))
                if status == "Target Up Hit":
                    color = "background-color: #d1e7dd; color: #0f5132; font-weight: 500;"
                elif status == "Target Down Hit":
                    color = "background-color: #f8d7da; color: #842029; font-weight: 500;"
                elif status == "Both Hit Same Day":
                    color = "background-color: #fff3cd; color: #664d03; font-weight: 500;"
                elif "No Data" in status or "Invalid" in status:
                    color = "background-color: #f1f5f9; color: #64748b;"
                else:
                    color = "color: #1e293b;"
                return [color] * len(row)
            
            display_cols = [
                "Original Ticker", 
                "Resolved Ticker",
                "Original Date", 
                "Actual Start Date", 
                "Baseline Price", 
                "Target Up Price", 
                "Target Down Price", 
                "Status", 
                "Date Hit", 
                "Days to Hit",
                "End Price"
            ]
            
            available_cols = [c for c in display_cols if c in res_df.columns]
            display_df = res_df[available_cols].copy()
            
            col_rename_map = {
                "Original Ticker": "Input Company/Ticker",
                "Resolved Ticker": "Market Symbol",
                "Original Date": "Entry Date",
                "Actual Start Date": "Trading Start Date",
                "Baseline Price": "Baseline Price",
                "Target Up Price": "Target Up",
                "Target Down Price": "Target Down",
                "Status": "Status",
                "Date Hit": "Date Hit",
                "Days to Hit": "Days to Hit",
                "End Price": "End Price (1mo)"
            }
            display_df.rename(columns=col_rename_map, inplace=True)
            
            # Ensure uniform string types to prevent Arrow serialization issues
            for col in display_df.columns:
                display_df[col] = display_df[col].astype(str).replace({'nan': 'N/A', 'None': 'N/A', '<NA>': 'N/A', 'NaT': 'N/A'})
            
            styled_df = display_df.style.apply(style_status_rows, axis=1)
            st.dataframe(
                styled_df, 
                use_container_width=True, 
                height=500
            )
            
            # --- EXPORT BUTTON ---
            st.markdown("### Export Output")
            csv_buffer = io.StringIO()
            res_df.to_csv(csv_buffer, index=False)
            csv_str = csv_buffer.getvalue()
            
            st.download_button(
                label="📥 DOWNLOAD RESULTS AS CSV",
                data=csv_str,
                file_name="backtest_results.csv",
                mime="text/csv",
                use_container_width=True
            )
            
else:
    st.info("💡 Please upload a CSV file of tickers and dates in the sidebar to get started.")
    
    st.markdown("""
        ### Supported Input Formats
        You can provide either ticker symbols or company names across both US and Indian stock markets:
        
        | Company / Ticker | Date | Auto-Resolution |
        |---|---|---|
        | `RELIANCE` | 2025-01-15 | Auto-resolves to `RELIANCE.NS` (NSE) |
        | `Tata Motors` | 2025-01-20 | Auto-resolves to `TATAMOTORS.NS` (NSE) |
        | `SAIL` | 2025-02-01 | Auto-resolves to `SAIL.NS` (NSE) |
        | `HAL` | 2025-02-05 | Auto-resolves to `HAL.NS` (NSE) |
        | `AAPL` | 2025-02-15 | Resolves to `AAPL` (NASDAQ) |
        
        *Dates must be in the past so historical market data exists.*
    """)
