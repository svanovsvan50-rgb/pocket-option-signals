import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import random
from datetime import datetime, timezone

st.set_page_config(page_title="PO Signals Active", page_icon="🎯", layout="wide", initial_sidebar_state="collapsed")

# ⚡ Автообновление каждые 40 секунд
st_autorefresh(interval=40000, limit=None, key="po_refresh")
st.title("🎯 PO Signals 1m Active")

# 📊 Счётчик проверок (для отладки)
if 'checks' not in st.session_state:
    st.session_state.checks = 0
st.session_state.checks += 1

# 📖 Журнал
if 'journal' not in st.session_state:
    st.session_state.journal = []

# 🌍 Фильтр сессий (07:00 - 21:00 UTC - расширен)
current_utc = datetime.now(timezone.utc)
is_active = 7 <= current_utc.hour <= 21
st.info(f"🌍 UTC: {current_utc.strftime('%H:%M')} | {'✅ Сессия активна' if is_active else '⏸️ Ожидание сессии'} | 🔍 Проверок: {st.session_state.checks}")

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
SYMBOLS = ["EUR/USD", "GBP/USD", "AUD/USD", "EUR/CHF"]

def get_data(sym, key):
    symbol_encoded = sym.replace("/", "%2F")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol_encoded}&interval=1min&outputsize=50&apikey={key}&_={random.randint(1000,9999)}"
    try:
        r = requests.get(url, timeout=12)
        data = r.json()
        if "values" not in data: return None, data.get("message", "Ошибка")
        df = pd.DataFrame(data["values"]).iloc[::-1].reset_index(drop=True)
        df["date"] = pd.to_datetime(df["datetime"], utc=True)
        for c in ["open", "high", "low", "close"]: df[c] = pd.to_numeric(df[c], errors="coerce")
        return df, None
    except Exception as e: return None, str(e)

def analyze(df):
    """Упрощённая стратегия: больше сигналов, меньше условий"""
    if len(df) < 15: return "⏳", "hold", None
    
    df["ema14"] = EMAIndicator(close=df["close"], window=14).ema_indicator()
    df["rsi14"] = RSIIndicator(close=df["close"], window=14).rsi()
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 🟢 CALL: RSI ниже 40 + цена выше EMA (бычий импульс после отката)
    if curr["rsi14"] < 40 and curr["close"] > curr["ema14"]:
        return "🟢 CALL", "call", curr["close"]
    # 🔴 PUT: RSI выше 60 + цена ниже EMA (медвежий импульс после отката)
    elif curr["rsi14"] > 60 and curr["close"] < curr["ema14"]:
        return "🔴 PUT", "put", curr["close"]
    # 🟡 WATCH: пограничные зоны
    elif 38 <= curr["rsi14"] <= 42 or 58 <= curr["rsi14"] <= 62:
        return "🟡 WATCH", "watch", curr["close"]
    
    return "⚪ HOLD", "hold", curr["close"]

def chart(df, sym):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema14"], line=dict(color="cyan", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi14"], line=dict(color="purple")), row=2, col=1)
    fig.add_hline(y=60, line_dash="dash", line_color="#ff9800", row=2, col=1)
    fig.add_hline(y=40, line_dash="dash", line_color="#ff9800", row=2, col=1)
    fig.update_layout(height=400, margin=dict(l=25,r=25,t=25,b=25), template="plotly_dark", showlegend=False, xaxis=dict(tickformat="%H:%M"))
    return fig

# 🔊 Звук
st.markdown("""<script>
(function(){
  let last = JSON.parse(localStorage.getItem('po_sigs') || '{}');
  let changed = false;
  document.querySelectorAll('[data-sig]').forEach(el => {
    let s = el.dataset.sym, v = el.dataset.sig;
    if(last[s] && last[s] !== v && !v.includes('HOLD') && !v.includes('watch')) changed = true;
    last[s] = v;
  });
  if(changed){ let snd = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg'); snd.volume=0.6; snd.play().catch(()=>{}); }
  localStorage.setItem('po_sigs', JSON.stringify(last));
})();
</script>""", unsafe_allow_html=True)

# 🖥️ UI
if st.button("🔄 Обновить"): st.rerun()

cols = st.columns(2)
for i, sym in enumerate(SYMBOLS):
    with cols[i % 2]:
        if not is_active:
            st.warning(f"⏸️ {sym}: Ожидание сессии")
            continue
        df, err = get_data(sym, api_key)
        if err: st.error(f"❌ {sym}: {err}"); continue
        
        sig_text, sig_class, price = analyze(df)
        last_time = df["date"].iloc[-1].strftime("%H:%M UTC")
        price_str = f"{price:.5f}" if price else "N/A"
        
        bg = {"call": "#00c853", "put": "#ff1744", "watch": "#ff9800", "hold": "#757575"}
        st.markdown(f'<div style="padding:15px;border-radius:10px;text-align:center;font-weight:bold;background:{bg.get(sig_class, "#757575")};color:white;margin:5px 0;" data-sym="{sym}" data-sig="{sig_class}">{sym}<br>{sig_text}<br>{price_str}<br><small style="opacity:0.8">Свеча: {last_time}</small></div>', unsafe_allow_html=True)
        st.plotly_chart(chart(df, sym), use_container_width=True)
        
        # 📖 Автожурнал
        if sig_class in ["call", "put"]:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if not st.session_state.journal or st.session_state.journal[-1]["time_utc"][:16] != now_str[:16]:
                st.session_state.journal.append({"time_utc": now_str, "pair": sym, "signal": sig_text, "price": price_str, "result": ""})

# 📊 Журнал
st.markdown("---")
st.subheader("📖 Журнал сделок")
if st.session_state.journal:
    df_j = pd.DataFrame(st.session_state.journal)
    st.data_editor(df_j, use_container_width=True, key="journal_edit", disabled=["time_utc","pair","signal","price"])
    csv = df_j.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Скачать CSV", csv, f"journal_{datetime.now().strftime('%d%m')}.csv", "text/csv")
else:
    st.info("Нет сигналов. Ожидайте 🟢/🔴 в активную сессию.")

st.caption("""
📌 **Стратегия (упрощённая):**
• 🟢 CALL: RSI(14) < 40 + цена > EMA(14)
• 🔴 PUT: RSI(14) > 60 + цена < EMA(14)
• ⏰ Сессия: 07:00–21:00 UTC (расширена)
• 🔊 Звук при 🟢/🔴
• 📊 Вносите `+` или `-` в журнал после сделки
• ⚠️ Демо: 50 сделок → статистика → решение
""")
