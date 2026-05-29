import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import random
from datetime import datetime

st.set_page_config(page_title="PO Signals", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# ⚡ Автообновление каждые 50 секунд
st_autorefresh(interval=50000, limit=None, key="po_refresh")
st.title("📊 PO Signals 1m")

# 🔄 Индикатор обновления
last_update = datetime.now().strftime("%H:%M:%S")
st.info(f"🔄 Данные обновлены: {last_update} | Автопроверка каждые 50 сек")

# 🔑 Ключ
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

new_key = st.text_input("🔑 Twelve Data API Key", type="password", value=st.session_state.api_key)
if new_key and new_key != st.session_state.api_key:
    st.session_state.api_key = new_key
    st.rerun()

if not st.session_state.api_key:
    st.info("💡 Введите ключ → нажмите Enter.")
    st.stop()

api_key = st.session_state.api_key

# 🌐 Часовой пояс
tz_offset = st.selectbox("🌐 Часовой пояс (как в PO):", ["UTC+2", "UTC+3", "UTC+4"], index=0)
offset_hours = int(tz_offset.split("+")[1])

# 📊 Добавлены AUD/USD и EUR/CHF
SYMBOLS = ["EUR/USD", "GBP/USD", "AUD/USD", "EUR/CHF"]

def get_data(sym, key):
    symbol_encoded = sym.replace("/", "%2F")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol_encoded}&interval=1min&outputsize=60&apikey={key}&_={random.randint(1000,9999)}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        if "values" not in data:
            return None, data.get("message", "Ошибка API")
        df = pd.DataFrame(data["values"]).iloc[::-1].reset_index(drop=True)
        df["date"] = pd.to_datetime(df["datetime"], utc=True) + pd.Timedelta(hours=offset_hours)
        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df, None
    except Exception as e:
        return None, str(e)

def analyze(df):
    if len(df) < 20: return "⏳ WAIT", "hold", None
    
    df["ema9"] = EMAIndicator(close=df["close"], window=9).ema_indicator()
    df["rsi9"] = RSIIndicator(close=df["close"], window=9).rsi()
    
    curr, prev = df.iloc[-1], df.iloc[-2]
    
    if curr["rsi9"] < 30 and curr["close"] > curr["ema9"] and curr["close"] > prev["close"]:
        return "🟢 CALL", "call", curr["close"]
    elif curr["rsi9"] > 70 and curr["close"] < curr["ema9"] and curr["close"] < prev["close"]:
        return "🔴 PUT", "put", curr["close"]
    return "⚪ HOLD", "hold", curr["close"]

def chart(df, sym):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema9"], line=dict(color="orange", width=2), name="EMA9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi9"], line=dict(color="purple")), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    fig.update_layout(height=400, margin=dict(l=25,r=25,t=25,b=25), template="plotly_dark", showlegend=True)
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

# 🖥️ UI
if st.button("🔍 Проверить сейчас"):
    st.rerun()

# 📱 Адаптивная сетка: 2 колонки на мобильном, 4 на десктопе
st.markdown("<style>@media (max-width: 768px) { .stColumns { flex-wrap: wrap; } }</style>", unsafe_allow_html=True)

cols = st.columns(2)
for i, sym in enumerate(SYMBOLS):
    with cols[i % 2]:
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
            f'{sym}<br>{sig_text}<br>{price_str}<br><small style="opacity:0.8">Свеча: {last_candle_time}</small>'
            f'</div>',
            unsafe_allow_html=True
        )
        st.plotly_chart(chart(df, sym), use_container_width=True)

st.caption("""
📌 **Пары для торговли:**
• EUR/USD, GBP/USD — основные, высокая ликвидность
• AUD/USD — азиатская сессия (03:00–12:00 МСК)
• EUR/CHF — низкая волатильность, меньше сигналов

🎯 **Правила:**
1. 🟢 CALL → ВВЕРХ | 🔴 PUT → ВНИЗ | ⚪ HOLD → ждать
2. 🔊 Звук при смене сигнала
3. ⚠️ Разница цен с PO на 1-4 пипса — норма
4. 📊 Торгуйте на ДЕМО минимум 100 сделок
""")
