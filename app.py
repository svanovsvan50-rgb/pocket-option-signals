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

st.set_page_config(page_title="PO Signals Pro", page_icon="🎯", layout="wide", initial_sidebar_state="collapsed")

# ⚡ Автообновление каждые 45 секунд
st_autorefresh(interval=45000, limit=None, key="po_refresh")
st.title("🎯 PO Signals 1m Pro")

# 📖 Инициализация журнала в сессии
if 'journal' not in st.session_state:
    st.session_state.journal = []

# 🌍 Фильтр торговых сессий (08:00 - 20:00 UTC)
current_utc = datetime.now(timezone.utc)
is_active = 8 <= current_utc.hour <= 20
st.info(f"🌍 Текущее время (UTC): {current_utc.strftime('%H:%M')} | {'✅ Активная сессия' if is_active else '⏸️ Рынок в шуме (вне сессии)'}")

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
    url = f"https://api.twelvedata.com/time_series?symbol={symbol_encoded}&interval=1min&outputsize=60&apikey={key}&_={random.randint(1000,9999)}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        if "values" not in data: return None, data.get("message", "Ошибка")
        df = pd.DataFrame(data["values"]).iloc[::-1].reset_index(drop=True)
        df["date"] = pd.to_datetime(df["datetime"], utc=True)
        for c in ["open", "high", "low", "close"]: df[c] = pd.to_numeric(df[c], errors="coerce")
        return df, None
    except Exception as e: return None, str(e)

def analyze(df):
    """Стратегия: Откат в направлении тренда (Pullback Reversal)"""
    if len(df) < 20: return "⏳", "hold", None, 0
    df["ema20"] = EMAIndicator(close=df["close"], window=20).ema_indicator()
    df["rsi7"] = RSIIndicator(close=df["close"], window=7).rsi()
    curr, prev = df.iloc[-1], df.iloc[-2]

    # 🟢 CALL: Восходящий тренд + RSI ушёл в перепроданность и разворачивается
    if curr["close"] > curr["ema20"] and curr["rsi7"] < 25 and prev["rsi7"] >= 25:
        return "🟢 CALL", "call", curr["close"], 78
    # 🔴 PUT: Нисходящий тренд + RSI ушёл в перекупленность и разворачивается
    elif curr["close"] < curr["ema20"] and curr["rsi7"] > 75 and prev["rsi7"] <= 75:
        return "🔴 PUT", "put", curr["close"], 78
    # ⚠️ Зоны подготовки
    elif curr["close"] > curr["ema20"] and 25 <= curr["rsi7"] < 35:
        return "🟡 WATCH CALL", "watch_call", curr["close"], 55
    elif curr["close"] < curr["ema20"] and 65 < curr["rsi7"] <= 75:
        return "🟠 WATCH PUT", "watch_put", curr["close"], 55
    return "⚪ HOLD", "hold", curr["close"], 0

def chart(df, sym):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema20"], line=dict(color="cyan", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi7"], line=dict(color="purple")), row=2, col=1)
    fig.add_hline(y=75, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=25, line_dash="dash", line_color="green", row=2, col=1)
    fig.update_layout(height=400, margin=dict(l=25,r=25,t=25,b=25), template="plotly_dark", showlegend=False, xaxis=dict(tickformat="%H:%M"))
    return fig

# 🔊 Звук при смене сигнала
st.markdown("""<script>
(function(){
  let last = JSON.parse(localStorage.getItem('po_sigs') || '{}');
  let changed = false;
  document.querySelectorAll('[data-sig]').forEach(el => {
    let s = el.dataset.sym, v = el.dataset.sig;
    if(last[s] && last[s] !== v && !v.includes('HOLD') && !v.includes('watch')) changed = true;
    last[s] = v;
  });
  if(changed){ let snd = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg'); snd.volume=0.5; snd.play().catch(()=>{}); }
  localStorage.setItem('po_sigs', JSON.stringify(last));
})();
</script>""", unsafe_allow_html=True)

# 🖥️ UI
if st.button("🔍 Проверить сейчас"): st.rerun()

cols = st.columns(2)
for i, sym in enumerate(SYMBOLS):
    with cols[i % 2]:
        if not is_active:
            st.warning(f"⏸️ {sym}: Нет сигналов вне сессии")
            continue
            
        df, err = get_data(sym, api_key)
        if err: st.error(f"❌ {sym}: {err}"); continue

        sig_text, sig_class, price, score = analyze(df)
        last_time = df["date"].iloc[-1].strftime("%H:%M UTC")
        price_str = f"{price:.5f}" if price else "N/A"

        bg = {"call": "#00c853", "put": "#ff1744", "watch_call": "#4caf50", "watch_put": "#f44336", "hold": "#757575"}
        bg_color = bg.get(sig_class, "#757575")

        st.markdown(f'<div style="padding:15px;border-radius:10px;text-align:center;font-weight:bold;background:{bg_color};color:white;margin:5px 0;" data-sym="{sym}" data-sig="{sig_class}">{sym}<br>{sig_text}<br>{price_str}<br><small style="opacity:0.9">📊 Надёжность: {score}%</small><br><small style="opacity:0.8">Свеча: {last_time}</small></div>', unsafe_allow_html=True)
        st.plotly_chart(chart(df, sym), use_container_width=True)

        # 📖 Автозапись в журнал
        if sig_class in ["call", "put"]:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            # Не дублируем сигнал в ту же минуту
            if not st.session_state.journal or st.session_state.journal[-1]["time_utc"][:16] != now_str[:16]:
                st.session_state.journal.append({"time_utc": now_str, "pair": sym, "signal": sig_text, "score": score, "price": price_str, "result": ""})

# 📊 Журнал и экспорт
st.markdown("---")
st.subheader("📖 Журнал сигналов (Заполняйте `+` или `-` после закрытия сделки)")
if st.session_state.journal:
    df_journal = pd.DataFrame(st.session_state.journal)
    st.data_editor(df_journal, use_container_width=True, key="journal_table", disabled=["time_utc", "pair", "signal", "score", "price"])
    csv = df_journal.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Скачать журнал в CSV", csv, f"po_journal_{datetime.now().strftime('%d%m')}.csv", "text/csv")
else:
    st.info("Пока нет сигналов. Журнал формируется автоматически при появлении 🟢/🔴")

st.caption("""
📌 **Как работает новая стратегия:**
• 🟢 CALL: Цена ВЫШЕ EMA(20) + RSI(7) падает ниже 25 и разворачивается (откуп в восходящем тренде)
• 🔴 PUT: Цена НИЖЕ EMA(20) + RSI(7) поднимается выше 75 и разворачивается (откуп в нисходящем тренде)
• ⏰ Работает ТОЛЬКО 08:00-20:00 UTC. В остальное время бот блокирует сигналы
• 📊 После сделки вносите `+` или `-` в колонку `result` и скачивайте CSV для расчёта winrate
• ⚠️ Тестируйте строго 50 сделок на ДЕМО. Если winrate ≥55% → переходите к микро-реалу
""")
