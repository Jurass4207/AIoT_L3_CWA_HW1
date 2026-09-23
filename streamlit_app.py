"""
app.py
台灣即時氣象地圖 (Taiwan Live Weather Map) — 類 Windy 現代暗黑風格
設計參考：https://taiwan-weather-map.vercel.app/
資料來源：交通部中央氣象署 (CWA) O-A0003-001 局屬與自動氣象站實況
"""

import os
import sqlite3
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# 引入資料擷取模組
try:
    from fetch_data import main as run_fetch_data, DB_PATH
except ImportError:
    DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
    run_fetch_data = None

# 1. 頁面基本配置 (暗色現代風格)
st.set_page_config(
    page_title="台灣即時氣象地圖 | Taiwan Weather Map",
    page_icon="⛅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 注入精確復刻 taiwan-weather-map.vercel.app 之 CSS 樣式
st.markdown("""
<style>
    /* 全域暗色基調 */
    .stApp {
        background-color: #030712;
        color: #f3f4f6;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* 玻璃擬態控制面板 (bg-panel) */
    .bg-panel {
        background: rgba(17, 24, 39, 0.85);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }
    
    /* 頂部 Header 與標題 */
    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #38bdf8 0%, #0ea5e9 40%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }
    .hero-sub {
        font-size: 0.95rem;
        color: #9ca3af;
        margin-bottom: 20px;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 9999px;
        background: rgba(14, 165, 233, 0.15);
        border: 1px solid rgba(14, 165, 233, 0.35);
        color: #38bdf8;
        font-size: 0.8rem;
        font-weight: 500;
    }
    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 5px;
        background: #38bdf8;
        box-shadow: 0 0 8px #0ea5e9;
    }

    /* 指標卡片 (Metric Cards) */
    .metric-box {
        background: rgba(17, 24, 39, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
    .metric-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #9ca3af;
        margin-bottom: 4px;
    }
    .metric-val {
        font-size: 1.6rem;
        font-weight: 700;
        color: #f9fafb;
    }
    .metric-sub {
        font-size: 0.75rem;
        color: #6b7280;
        margin-top: 4px;
    }

    /* 圖例條樣式 (復刻 bottom-4 right-4 色彩進度條) */
    .weather-colorbar {
        background: rgba(17, 24, 39, 0.92);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 10px;
        padding: 12px 18px;
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.4);
        margin-top: 10px;
    }
    .colorbar-gradient {
        height: 10px;
        width: 100%;
        border-radius: 6px;
        background: linear-gradient(to right, #2c7bb6, #5aa2cf, #abd9e9, #7fcdbb, #d9ef8b, #fee08b, #fdae61, #f46d43, #d73027);
    }
    .colorbar-labels {
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        font-variant-numeric: tabular-nums;
        color: #9ca3af;
        margin-top: 5px;
    }

    /* Leaflet 容器暗黑模式覆蓋 */
    .leaflet-container {
        background: #0b1120 !important;
        font-family: inherit !important;
        border-radius: 10px;
    }
    .leaflet-container .leaflet-popup-content-wrapper,
    .leaflet-container .leaflet-popup-tip {
        background: rgba(17, 24, 39, 0.95) !important;
        color: #f3f4f6 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.6) !important;
        border-radius: 8px !important;
    }
    .leaflet-container .leaflet-popup-content {
        margin: 10px 14px !important;
        line-height: 1.5 !important;
        color: #f3f4f6 !important;
    }
    .leaflet-container .leaflet-popup-close-button {
        color: #9ca3af !important;
    }

    /* 氣溫數字膠囊標籤 (temp-label) */
    .temp-label {
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 28px;
        height: 18px;
        padding: 0 5px;
        border-radius: 9px;
        font-size: 11px;
        font-weight: 700;
        line-height: 1;
        white-space: nowrap;
        color: #ffffff;
        border: 1px solid rgba(0, 0, 0, 0.4);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.55);
        text-shadow: 0 0 2px rgba(0, 0, 0, 0.95), 0 1px 1px rgba(0, 0, 0, 0.7);
    }
</style>
""", unsafe_allow_html=True)


# 3. 讀取與快取資料庫資料
@st.cache_data(ttl=300)
def load_observation_data(db_path: str = DB_PATH) -> pd.DataFrame:
    """讀取 StationObservations 即時觀測資料表"""
    if not os.path.exists(db_path):
        if run_fetch_data:
            with st.spinner("正在連線氣象署下載最新觀測實況..."):
                run_fetch_data()
        else:
            return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='StationObservations';")
    if not cursor.fetchone():
        conn.close()
        if run_fetch_data:
            with st.spinner("正在連線氣象署建立測站資料庫..."):
                run_fetch_data()
            conn = sqlite3.connect(db_path)
        else:
            return pd.DataFrame()

    query = """
        SELECT s.id, s.station_id, s.station_name, s.county, s.town, s.lat, s.lon,
               s.observed_at, s.temperature, s.humidity, s.wind_speed, s.weather,
               s.precipitation, s.daily_high, s.daily_low, s.created_at
        FROM StationObservations s
        INNER JOIN (
            SELECT station_id, MAX(observed_at) as max_time
            FROM StationObservations
            GROUP BY station_id
        ) latest ON s.station_id = latest.station_id AND s.observed_at = latest.max_time
        ORDER BY s.temperature DESC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# 4. 色彩映射邏輯 (對齊 taiwan-weather-map 色階梯隊)
def get_weather_map_color(temp: float) -> str:
    """
    對應色階漸變：
    #2c7bb6 (5°C) -> #5aa2cf (10°C) -> #abd9e9 (15°C) -> #7fcdbb (20°C)
    -> #d9ef8b (24°C) -> #fee08b (28°C) -> #fdae61 (32°C) -> #f46d43 (36°C) -> #d73027 (>36°C)
    """
    if temp is None:
        return "#6b7280"
    if temp < 5.0:
        return "#2c7bb6"
    elif temp < 10.0:
        return "#5aa2cf"
    elif temp < 15.0:
        return "#abd9e9"
    elif temp < 20.0:
        return "#7fcdbb"
    elif temp < 24.0:
        return "#d9ef8b"
    elif temp < 28.0:
        return "#fee08b"
    elif temp < 32.0:
        return "#fdae61"
    elif temp < 36.0:
        return "#f46d43"
    else:
        return "#d73027"


# 載入測站資料
df_all = load_observation_data()

# ==================== 側邊欄控制面板 (復刻右側 Floating Panel 功能) ====================
with st.sidebar:
    st.markdown("### 🎛️ 氣象圖層與控制")
    st.caption("Taiwan Live Weather Map · CWA O-A0003-001")
    
    # 重新整理按鈕
    if st.button("🔄 立即同步最新觀測", use_container_width=True):
        if run_fetch_data:
            with st.spinner("正在連線中央氣象署抓取最新資料…"):
                run_fetch_data()
                st.cache_data.clear()
                st.success("✅ 即時觀測更新完成！")
                st.rerun()
        else:
            st.error("未找到 fetch_data 模組")

    st.markdown("---")
    
    # 圖層要素切換 (對齊網頁圖層按鈕)
    st.markdown("**觀測圖層 (Layer)**")
    selected_layer = st.radio(
        "選擇氣象指標",
        options=["🌡️ 氣溫 (°C)", "💧 濕度 (%)", "💨 風速 (m/s)", "🌧️ 雨量 (mm)"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("**地圖顯示模式 (Map Controls)**")
    
    # 標籤樣式選擇 (預設為經典發光圓點)
    marker_style = st.radio(
        "測站標記樣式",
        options=["● 經典發光圓點 (推薦)", "🏷️ 氣溫數字膠囊"],
        index=0,
        horizontal=True
    )
    show_labels = (marker_style == "🏷️ 氣溫數字膠囊")
    
    # 底圖切換 (深色採用無浮水印之 Esri Dark Canvas)
    basemap_choice = st.radio(
        "底圖模式 (Basemap)",
        options=["深色 (Esri Dark Canvas)", "街道圖 (OpenStreetMap)"],
        index=0,
        horizontal=True
    )

    st.markdown("---")
    st.markdown("**區域過濾與搜尋 (Filters)**")
    
    # 縣市篩選
    if not df_all.empty:
        all_counties = ["全部縣市"] + sorted([c for c in df_all["county"].dropna().unique().tolist() if c])
        selected_county = st.selectbox(
            "📍 選擇縣市",
            options=all_counties,
            index=0
        )
        
        # 測站搜尋
        search_kw = st.text_input(
            "🔍 搜尋測站或鄉鎮",
            placeholder="例如：臺北、玉山、日月潭..."
        )
    else:
        selected_county = "全部縣市"
        search_kw = ""

    st.markdown("---")
    st.markdown("""
    <div style="font-size:0.8rem; color:#6b7280; line-height:1.6;">
        <b>資料來源</b>：交通部中央氣象署 (CWA)<br/>
        <b>開放資料集</b>：<code>O-A0003-001</code><br/>
        <b>更新週期</b>：自動測站約每 10 分鐘同步一次
    </div>
    """, unsafe_allow_html=True)


# ==================== 主頁面視圖 ====================
# 頂部 Hero 區域
col_hero_left, col_hero_right = st.columns([3, 1])
with col_hero_left:
    st.markdown('<div class="hero-title">台灣即時氣象地圖</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">中央氣象署開放資料即時視覺化地圖（類 Windy 暗黑動態風格）</div>', unsafe_allow_html=True)

with col_hero_right:
    latest_time_str = df_all["observed_at"].iloc[0].replace("T", " ")[:16] if not df_all.empty else "取得中"
    st.markdown(f"""
    <div style="text-align:right; padding-top:10px;">
        <span class="status-badge"><span class="status-dot"></span> 即時連線正常</span>
        <div style="font-size:0.75rem; color:#9ca3af; margin-top:5px;">觀測時間：{latest_time_str}</div>
    </div>
    """, unsafe_allow_html=True)

if df_all.empty:
    st.warning("⚠️ 尚無測站觀測資料，請點擊左側「🔄 立即同步最新觀測」以載入資料！")
    st.stop()

# 資料過濾處理
df_filtered = df_all.copy()
if selected_county != "全部縣市":
    df_filtered = df_filtered[df_filtered["county"] == selected_county]
if search_kw.strip():
    kw = search_kw.strip()
    df_filtered = df_filtered[
        df_filtered["station_name"].str.contains(kw, na=False) |
        df_filtered["town"].str.contains(kw, na=False) |
        df_filtered["county"].str.contains(kw, na=False)
    ]

# 頂部關鍵氣象指標 Cards
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-label">📍 有效測站數</div>
        <div class="metric-val">{len(df_filtered)} <span style="font-size:0.9rem; font-weight:normal; color:#9ca3af;">/ {len(df_all)} 站</span></div>
        <div class="metric-sub">{selected_county}</div>
    </div>
    """, unsafe_allow_html=True)

if not df_filtered.empty:
    h_row = df_filtered.loc[df_filtered["temperature"].idxmax()]
    l_row = df_filtered.loc[df_filtered["temperature"].idxmin()]
    avg_t = round(df_filtered["temperature"].mean(), 1)
    avg_h = round(df_filtered["humidity"].dropna().mean(), 1) if not df_filtered["humidity"].dropna().empty else None

    with c2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">🔥 最高氣溫</div>
            <div class="metric-val" style="color:#f87171;">{h_row['temperature']} °C</div>
            <div class="metric-sub">{h_row['station_name']} ({h_row['county']})</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">❄️ 最低氣溫</div>
            <div class="metric-val" style="color:#60a5fa;">{l_row['temperature']} °C</div>
            <div class="metric-sub">{l_row['station_name']} ({l_row['county']})</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">🌡️ 平均氣溫</div>
            <div class="metric-val" style="color:#38bdf8;">{avg_t} °C</div>
            <div class="metric-sub">全區域均值</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">💧 平均相對濕度</div>
            <div class="metric-val" style="color:#34d399;">{avg_h} %</div>
            <div class="metric-sub">地面濕度概況</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 頁籤切換：互動地圖 (置頂主打) / 排行榜與統計圖表 / SQL 資料庫檢驗
tab_map, tab_charts, tab_db = st.tabs([
    "🗺️ 即時氣象互動地圖 (Live Map)",
    "📊 全台高低溫排行與統計 (Rankings & Charts)",
    "🗄️ SQLite 即時資料庫檢驗 (SQL Console)"
])

# ==================== Tab 1: 台灣即時氣象地圖 ====================
with tab_map:
    # 決定地圖視角中心
    if not df_filtered.empty and selected_county != "全部縣市":
        center_lat = df_filtered["lat"].mean()
        center_lon = df_filtered["lon"].mean()
        zoom_level = 10.0
    else:
        center_lat = 23.75
        center_lon = 120.95
        zoom_level = 7.5

    # 決定底圖樣式 (使用完全無浮水印的暗黑圖磚)
    if basemap_choice.startswith("深色"):
        tiles_url = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        tiles_attr = "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ"
    else:
        tiles_url = "OpenStreetMap"
        tiles_attr = None

    if tiles_attr:
        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, tiles=tiles_url, attr=tiles_attr, control_scale=True)
    else:
        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, tiles=tiles_url, control_scale=True)

    # 繪製測站點位
    for _, row in df_filtered.iterrows():
        temp = row["temperature"]
        color = get_weather_map_color(temp)
        st_name = row["station_name"]
        county_str = row["county"]
        town_str = row["town"] or ""
        hum = f"{row['humidity']}%" if pd.notnull(row["humidity"]) else "無數據"
        wind = f"{row['wind_speed']} m/s" if pd.notnull(row["wind_speed"]) else "無數據"
        rain = f"{row['precipitation']} mm" if pd.notnull(row["precipitation"]) else "0.0 mm"
        d_high = f"{row['daily_high']}°C" if pd.notnull(row["daily_high"]) else "無"
        d_low = f"{row['daily_low']}°C" if pd.notnull(row["daily_low"]) else "無"
        obs_t = str(row["observed_at"]).replace("T", " ")[:19]

        popup_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; min-width: 190px; color:#f3f4f6;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.12); padding-bottom:6px; margin-bottom:8px;">
                <b style="font-size:1.15rem; color:#f9fafb;">{st_name} 測站</b>
                <span style="font-size:0.75rem; background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px; color:#9ca3af;">{county_str}{town_str}</span>
            </div>
            <div style="display:flex; align-items:baseline; gap:8px; margin-bottom:8px;">
                <span style="font-size:1.8rem; font-weight:800; color:{color}; line-height:1;">{temp}</span>
                <span style="font-size:1.1rem; color:{color}; font-weight:600;">°C</span>
                <span style="font-size:0.8rem; color:#9ca3af; margin-left:auto;">{row.get('weather', '實測')}</span>
            </div>
            <div style="font-size:0.82rem; line-height:1.6; color:#d1d5db;">
                <div>💧 <b>相對濕度</b>：<span style="color:#38bdf8;">{hum}</span></div>
                <div>💨 <b>即時風速</b>：<span style="color:#34d399;">{wind}</span></div>
                <div>🌧️ <b>時雨量</b>：<span style="color:#60a5fa;">{rain}</span></div>
                <div>📈 <b>今日極值</b>：<span style="color:#f59e0b;">{d_low} ~ {d_high}</span></div>
                <div style="font-size:0.72rem; color:#6b7280; margin-top:4px;">🕒 觀測時間：{obs_t}</div>
            </div>
        </div>
        """

        if show_labels:
            # 膠囊數字標籤模式 (temp-label)
            icon_html = f'<div class="temp-label" style="background:{color};">{temp}</div>'
            folium.Marker(
                location=[row["lat"], row["lon"]],
                icon=folium.DivIcon(
                    html=icon_html,
                    icon_size=(32, 18),
                    icon_anchor=(16, 9)
                ),
                popup=folium.Popup(popup_html, max_width=290),
                tooltip=f"{st_name} ({county_str}{town_str}): {temp}°C"
            ).add_to(m)
        else:
            # 圓形發光標記模式 (CircleMarker)
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=7.5,
                popup=folium.Popup(popup_html, max_width=290),
                tooltip=f"{st_name} ({county_str}{town_str}): {temp}°C",
                color="#ffffff",
                weight=1.5,
                fill=True,
                fill_color=color,
                fill_opacity=0.88
            ).add_to(m)

    # 渲染 Folium 地圖
    st_folium(m, width=950, height=580)

    # 底部漸變色階進度條 (復刻 target web 右下角圖例)
    st.markdown("""
    <div class="weather-colorbar">
        <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:12px; font-weight:700; color:#f3f4f6;">°C</span>
            <div style="flex:1;">
                <div class="colorbar-gradient"></div>
                <div class="colorbar-labels">
                    <span>5</span>
                    <span>10</span>
                    <span>15</span>
                    <span>20</span>
                    <span>24</span>
                    <span>28</span>
                    <span>32</span>
                    <span>36</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ==================== Tab 2: 氣溫排行與各縣市統計 ====================
with tab_charts:
    st.markdown("### 📊 全台氣溫極值排行與縣市均溫統計")
    
    col_chart_l, col_chart_r = st.columns(2)
    
    # 1. 最高溫 Top 10
    with col_chart_l:
        st.markdown("**🔥 全台即時最高溫測站 Top 10**")
        top_hot = df_all.nlargest(10, "temperature").sort_values("temperature", ascending=True)
        top_hot["label"] = top_hot["station_name"] + " (" + top_hot["county"] + ")"
        
        fig_hot = px.bar(
            top_hot,
            x="temperature",
            y="label",
            orientation="h",
            text="temperature",
            color="temperature",
            color_continuous_scale=[[0, "#fdae61"], [0.5, "#f46d43"], [1.0, "#d73027"]],
            labels={"temperature": "氣溫 (°C)", "label": "測站"}
        )
        fig_hot.update_traces(texttemplate="%{text:.1f}°C", textposition="outside", textfont=dict(color="#f3f4f6"))
        fig_hot.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=30, t=10, b=10),
            height=340,
            coloraxis_showscale=False,
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
            yaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig_hot, use_container_width=True)

    # 2. 最低溫 Top 10
    with col_chart_r:
        st.markdown("**❄️ 全台即時最低溫測站 Top 10**")
        top_cold = df_all.nsmallest(10, "temperature").sort_values("temperature", ascending=False)
        top_cold["label"] = top_cold["station_name"] + " (" + top_cold["county"] + ")"
        
        fig_cold = px.bar(
            top_cold,
            x="temperature",
            y="label",
            orientation="h",
            text="temperature",
            color="temperature",
            color_continuous_scale=[[0, "#2c7bb6"], [0.5, "#5aa2cf"], [1.0, "#abd9e9"]],
            labels={"temperature": "氣溫 (°C)", "label": "測站"}
        )
        fig_cold.update_traces(texttemplate="%{text:.1f}°C", textposition="outside", textfont=dict(color="#f3f4f6"))
        fig_cold.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=30, t=10, b=10),
            height=340,
            coloraxis_showscale=False,
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
            yaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig_cold, use_container_width=True)

    # 3. 各縣市均溫比較圖
    st.markdown("---")
    st.markdown("**🏙️ 各縣市即時平均氣溫柱狀比較**")
    df_c_avg = df_all.groupby("county").agg(
        avg_temp=("temperature", "mean"),
        count=("station_id", "count")
    ).reset_index().sort_values("avg_temp", ascending=False)
    df_c_avg["avg_temp"] = df_c_avg["avg_temp"].round(1)

    fig_county = px.bar(
        df_c_avg,
        x="county",
        y="avg_temp",
        text="avg_temp",
        color="avg_temp",
        color_continuous_scale=[
            [0.0, "#2c7bb6"], [0.25, "#7fcdbb"], [0.5, "#fee08b"], [0.75, "#fdae61"], [1.0, "#d73027"]
        ],
        labels={"avg_temp": "平均氣溫 (°C)", "county": "縣市", "count": "測站數量"}
    )
    fig_county.update_traces(texttemplate="%{text:.1f}°C", textposition="outside", textfont=dict(color="#f3f4f6"))
    fig_county.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=20, b=20),
        height=320,
        coloraxis_showscale=False,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
    )
    st.plotly_chart(fig_county, use_container_width=True)

    # 4. 測站明細表格
    st.markdown("---")
    st.markdown(f"**📋 測站詳細觀測數據列表 ({len(df_filtered)} 站)**")
    
    df_display = df_filtered[[
        "station_id", "station_name", "county", "town", "temperature",
        "humidity", "wind_speed", "precipitation", "daily_high", "daily_low", "observed_at"
    ]].copy()
    
    df_display.rename(columns={
        "station_id": "測站編號",
        "station_name": "測站名稱",
        "county": "縣市",
        "town": "鄉鎮區",
        "temperature": "氣溫 (°C)",
        "humidity": "濕度 (%)",
        "wind_speed": "風速 (m/s)",
        "precipitation": "雨量 (mm)",
        "daily_high": "當日高溫 (°C)",
        "daily_low": "當日低溫 (°C)",
        "observed_at": "觀測時間"
    }, inplace=True)
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)


# ==================== Tab 3: SQLite 即時資料庫檢驗 ====================
with tab_db:
    st.markdown("### 🗄️ SQLite 即時資料庫結構與 SQL 查詢")
    st.markdown("直連 `data.db` 之後台 `StationObservations` 表格，檢驗資料清洗與聚合分析：")

    col_q1, col_q2 = st.columns(2)
    
    with col_q1:
        st.markdown("**1. 各縣市測站數與氣溫極值統計 (GROUP BY county)**")
        conn = sqlite3.connect(DB_PATH)
        df_group = pd.read_sql_query("""
            SELECT county as 縣市,
                   COUNT(*) as 測站總數,
                   ROUND(AVG(temperature), 1) as 平均氣溫,
                   ROUND(MIN(temperature), 1) as 最低氣溫,
                   ROUND(MAX(temperature), 1) as 最高氣溫
            FROM StationObservations
            GROUP BY county
            ORDER BY 平均氣溫 DESC;
        """, conn)
        st.dataframe(df_group, use_container_width=True, hide_index=True)
        conn.close()

    with col_q2:
        st.markdown("**2. 全台測站高溫 Top 15 原始記錄**")
        conn = sqlite3.connect(DB_PATH)
        df_top15 = pd.read_sql_query("""
            SELECT station_name as 測站,
                   county as 縣市,
                   town as 鄉鎮,
                   temperature as 氣溫,
                   humidity as 濕度,
                   wind_speed as 風速,
                   observed_at as 觀測時間
            FROM StationObservations
            ORDER BY temperature DESC
            LIMIT 15;
        """, conn)
        st.dataframe(df_top15, use_container_width=True, hide_index=True)
        conn.close()

    st.markdown("---")
    st.markdown("**3. 互動式 SQL 查詢測試 (SQL Interactive Console)**")
    sql_input = st.text_area(
        "輸入欲執行的 SQL SELECT 語句：",
        value="SELECT station_name, county, temperature, humidity, wind_speed FROM StationObservations WHERE county='臺北市' ORDER BY temperature DESC;",
        height=70
    )
    if st.button("執行 SQL 語句"):
        try:
            if not sql_input.strip().lower().startswith("select"):
                st.error("基於安全原則，僅支援 SELECT 讀取語句！")
            else:
                conn = sqlite3.connect(DB_PATH)
                res_df = pd.read_sql_query(sql_input, conn)
                conn.close()
                st.success(f"查詢成功，共回傳 {len(res_df)} 筆紀錄：")
                st.dataframe(res_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"SQL 查詢失敗: {e}")

# 頁尾資訊
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#6b7280; font-size:0.8rem; padding:10px 0;">
    台灣即時氣象地圖 · 類 Windy 現代暗黑風格 · 資料來源：中央氣象署開放資料平台 (CWA OpenData O-A0003-001)
</div>
""", unsafe_allow_html=True)
