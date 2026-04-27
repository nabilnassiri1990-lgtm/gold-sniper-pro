import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
import time

st.set_page_config(page_title="Quant Gold Sniper Pro", page_icon="🏹")
st.title("🏹 Quant Gold Sniper Pro")

# ================= TELEGRAM =================
def send_telegram(msg):
    if not TOKEN or not CHAT_ID:
        st.warning("Telegram token/chat_id not configured.")
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
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(df, length=14):
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(length).mean()
    return atr

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
        gold = yf.download(
            "GC=F",
            interval="5m",
            period="5d",
            progress=False,
            auto_adjust=False
        )

        if gold.empty or len(gold) < 50:
            st.error("Data error: not enough Gold data.")
            return

        # Fix multi-index columns if yfinance returns them
        if isinstance(gold.columns, pd.MultiIndex):
            gold.columns = gold.columns.get_level_values(0)

        gold = gold.dropna()

        gold["RSI"] = calculate_rsi(gold["Close"], 14)
        gold["EMA_20"] = gold["Close"].ewm(span=20, adjust=False).mean()
        gold["ATR"] = calculate_atr(gold, 14)
        gold["AVG_VOL"] = gold["Volume"].rolling(20).mean()

        gold = gold.dropna()

        last = gold.iloc[-1]

        price = float(last["Close"])
        rsi = float(last["RSI"])
        ema = float(last["EMA_20"])
        atr = float(last["ATR"])
        current_vol = float(last["Volume"])
        avg_vol = float(last["AVG_VOL"])

        st.metric("Gold Price", f"${price:.2f}")
        st.metric("RSI", f"{rsi:.2f}")
        st.metric("EMA 20", f"{ema:.2f}")
        st.metric("ATR", f"{atr:.2f}")

        # ============ SIGNAL SEARCH ============
        if st.session_state.active_trade is None:
            st.info("🔍 Searching for signals...")

            signal = None

            if rsi < 35 and price > ema and current_vol > avg_vol:
                signal = "BUY"
                tp1 = price + atr * 1.5
                tp2 = price + atr * 2.5
                tp3 = price + atr * 4.0
                sl = price - atr * 2.0

            elif rsi > 65 and price < ema and current_vol > avg_vol:
                signal = "SELL"
                tp1 = price - atr * 1.5
                tp2 = price - atr * 2.5
                tp3 = price - atr * 4.0
                sl = price + atr * 2.0

            if signal and is_trading_session:
                st.session_state.active_trade = {
                    "type": signal,
                    "entry": price,
                    "tp1": tp1,
                    "tp2": tp2,
                    "tp3": tp3,
                    "sl": sl,
                    "be_reached": False
                }

                msg = (
                    f"🎯 *NEW GOLD SIGNAL: {signal}*\n\n"
                    f"💰 Entry: {price:.2f}\n"
                    f"✅ TP1: {tp1:.2f}\n"
                    f"🚀 TP2: {tp2:.2f}\n"
                    f"🔥 TP3: {tp3:.2f}\n"
                    f"🛑 SL: {sl:.2f}\n\n"
                    f"RSI: {rsi:.2f}"
                )

                send_telegram(msg)
                st.success(msg)

            elif signal and not is_trading_session:
                st.warning("Signal found, but outside trading session.")

        # ============ TRADE MONITOR ============
        else:
            trade = st.session_state.active_trade
            st.warning(f"🛡️ Monitoring {trade['type']} trade...")

            st.write(trade)

            if not trade["be_reached"]:
                if trade["type"] == "BUY" and price >= trade["tp1"]:
                    trade["be_reached"] = True
                    trade["sl"] = trade["entry"]
                    send_telegram(f"⚡ *TP1 REACHED!* Price: {price:.2f}\nSL moved to Break Even.")

                elif trade["type"] == "SELL" and price <= trade["tp1"]:
                    trade["be_reached"] = True
                    trade["sl"] = trade["entry"]
                    send_telegram(f"⚡ *TP1 REACHED!* Price: {price:.2f}\nSL moved to Break Even.")

            if trade["type"] == "BUY" and price >= trade["tp3"]:
                send_telegram(f"🏆 *TP3 HIT!* Closed at {price:.2f}")
                st.session_state.active_trade = None

            elif trade["type"] == "SELL" and price <= trade["tp3"]:
                send_telegram(f"🏆 *TP3 HIT!* Closed at {price:.2f}")
                st.session_state.active_trade = None

            elif trade["type"] == "BUY" and price <= trade["sl"]:
                status = "Break Even" if trade["be_reached"] else "SL Hit"
                send_telegram(f"🛑 *{status}* at {price:.2f}")
                st.session_state.active_trade = None

            elif trade["type"] == "SELL" and price >= trade["sl"]:
                status = "Break Even" if trade["be_reached"] else "SL Hit"
                send_telegram(f"🛑 *{status}* at {price:.2f}")
                st.session_state.active_trade = None

    except Exception as e:
        st.error(f"Bot error: {e}")

# ================= START =================
if st.session_state.first_run:
    send_telegram("🚀 Quant Gold Sniper Pro is LIVE.")
    st.session_state.first_run = False

run_bot()

st.caption("Auto-refresh every 5 minutes.")
time.sleep(300)
st.rerun()
