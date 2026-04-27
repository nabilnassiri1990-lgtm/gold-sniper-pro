import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
import time

# ================= CONFIG =================
TOKEN = st.secrets.get("TELEGRAM_TOKEN")
CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

st.set_page_config(page_title="Quant Gold Sniper Pro", page_icon="🏹")
st.title("🏹 Quant Gold Sniper Pro")
st.header("(XAU/USD)")

# ================= TELEGRAM =================
def send_telegram(msg):
    if not TOKEN or not CHAT_ID:
        st.warning("Telegram token/chat_id not configured.")
        return

    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        params = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        r = requests.get(url, params=params, timeout=10)

        if r.status_code != 200:
            st.error(f"Telegram error: {r.text}")

    except Exception as e:
        st.error(f"Telegram exception: {e}")

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

# ================= DATA =================
def get_gold_data():
    tickers = ["XAUUSD=X", "GC=F"]

    for ticker in tickers:
        for _ in range(3):
            data = yf.download(
                ticker,
                interval="5m",
                period="5d",
                progress=False,
                threads=False,
                auto_adjust=False
            )

            if not data.empty:
                return data, ticker

            time.sleep(2)

    data = yf.download(
        "XAUUSD=X",
        interval="1d",
        period="1mo",
        progress=False,
        threads=False,
        auto_adjust=False
    )

    return data, "XAUUSD=X fallback 1d"

# ================= SESSION =================
if "active_trade" not in st.session_state:
    st.session_state.active_trade = None

if "test_sent" not in st.session_state:
    send_telegram("✅ TEST: Bot khdam w mconnecti m3a Telegram 🚀")
    st.session_state.test_sent = True

# ================= TIME FILTER =================
now = datetime.datetime.now().time()
is_trading_session = datetime.time(8, 0) <= now <= datetime.time(21, 0)

# ================= BOT =================
def run_bot():
    try:
        gold, ticker_used = get_gold_data()

        if gold.empty or len(gold) < 50:
            st.error("Data error: Yahoo Finance ma-3tatnach s-si3r dba.")
            st.write("Ticker used:", ticker_used)
            st.write(gold.tail())
            return

        if isinstance(gold.columns, pd.MultiIndex):
            gold.columns = gold.columns.get_level_values(0)

        gold = gold.dropna()

        gold["RSI"] = calculate_rsi(gold["Close"], 14)
        gold["EMA_20"] = gold["Close"].ewm(span=20, adjust=False).mean()
        gold["ATR"] = calculate_atr(gold, 14)
        gold["AVG_VOL"] = gold["Volume"].rolling(20).mean()

        gold = gold.dropna()

        if gold.empty:
            st.error("Data error after indicators.")
            return

        last = gold.iloc[-1]

        price = float(last["Close"])
        rsi = float(last["RSI"])
        ema = float(last["EMA_20"])
        atr = float(last["ATR"])
        current_vol = float(last["Volume"])
        avg_vol = float(last["AVG_VOL"])

        st.success(f"Data OK ✅ | Source: {ticker_used}")
        st.metric("Gold Price", f"${price:.2f}")
        st.metric("RSI", f"{rsi:.2f}")
        st.metric("EMA 20", f"{ema:.2f}")
        st.metric("ATR", f"{atr:.2f}")

        st.write("Last candles:")
        st.write(gold.tail())

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
                    f"RSI: {rsi:.2f}\n"
                    f"Source: {ticker_used}"
                )

                send_telegram(msg)
                st.success(msg)

            elif signal and not is_trading_session:
                st.warning("Signal found, but outside trading session.")
            else:
                st.info("No signal now.")

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

run_bot()

st.caption("Auto-refresh kulla 5 d-qayeq.")
time.sleep(300)
st.rerun()
