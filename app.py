import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import time
from datetime import datetime, timezone

st.set_page_config(page_title="PO Signals 5m", page_icon="🎯", layout="wide", initial_sidebar_state="collapsed")

# ⚡ Обновление каждые 60 секунд (экономит лимиты API)
st_autorefresh(interval=60000, limit=None, key="po_refresh")
st.title("🎯 PO Signals 5m (Только РЕАЛЬНЫЕ пары)")

# 🔊 Кнопка для разблокировки звука в браузере (ОБЯЗАТЕЛЬНО НАЖМИ ПЕРВЫМ!)
if st.button("🔊 Нажми здесь, чтобы разрешить звук"):
    st.markdown("""
    <script>
    let snd = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
    snd.volume = 0.7;
    snd.play().then(() => { alert('✅ Звук работает! Теперь бот будет пищать при сигналах.'); }).catch(e => alert('❌ Не удалось воспроизвести звук. Проверь настройки телефона.'));
    </script>
    """, unsafe_allow_html=True)

if 'journal' not in st.session_state: st.session_state.journal = []
if 'last_candle_min' not in st.session_state: st.session_state.last_candle_min = {}

current_utc = datetime.now(timezone.utc)
is_active = 7 <= current_utc.hour <= 21
st.info(f"🌍 UTC: {current_utc.strftime('%H:%M')} | {'✅ Активная сессия' if is_active else '⏸️ Ожидание сессии'}")

# 🔑 Ключ
if 'api_key' not in st.session_state: st.session_state.api_key = ''
new_key = st.text_input("🔑 Twelve Data API Key", type="password", value=st.session_state.api_key)
if new_key and new_key != st.session_state.api_key:
    st.session_state.api_key = new_key; st.rerun()
if not st.session_state.api_key: st.info("💡 Введите ключ → нажмите Enter."); st.stop()

api_key = st.session_state.api_key
# Только реальные пары с высокой ликвидностью
SYMBOLS = ["EUR/USD", "GBP/USD"]

def get_data(sym, key):
    # 🕒 Запрашиваем данные только если сменилась 5-минутная свеча
    now_min_5 = int(time.time() // 300) 
    if st.session_state.last_candle_min.get(sym) == now_min_5:
        return None, "CACHED"
        
    symbol_encoded = sym.replace("/", "%2F")
    # ⚠️ ВАЖНО: interval=5min
    url = f"https://api.twelvedata.com/time_series?symbol={symbol_encoded}&interval=5min&outputsize=30&apikey={key}"
    try:
        r = requests.get(url, timeout=12)
        data = r.json()
        if "values" not in data: return None, data.get("message", "Ошибка API")
        df = pd.DataFrame(data["values"]).iloc[::-1].reset_index(drop=True)
        df["date"] = pd.to_datetime(df["datetime"], utc=True)
        for c in ["open", "high", "low", "close"]: df[c] = pd.to_numeric(df[c], errors="coerce")
        st.session_state.last_candle_min[sym] = now_min_5
        return df, None
    except Exception as e: return None, str(e)

def analyze(df):
    if len(df) < 15: return "⏳", "hold", None
    # Индикаторы для 5-минутного графика
    df["ema14"] = EMAIndicator(close=df["close"], window=14).ema_indicator()
    df["rsi14"] = RSIIndicator(close=df["close"], window=14).rsi()
    curr, prev = df.iloc[-1], df.iloc[-2]
    
    # 🟢 CALL: Цена выше EMA14 (восходящий тренд), но RSI упал ниже 40 (локальный откат для входа)
    if curr["close"] > curr["ema14"] and curr["rsi14"] < 40:
        return "🟢 CALL", "call", curr["close"]
    # 🔴 PUT: Цена ниже EMA14 (нисходящий тренд), но RSI поднялся выше 60 (локальный откат для входа)
    elif curr["close"] < curr["ema14"] and curr["rsi14"] > 60:
        return "🔴 PUT", "put", curr["close"]
        
    return "⚪ HOLD", "hold", curr["close"]

def chart(df, sym):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema14"], line=dict(color="cyan", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi14"], line=dict(color="purple")), row=2, col=1)
    fig.add_hline(y=60, line_dash="dash", line_color="#ff9800", row=2, col=1)
    fig.add_hline(y=40, line_dash="dash", line_color="#ff9800", row=2, col=1)
    fig.update_layout(height=400, margin=dict(l=25,r=25,t=25,b=25), template="plotly_dark", showlegend=False)
    return fig

# 🔄 Фоновая проверка звука при сигнале
st.markdown("""<script>
(function(){
  let last = JSON.parse(localStorage.getItem('po_sigs') || '{}');
  let changed = false;
  document.querySelectorAll('[data-sig]').forEach(el => {
    let s = el.dataset.sym, v = el.dataset.sig;
    if(last[s] && last[s] !== v && v !== 'hold') changed = true;
    last[s] = v;
  });
  if(changed){ 
    let snd = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg'); 
    snd.volume = 0.7; 
    snd.play().catch(()=>{}); 
  }
  localStorage.setItem('po_sigs', JSON.stringify(last));
})();
</script>""", unsafe_allow_html=True)

if st.button("🔄 Обновить вручную"): st.rerun()

st.warning("⚠️ ВНИМАНИЕ: В Pocket Option выбирайте ТОЛЬКО реальные пары (без приставки OTC). Таймфрейм графика: 5 мин. Экспирация: 5 мин.")

cols = st.columns(2)
for i, sym in enumerate(SYMBOLS):
    with cols[i % 2]:
        if not is_active: st.warning(f"⏸️ {sym}: Ожидание сессии"); continue
        df, err = get_data(sym, api_key)
        if err == "CACHED": st.info(f"📦 {sym}: Ожидание закрытия 5-минутной свечи..."); continue
        if err: st.error(f"❌ {sym}: {err}"); continue
        
        sig_text, sig_class, price = analyze(df)
        last_time = df["date"].iloc[-1].strftime("%H:%M UTC")
        price_str = f"{price:.5f}" if price else "N/A"
        bg = {"call": "#00c853", "put": "#ff1744", "hold": "#757575"}
        
        st.markdown(f'<div style="padding:15px;border-radius:10px;text-align:center;font-weight:bold;background:{bg.get(sig_class, "#757575")};color:white;margin:5px 0;" data-sym="{sym}" data-sig="{sig_class}">{sym}<br>{sig_text}<br>{price_str}<br><small style="opacity:0.8">Свеча: {last_time}</small></div>', unsafe_allow_html=True)
        st.plotly_chart(chart(df, sym), use_container_width=True)

        if sig_class in ["call", "put"]:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if not st.session_state.journal or st.session_state.journal[-1]["time_utc"][:16] != now_str[:16]:
                st.session_state.journal.append({"time_utc": now_str, "pair": sym, "signal": sig_text, "price": price_str, "result": ""})

st.markdown("---")
st.subheader("📖 Журнал сделок (5 мин)")
if st.session_state.journal:
    df_j = pd.DataFrame(st.session_state.journal)
    st.data_editor(df_j, use_container_width=True, key="journal_edit", disabled=["time_utc","pair","signal","price"])
    csv = df_j.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Скачать CSV", csv, f"journal_5m_{datetime.now().strftime('%d%m')}.csv", "text/csv")
else: st.info("Нет сигналов. Ожидайте 🟢/🔴")
