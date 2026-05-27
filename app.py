import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from datetime import datetime

st.set_page_config(
    page_title="PO Signals", 
    page_icon="📊", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# Принудительно задаём имя ярлыка для Android/iOS
st.markdown("""
<meta name="application-name" content="PO Signals">
<meta name="apple-mobile-web-app-title" content="PO Signals">
<meta name="mobile-web-app-capable" content="yes">
""", unsafe_allow_html=True)


# 🔊 Звуковые сигналы + стили
st.markdown("""
<style>
    .signal-box { padding: 15px; border-radius: 12px; text-align: center; font-weight: bold; margin: 8px 0; }
    .call { background: linear-gradient(135deg, #00c853, #69f0ae); color: #000; }
    .put { background: linear-gradient(135deg, #ff1744, #ff5252); color: #fff; }
    .hold { background: linear-gradient(135deg, #757575, #bdbdbd); color: #fff; }
    .error { background: #ffebee; color: #c62828; padding: 10px; border-radius: 8px; margin: 10px 0; }
</style>
<script>
    const callSound = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
    const putSound = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
    let last = {};
    function check() {
        document.querySelectorAll('[data-sig]').forEach(el => {
            const sym = el.dataset.sym, sig = el.dataset.sig;
            if (last[sym] !== sig && sig !== 'HOLD') {
                (sig === 'CALL' ? callSound : putSound).play().catch(()=>{});
                last[sym] = sig;
            }
        });
    }
    setInterval(check, 2000);
</script>
""", unsafe_allow_html=True)

st.title("📊 PO Signals 1m 🔊")

# 🔑 Ввод ключа
# 🔑 Стабильная работа с API ключом
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

def save_key():
    st.session_state.api_key = st.session_state.input_key.strip()
    if st.session_state.api_key:
        st.rerun()

st.text_input("st.markdown("<style>input[type='text'] { -webkit-text-security: disc; }</style>", unsafe_allow_html=True)", 
              type="text", 
              key="input_key",
              value=st.session_state.api_key,
              on_change=save_key,
              placeholder="Введите ключ и нажмите Enter")

api_key = st.session_state.api_key

if not api_key:
    st.info("⏳ Введите API-ключ в поле выше и нажмите Enter. Он сохранится для этой сессии.")
    st.stop()

# 🧪 Тест ключа (опционально, можно скрыть)
if st.button("🧪 Проверить ключ", type="primary"):
    with st.spinner("Проверка..."):
        test_url = f"https://api.twelvedata.com/time_series?symbol=EUR%2FUSD&interval=1min&outputsize=1&apikey={api_key}"
        try:
            r = requests.get(test_url, timeout=10)
            data = r.json()
            if "values" in data:
                st.success("✅ Ключ работает!")
            else:
                st.error(f"❌ {data.get('message', 'Ошибка')}")
        except Exception as e:
            st.error(f"❌ {e}")

# ⚙️ Настройки
SYMBOLS = ["EUR/USD", "GBP/USD", "USD/RUB"]

@st.cache_data(ttl=60)
def get_data(sym, key, minute):
    symbol_encoded = sym.replace("/", "%2F")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol_encoded}&interval=1min&outputsize=50&apikey={key}"
    
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        data = r.json()
        if "message" in data:
            return None, data["message"]
        if "values" not in data or not data["values"]:
            return None, "Нет данных в ответе"
        df = pd.DataFrame(data["values"])
        df = df.iloc[::-1].reset_index(drop=True)
        df["date"] = pd.to_datetime(df["datetime"])
        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        if df["close"].isna().any():
            return None, "Ошибка парсинга цен"
        return df, None
    except requests.Timeout:
        return None, "Тайм-аут (попробуйте позже)"
    except Exception as e:
        return None, str(e)

def analyze(df):
    if len(df) < 20:
        return "⏳ WAIT", "hold", None
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
    fig.update_layout(height=420, margin=dict(l=25,r=25,t=25,b=25), template="plotly_dark", showlegend=False)
    return fig

# 📊 Основной блок с гарантированным обновлением
st.markdown(f"🕒 Обновлено: {datetime.now().strftime('%H:%M:%S')}")
cols = st.columns(3)

# Получаем текущую минуту для принудительного сброса кэша
import time
current_minute = int(time.time() // 60)

for i, sym in enumerate(SYMBOLS):
    with cols[i]:
        # Передаём current_minute, чтобы кэш обновлялся каждую минуту
        df, err = get_data(sym, api_key, current_minute)
        if err:
            st.markdown(f'<div class="error">❌ {sym}<br><small>{err}</small></div>', unsafe_allow_html=True)
            continue
        
        sig_text, sig_class, price = analyze(df)
        price_str = f"{price:.5f}" if price else "N/A"
        
        st.markdown(
            f'<div class="signal-box {sig_class}" data-sig="{sig_class}" data-sym="{sym}">'
            f'{sym}<br>{sig_text}<br>{price_str}'
            f'</div>',
            unsafe_allow_html=True
        )
        st.plotly_chart(chart(df, sym), use_container_width=True)

st.caption("""
**Как использовать:**
• 🟢 CALL → сделка ВВЕРХ на 1 мин | 🔴 PUT → ВНИЗ | ⚪ HOLD → ждать
• 🔊 Звук при смене сигнала (включите звук на телефоне)
• ⚠️ Тестируйте на ДЕМО-счёте минимум 100 сделок перед реальными деньгами
""")

# 🔄 Гарантированное обновление страницы (работает в Android PWA)
st.markdown("""
<script>
(function() {
    let timeLeft = 55;
    const timer = document.createElement('div');
    timer.style.cssText = 'position:fixed;bottom:10px;right:10px;background:#1e1e1e;color:#00ff00;padding:6px 10px;border-radius:8px;font-size:12px;z-index:9999;';
    document.body.appendChild(timer);
    
    const interval = setInterval(() => {
        timeLeft--;
        timer.textContent = `🔄 Обновление: ${timeLeft}с`;
        if (timeLeft <= 0) {
            clearInterval(interval);
            window.location.reload();
        }
    }, 1000);
})();
</script>
""", unsafe_allow_html=True)
