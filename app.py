import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import datetime
import random

st.set_page_config(page_title="PO Signals", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

st_autorefresh(interval=55000, limit=None, key="po_refresh")
st.title("📊 PO Signals 1m (Адаптировано)")

if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

new_key = st.text_input("🔑 Twelve Data API Key", type="password", value=st.session_state.api_key)
if new_key and new_key != st.session_state.api_key:
    st.session_state.api_key = new_key
    st.rerun()

if not st.session_state.api_key:
    st.info("💡 Введите ключ → нажмите Enter. Chrome предложит сохранить его.")
    st.stop()

api_key = st.session_state.api_key
# Только реальные Forex-пары (OTC-пары на PO не совпадают с биржей)
SYMBOLS = ["EUR/USD", "GBP/USD"]

def get_data(sym, key):
    symbol_encoded = sym.replace("/", "%2F")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol_encoded}&interval=1min&outputsize=50&apikey={key}&_={random.randint(1000,9999)}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        if "values" not in data:
            return None, data.get("message", "Ошибка API")
        df = pd.DataFrame(data["values"]).iloc[::-1].reset_index(drop=True)
        df["date"] = pd.to_datetime(df["datetime"])
        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df, None
    except Exception as e:
        return None, str(e)

def analyze(df):
    if len(df) < 25:
        return "⏳ WAIT", "hold", None
    
    df["ema9"] = EMAIndicator(close=df["close"], window=9).ema_indicator()
    df["ema21"] = EMAIndicator(close=df["close"], window=21).ema_indicator()
    df["rsi14"] = RSIIndicator(close=df["close"], window=14).rsi()
    
    curr, prev = df.iloc[-1], df.iloc[-2]
    
    # Более чувствительные, но с фильтром тренда
    if curr["rsi14"] < 35 and curr["close"] > curr["ema21"] and curr["ema9"] > prev["ema9"]:
        return "🟢 CALL", "call", curr["close"]
    elif curr["rsi14"] > 65 and curr["close"] < curr["ema21"] and curr["ema9"] < prev["ema9"]:
        return "🔴 PUT", "put", curr["close"]
    return "⚪ HOLD", "hold", curr["close"]

def chart(df, sym):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema9"], line=dict(color="orange", width=2), name="EMA9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema21"], line=dict(color="#00bcd4", width=2), name="EMA21"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi14"], line=dict(color="purple")), row=2, col=1)
    fig.add_hline(y=65, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=35, line_dash="dash", line_color="green", row=2, col=1)
    fig.update_layout(height=420, margin=dict(l=25,r=25,t=25,b=25), template="plotly_dark", showlegend=True)
    return fig

# 🔊 Звук при смене сигнала
st.markdown("""
<script>
(function(){
    let last = JSON.parse(localStorage.getItem('po_sigs') || '{}');
    let changed = false;
    document.querySelectorAll('[data-sig]').forEach(el => {
        let s = el.dataset.sym, v = el.dataset.sig;
        if(last[s] && last[s] !== v && v !== 'HOLD') changed = true;
        last[s] = v;
    });
    if(changed){
        let snd = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
        snd.volume = 0.5; snd.play().catch(()=>{});
    }
    localStorage.setItem('po_sigs', JSON.stringify(last));
})();
</script>
""", unsafe_allow_html=True)

# 🖥️ Интерфейс
local_time = datetime.datetime.now().astimezone().strftime("%H:%M:%S")
st.markdown(f"🕒 Ваше время: `{local_time}` | ⏱️ API задержка: ~15 сек | 🔄 Автопроверка каждые 55 сек")

if st.button("🔍 Проверить сигналы сейчас"):
    st.rerun()

cols = st.columns(2)

for i, sym in enumerate(SYMBOLS):
    with cols[i]:
        df, err = get_data(sym, api_key)
        if err:
            st.error(f"❌ {sym}: {err}")
            continue
            
        sig_text, sig_class, price = analyze(df)
        last_candle_time = df["date"].iloc[-1].strftime("%H:%M")
        price_str = f"{price:.5f}" if price else "N/A"
        bg = "#00c853" if sig_class == "call" else "#ff1744" if sig_class == "put" else "#757575"
        
        st.markdown(
            f'<div style="padding:15px;border-radius:10px;text-align:center;font-weight:bold;background:{bg};color:white;margin:5px 0;" data-sym="{sym}" data-sig="{sig_class}">'
            f'{sym}<br>{sig_text}<br>{price_str}<br><small style="opacity:0.8">Свеча закрыта в: {last_candle_time} UTC</small>'
            f'</div>',
            unsafe_allow_html=True
        )
        st.plotly_chart(chart(df, sym), use_container_width=True)

st.caption("""
📌 **Как торговать с задержкой API:**
1. Дождитесь 🟢/🔴 и звука
2. Откройте PO → выберите ту же пару
3. Подождите 5-10 сек (компенсация задержки)
4. Откройте сделку ВВЕРХ/ВНИЗ на 1 мин
5. ⚠️ Не используйте OTC-пары. Торгуйте в сессии Лондон/Нью-Йорк.
""")
