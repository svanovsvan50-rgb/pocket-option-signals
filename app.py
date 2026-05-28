import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import time

st.set_page_config(page_title="PO Signals", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

st.title("📊 PO Signals 1m 🔊")

# 🔑 Хранение ключа в сессии
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
SYMBOLS = ["EUR/USD", "GBP/USD", "USD/RUB"]

@st.cache_data(ttl=30)
def get_data(sym, key, ts):
    symbol_encoded = sym.replace("/", "%2F")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol_encoded}&interval=1min&outputsize=50&apikey={key}"
    try:
        r = requests.get(url, timeout=10)
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
    if len(df) < 20: return "⏳ WAIT", "hold", None
    df["ema9"] = EMAIndicator(close=df["close"], window=9).ema_indicator()
    df["rsi14"] = RSIIndicator(close=df["close"], window=14).rsi()
    curr, prev = df.iloc[-1], df.iloc[-2]
    if curr["ema9"] > prev["ema9"] and curr["rsi14"] < 30:
        return "🟢 CALL", "call", curr["close"]
    elif curr["ema9"] < prev["ema9"] and curr["rsi14"] > 70:
        return "🔴 PUT", "put", curr["close"]
    return "⚪ HOLD", "hold", curr["close"]

def chart(df, sym):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema9"], line=dict(color="orange", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi14"], line=dict(color="purple")), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    fig.update_layout(height=400, margin=dict(l=25,r=25,t=25,b=25), template="plotly_dark", showlegend=False)
    return fig

# 🖥️ Отрисовка интерфейса
st.markdown(f"🕒 Обновлено: {time.strftime('%H:%M:%S')}")
cols = st.columns(3)
cache_ts = int(time.time() // 60)

for i, sym in enumerate(SYMBOLS):
    with cols[i]:
        df, err = get_data(sym, api_key, cache_ts)
        if err:
            st.error(f"❌ {sym}: {err}")
            continue
            
        sig_text, sig_class, price = analyze(df)
        price_str = f"{price:.5f}" if price else "N/A"
        bg = "#00c853" if sig_class == "call" else "#ff1744" if sig_class == "put" else "#757575"
        
        st.markdown(
            f'<div style="padding:15px;border-radius:10px;text-align:center;font-weight:bold;background:{bg};color:white;margin:5px 0;" data-sym="{sym}" data-sig="{sig_class}">'
            f'{sym}<br>{sig_text}<br>{price_str}'
            f'</div>',
            unsafe_allow_html=True
        )
        st.plotly_chart(chart(df, sym), use_container_width=True)

# 🔊 Звук + ⏱️ Таймер автообновления (работает в PWA)
st.markdown("""
<script>
(function() {
    // 1. Обратный отсчёт и принудительное обновление
    let t = 55;
    const box = document.createElement('div');
    box.id = 'po-timer';
    box.style.cssText = 'position:fixed;bottom:15px;right:15px;background:#111;color:#0f0;padding:10px 14px;border-radius:10px;font-weight:bold;font-size:14px;z-index:9999;border:1px solid #333;';
    document.body.appendChild(box);
    
    const tick = setInterval(() => {
        t--;
        box.textContent = `🔄 ${t}с`;
        if (t <= 0) {
            clearInterval(tick);
            box.textContent = '🔄 Обновляю...';
            setTimeout(() => window.location.reload(), 500);
        }
    }, 1000);
    box.textContent = `🔄 ${t}с`;

    // 2. Проверка сигналов и звук
    let last = {};
    const snd = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
    snd.volume = 0.6;
    setInterval(() => {
        document.querySelectorAll('[data-sig]').forEach(el => {
            const s = el.dataset.sym, v = el.dataset.sig;
            if (last[s] !== v && v !== 'HOLD') {
                snd.play().catch(()=>{});
                last[s] = v;
            }
        });
    }, 1500);
})();
</script>
""", unsafe_allow_html=True)

st.caption("🔊 Включите звук. Торгуйте на ДЕМО. Риск ≤1% на сделку.")
