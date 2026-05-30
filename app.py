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

st.set_page_config(page_title="PO Signals", page_icon="🎯", layout="wide", initial_sidebar_state="collapsed")

# ⚡ Автообновление каждые 45 секунд (чаще = больше шансов)
st_autorefresh(interval=45000, limit=None, key="po_refresh")
st.title("🎯 PO Signals 1m (Активные)")

# 🔄 Индикатор обновления
last_update = datetime.now().strftime("%H:%M:%S")
st.info(f"🔄 Обновлено: {last_update} | Проверка каждые 45 сек")

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
tz_offset = st.selectbox("🌐 Часовой пояс:", ["UTC+2", "UTC+3", "UTC+4"], index=0)
offset_hours = int(tz_offset.split("+")[1])

SYMBOLS = ["EUR/USD", "GBP/USD", "AUD/USD", "EUR/CHF"]

def get_data(sym, key):
    symbol_encoded = sym.replace("/", "%2F")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol_encoded}&interval=1min&outputsize=60&apikey={key}&_={random.randint(1000,9999)}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        if "values" not in data:
            return None, data.get("message", "Ошибка")
        df = pd.DataFrame(data["values"]).iloc[::-1].reset_index(drop=True)
        df["date"] = pd.to_datetime(df["datetime"], utc=True) + pd.Timedelta(hours=offset_hours)
        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df, None
    except Exception as e:
        return None, str(e)

def analyze(df):
    """Генерирует сигналы с оценкой надёжности"""
    if len(df) < 15:
        return "⏳", "hold", None, 0
    
    df["ema9"] = EMAIndicator(close=df["close"], window=9).ema_indicator()
    df["rsi9"] = RSIIndicator(close=df["close"], window=9).rsi()
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 🎯 Рассчитываем "силу сигнала" (0-100)
    rsi_score = 0
    if curr["rsi9"] < 35:
        rsi_score = max(0, 100 - (curr["rsi9"] * 2.8))  # Чем ниже RSI, тем выше балл
    elif curr["rsi9"] > 65:
        rsi_score = max(0, (curr["rsi9"] - 65) * 2.8)   # Чем выше RSI, тем выше балл
    
    ema_score = 50 if (curr["close"] > curr["ema9"]) == (prev["close"] > prev["ema9"]) else 30
    momentum_score = 70 if (curr["close"] - prev["close"]) * (curr["ema9"] - prev["ema9"]) > 0 else 30
    
    total_score = int((rsi_score * 0.5) + (ema_score * 0.3) + (momentum_score * 0.2))
    
    # 🟢🔴 Сигналы при более мягких условиях
    if curr["rsi9"] < 40 and curr["close"] > curr["ema9"]:
        return "🟢 CALL", "call", curr["close"], total_score
    elif curr["rsi9"] > 60 and curr["close"] < curr["ema9"]:
        return "🔴 PUT", "put", curr["close"], total_score
    # ⚪ Слабый сигнал при пограничных значениях
    elif 35 <= curr["rsi9"] <= 45 or 55 <= curr["rsi9"] <= 65:
        direction = "🟡 WATCH" if curr["rsi9"] < 50 else "🟠 WATCH"
        return direction, "watch", curr["close"], total_score
    
    return "⚪ HOLD", "hold", curr["close"], total_score

def chart(df, sym):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema9"], line=dict(color="orange", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi9"], line=dict(color="purple")), row=2, col=1)
    fig.add_hline(y=60, line_dash="dash", line_color="#ff9800", row=2, col=1)
    fig.add_hline(y=40, line_dash="dash", line_color="#ff9800", row=2, col=1)
    fig.update_layout(height=400, margin=dict(l=25,r=25,t=25,b=25), template="plotly_dark", showlegend=False)
    return fig

# 🔊 Звук
st.markdown("""
<script>
(function(){
  let last = JSON.parse(localStorage.getItem('po_sigs') || '{}');
  let changed = false;
  document.querySelectorAll('[data-sig]').forEach(el => {
    let s = el.dataset.sym, v = el.dataset.sig;
    if(last[s] && last[s] !== v && v !== 'HOLD' && v !== 'watch') changed = true;
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

cols = st.columns(2)
for i, sym in enumerate(SYMBOLS):
    with cols[i % 2]:
        df, err = get_data(sym, api_key)
        if err:
            st.error(f"❌ {sym}: {err}")
            continue
        sig_text, sig_class, price, score = analyze(df)
        last_candle_time = df["date"].iloc[-1].strftime("%H:%M")
        price_str = f"{price:.5f}" if price else "N/A"
        
        # Цвета по надёжности
        if sig_class == "call":
            bg = "#00c853" if score >= 60 else "#4caf50"
        elif sig_class == "put":
            bg = "#ff1744" if score >= 60 else "#f44336"
        elif sig_class == "watch":
            bg = "#ff9800"
        else:
            bg = "#757575"
        
        st.markdown(
            f'<div style="padding:15px;border-radius:10px;text-align:center;font-weight:bold;background:{bg};color:white;margin:5px 0;" data-sym="{sym}" data-sig="{sig_class}">'
            f'{sym}<br>{sig_text}<br>{price_str}<br><small style="opacity:0.9">📊 Надёжность: {score}%</small><br><small style="opacity:0.8">Свеча: {last_candle_time}</small>'
            f'</div>',
            unsafe_allow_html=True
        )
        st.plotly_chart(chart(df, sym), use_container_width=True)

st.caption("""
📌 **Как читать сигналы:**
• 🟢/🔴 + надёжность ≥60% → высокий приоритет входа
• 🟡/🟠 + надёжность 40-59% → можно войти с уменьшенной ставкой
• ⚪ → ждать, рынок в шуме

🎯 **Правила:**
1. Вход через 3-5 сек после сигнала (компенсация задержки API)
2. Экспирация: 1 минута
3. Риск: ≤1% депозита на сделку
4. Торгуйте в сессии Лондон/Нью-Йорк (10:00-18:00 МСК)
5. Ведите журнал: 100 сделок на демо перед реалом
""")
