import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import random

st.set_page_config(page_title="PO Signals", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# ⚡ Автообновление каждые 55 секунд
st_autorefresh(interval=55000, limit=None, key="po_refresh")
st.title("📊 PO Signals 1m")

# 🕐 Стабильные браузерные часы
st.markdown("""
<div style="padding:12px; background:#222; border-radius:10px; margin-bottom:15px; border:1px solid #444;">
    📱 <b>Ваше время:</b> <span id="po-clock" style="color:#00ffcc; font-family:monospace; font-size:1.3em;">--:--:--</span> &nbsp;|&nbsp; 
    🔄 Автопроверка каждые 55 сек
</div>
<script>
(function() {
    function runClock() {
        const el = document.getElementById('po-clock');
        if (!el) { setTimeout(runClock, 500); return; }
        function tick() { el.textContent = new Date().toLocaleTimeString(); }
        tick();
        setInterval(tick, 1000);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', runClock);
    else runClock();
})();
</script>
""", unsafe_allow_html=True)

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

# 🌐 Выбор часового пояса (совпадает с настройками PO)
tz_offset = st.selectbox("🌐 Часовой пояс свечей (как в Pocket Option):", 
                         ["UTC+2", "UTC+3", "UTC+4", "UTC+5"], index=0)
offset_hours = int(tz_offset.split("+")[1])

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
        
        # 🔑 Динамический сдвиг времени под ваш выбор
        df["date"] = pd.to_datetime(df["datetime"], utc=True) + pd.Timedelta(hours=offset_hours)
        
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
            f'{sym}<br>{sig_text}<br>{price_str}<br><small style="opacity:0.8">Свеча закрыта в: {last_candle_time}</small>'
            f'</div>',
            unsafe_allow_html=True
        )
        st.plotly_chart(chart(df, sym), use_container_width=True)

st.caption("""
📌 **Как точно совместить с Pocket Option:**
1. Выберите в списке выше тот же часовой пояс, что в настройках PO
2. Сравнивайте **ЗАКРЫТЫЕ** свечи (не текущую формирующуюся)
3. Цены могут отличаться на 1-3 пункта из-за разных поставщиков ликвидности → это нормально
4. Важно совпадение НАПРАВЛЕНИЯ и структуры свечей, а не точных цифр
""")
