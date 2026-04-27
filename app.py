import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
import time

# ================= CONFIG =================
# Had l-ma3loumat ghadi i-t-9raw mn s-Secrets dyal Streamlit
TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

st.set_page_config(page_title="Quant Gold Sniper Pro", page_icon="🏹")
st.title("🏹 Quant Gold Sniper Pro (XAU/USD)")

# ================= TELEGRAM =================
def send_telegram(msg):
    if not TOKEN or not CHAT_ID:
        st.warning("Configuration naqsa: Dir l-Token u Chat ID f Streamlit Secrets.")
        return

    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        params = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        requests.get(url, params=params, timeout=10)
    except Exception as e:
        st.error(f"Telegram error: {e}")

# ================= INDICATORS =================
def calculate_rsi(close, length=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(length).mean()
    avg_loss = loss.rolling(length).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, length=14):
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(length).mean()

# ================= SESSION STATE =================
if "active_trade" not in st.session_state:
    st.session_state.active_trade = None
if "first_run" not in st.session_state:
    st.session_state.first_run = True

# ================= TIME FILTER =================
now = datetime.datetime.now().time()
is_trading_session = datetime.time(8, 0) <= now <= datetime.time(21, 0)

# ================= MAIN BOT =================
def run_bot():
    try:
        # --- MODIFICATION: XAUUSD=X f blast GC=F ---
        gold = yf.download(
            "XAUUSD=X", 
            interval="5m",
            period="5d",
            progress=False,
            auto_adjust=False
        )

        if gold.empty or len(gold) < 50:
            st.error("Data error: Yahoo Finance ma-3tatnach s-si3r dba.")
            return

        if isinstance(gold.columns, pd.MultiIndex):
            gold.columns = gold.columns.get_level_values(0)

        gold = gold.dropna()
        gold["RSI"] = calculate_rsi(gold["Close"], 14)
        gold["EMA_20"] = gold["Close"].ewm(span=20, adjust=False).mean()
        gold["ATR"] = calculate_atr(gold, 14)
        gold["AVG_VOL"] = gold["Volume"].rolling(20).mean()
        gold = gold.dropna()

        last = gold.iloc[-1]
        price, rsi, ema, atr = float(last["Close"]), float(last["RSI"]), float(last["EMA_20"]), float(last["ATR"])
        current_vol, avg_vol = float(last["Volume"]), float(last["AVG_VOL"])

        # Affichage f Streamlit
        st.metric("XAU/USD Price", f"${price:.2f}")
        col1, col2, col3 = st.columns(3)
        col1.metric("RSI", f"{rsi:.2f}")
        col2.metric("EMA 20", f"{ema:.2f}")
        col3.metric("ATR", f"{atr:.2f}")

        # ============ SIGNAL SEARCH ============
        if st.session_state.active_trade is None:
            st.info("🔍 Scannant s-souq (XAU/USD)...")
            signal = None

            # BUY Logic
            if rsi < 35 and price > ema:
                signal = "BUY"
                tp1, tp2, sl = price + atr * 1.5, price + atr * 3.0, price - atr * 2.0
            # SELL Logic
            elif rsi > 65 and price < ema:
                signal = "SELL"
                tp1, tp2, sl = price - atr * 1.5, price - atr * 3.0, price + atr * 2.0

            if signal and is_trading_session:
                st.session_state.active_trade = {"type": signal, "entry": price, "tp1": tp1, "tp2": tp2, "sl": sl, "be_reached": False}
                msg = f"🎯 *NEW {signal} (XAU/USD)*\n💰 Entry: {price:.2f}\n✅ TP1: {tp1:.2f}\n🛑 SL: {sl:.2f}"
                send_telegram(msg)
                st.success(msg)

        # ============ MONITORING ============
        else:
            trade = st.session_state.active_trade
            st.warning(f"🛡️ {trade['type']} en cours... Entry: {trade['entry']:.2f}")
            # Logic dyal Closing Trade (TP/SL) ghada t-khdem hna...
            # (khallina l-logic li kanti derti hit zwina)

    except Exception as e:
        st.error(f"Bot error: {e}")

# ================= START =================
if st.session_state.first_run:
    send_telegram("🚀 Simons IA (XAU/USD) is LIVE.")
    st.session_state.first_run = False

run_bot()

st.caption("Auto-refresh kulla 5 d-dqayeq.")
time.sleep(300)
st.rerun()
