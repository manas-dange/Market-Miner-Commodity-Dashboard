import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import google.generativeai as genai
import random
import time
from datetime import datetime

# --- 1. WAR ROOM UI ARCHITECTURE ---
st.set_page_config(page_title="MARKET MINER | V18", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;500&display=swap');
    * { font-family: 'JetBrains Mono', monospace; border-radius: 0 !important; }
    [data-testid="stAppViewContainer"] { background-color: #000000; color: #00FFCC; }
    [data-testid="stSidebar"] { background-color: #050505 !important; border-right: 1px solid #111; }
    .ai-insights-box { background: #050505; border: 1px solid #00FFCC; padding: 20px; color: #00FFCC; box-shadow: 0 0 15px #00FFCC22; }
    .ingest-text { color: #00FFCC; font-size: 0.8rem; animation: blinker 1s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.1; } }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONFIG & AI AUTO-DISCOVERY ---
TICKERS = {"WTI_CRUDE": "CL=F", "GOLD": "GC=F", "COPPER": "HG=F", "NAT_GAS": "NG=F", "SILVER": "SI=F"}

st.sidebar.title("⚔️ COMMAND CENTER")
target_label = st.sidebar.selectbox("PRIMARY_FOCUS", list(TICKERS.keys()))
gemini_key = st.sidebar.text_input("GEMINI_API_KEY", type="password")

# Resilient AI Discovery
model = None
if gemini_key:
    genai.configure(api_key=gemini_key)
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash_m = [m for m in models if 'flash' in m.lower()]
        model = genai.GenerativeModel(flash_m[0] if flash_m else models[0])
    except: pass

@st.cache_data(ttl=55) # Slightly less than 60s to ensure fresh data for each loop
def fetch_exchange_data():
    # Only official 1-minute candles from Yahoo
    return yf.download(list(TICKERS.values()), period="1d", interval="1m", auto_adjust=True)

# --- 3. THE LIVE FRAGMENT (The 60-Second Pulse) ---
@st.fragment(run_every="60s")
def render_live_dashboard(target):
    t_sym = TICKERS[target]
    raw_data = fetch_exchange_data()
    t_df = raw_data.xs(t_sym, level=1, axis=1).copy()
    
    # 1. INITIALIZE PLACEHOLDERS
    header_spot = st.empty()
    chart_spot = st.empty()
    triple_spot = st.empty()
    ai_spot = st.empty()

    # 2. THE INGESTION ANIMATION
    # Every 60 seconds, we "replay" the last 30 minutes of data to show the 'build'
    window_size = 30 
    anim_data = t_df.tail(window_size)
    
    # We show the first 25 instantly, then animate the final 5 candles (including the new one)
    for i in range(window_size - 5, window_size + 1):
        current_view = anim_data.iloc[:i]
        
        # Update Header with "Ingesting" Status
        header_spot.markdown(f"### 🖥️ OPS_DECK // {target} <span class='ingest-text'>● INGESTING_EXCHANGE_DATA: {i}/{window_size}</span>", unsafe_allow_html=True)

        # Draw the Stretched Candlestick Chart
        with chart_spot.container():
            fig_main = go.Figure(data=[go.Candlestick(
                x=current_view.index, 
                open=current_view['Open'], high=current_view['High'], 
                low=current_view['Low'], close=current_view['Close'], 
                increasing_line_color='#00FFCC', decreasing_line_color='#FF0055'
            )])
            fig_main.update_layout(
                template="plotly_dark", height=450, paper_bgcolor='black', 
                plot_bgcolor='black', xaxis_rangeslider_visible=False, 
                margin=dict(t=0, b=0, l=0, r=0),
                # Set fixed range to prevent chart jumping during drawing
                xaxis=dict(range=[anim_data.index[0], anim_data.index[-1]])
            )
            st.plotly_chart(fig_main, use_container_width=True, key=f"anim_{i}_{time.time()}")
        
        # Tactical delay to make the "generating" visible
        time.sleep(0.15)

    # 3. STATS CALCULATION (Final Frame)
    sma = t_df['Close'].rolling(20).mean()
    std = t_df['Close'].rolling(20).std()
    current_z = (t_df['Close'].iloc[-1] - sma.iloc[-1]) / std.iloc[-1]

    # 4. TRIPLE THREAT MONITOR (The 1-Line Grid)
    with triple_spot.container():
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.caption("SYSTEMIC_CORRELATION")
            fig_heat = px.imshow(raw_data['Close'].corr(), color_continuous_scale='RdBu_r', aspect="auto")
            fig_heat.update_layout(template="plotly_dark", height=250, margin=dict(t=0, b=0), showlegend=False)
            st.plotly_chart(fig_heat, use_container_width=True, key=f"heat_{time.time()}")
            
        with c2:
            st.caption("SEASONAL_PROBABILITY")
            # Returns grouped by the minute of the hour (Tactical Momentum)
            rets = t_df['Close'].pct_change()
            seasonal = rets.groupby(rets.index.minute).mean() * 100
            fig_sea = px.bar(x=seasonal.index, y=seasonal.values, color_discrete_sequence=['#00FFCC'])
            fig_sea.update_layout(template="plotly_dark", height=250, margin=dict(t=0, b=0))
            st.plotly_chart(fig_sea, use_container_width=True, key=f"sea_{time.time()}")
            
        with c3:
            st.caption("MEAN_REVERSION_FORCE (Z-SCORE)")
            fig_z = go.Figure(go.Indicator(mode="gauge+number", value=current_z, 
                gauge={'axis': {'range': [-4, 4]}, 'bar': {'color': "#00FFCC"}, 
                       'steps': [{'range': [-4, -2], 'color': 'rgba(0,255,204,0.2)'}, {'range': [2, 4], 'color': 'rgba(255, 0, 85, 0.2)'}]}))
            fig_z.update_layout(template="plotly_dark", height=250, paper_bgcolor='black', margin=dict(t=30, b=0))
            st.plotly_chart(fig_z, use_container_width=True, key=f"z_{time.time()}")

    # 5. FULL-WIDTH AI STRATEGIC DIRECTIVE
    with ai_spot.container():
        st.markdown("#### [NEURAL_NET_STRATEGIC_DIRECTIVE]")
        if st.button("⚡ EXECUTE INFERENCE", key="inf_btn"):
            if model:
                with st.spinner("INFERRING..."):
                    ctx = f"Asset: {target}. Price: {t_df['Close'].iloc[-1]:.2f}. Z: {current_z:.2f}. Give a short tactical command."
                    st.session_state.ai_directive = model.generate_content(ctx).text
            else:
                st.error("AI_OFFLINE: API_KEY_REQUIRED")

        if "ai_directive" in st.session_state:
            st.markdown(f"<div class='ai-insights-box'>{st.session_state.ai_directive}</div>", unsafe_allow_html=True)

# --- 4. EXECUTION ---
render_live_dashboard(target_label)

# SIDEBAR CHATBOT
st.sidebar.divider()
if "chat_log" not in st.session_state: st.session_state.chat_log = []
for m in st.session_state.chat_log:
    with st.sidebar.chat_message(m["role"]): st.write(m["content"])

if prompt := st.sidebar.chat_input("Query system..."):
    st.session_state.chat_log.append({"role": "user", "content": prompt})
    with st.sidebar.chat_message("user"): st.write(prompt)
    if model:
        try:
            bot_res = model.generate_content(f"Context: {target_label}. User asks: {prompt}").text
        except Exception as e:
            bot_res = f"ERR: {e}"
    else: bot_res = "KEY_REQUIRED."
    with st.sidebar.chat_message("assistant"): st.write(bot_res)
    st.session_state.chat_log.append({"role": "assistant", "content": bot_res})
