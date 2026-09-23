"""
app.py
Taiwan Weather Live Dashboard — 台灣即時天氣觀測儀表板
中央氣象署 (CWA) O-A0003-001 即時氣象測站觀測 Web App
對應課程步驟：
- 步驟 11: Streamlit 入門 (Web App 介面)
- 步驟 12: 從 SQLite 資料庫讀取即時觀測資料 (SQL 查詢)
- 步驟 13: 縣市下拉選單與測站搜尋過濾
- 步驟 14: 繪製全台最高/最低氣溫 Top 10 與縣市平均長條圖 (Plotly)
- 步驟 15: 顯示全台 300+ 測站詳細觀測資料表格
- 步驟 16: 整合 Web App 關鍵指標卡與控制面板
- 步驟 17: 進階：台灣 300+ 測站即時互動地圖視覺化 (Folium + Streamlit)
- 步驟 18: 動態氣溫色階渲染與測站 Popup 詳細資訊卡
- 步驟 19: 完整成果展示 (Taiwan Weather Observation Dashboard)
- 步驟 20: 程式碼品質與防呆優化 (自訂 SQL 查詢、資料庫自動初始)
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

# 1. 頁面基本配置
st.set_page_config(
    page_title="Taiwan Weather Live | 台灣即時天氣觀測",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 提升介面現代感與視覺質感
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1E3A8A 0%, #0284C7 50%, #0D9488 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
    }
    .sub-header {
        color: #4B5563;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        text-align: center;
    }
    .legend-box {
        display: inline-block;
        width: 14px;
        height: 14px;
        margin-right: 6px;
        border-radius: 3px;
        vertical-align: middle;
    }
</style>
""", unsafe_allow_html=True)


# 2. 資料庫讀取函數 (使用快取避免重複讀取)
@st.cache_data(ttl=300)
def load_observation_data(db_path: str = DB_PATH) -> pd.DataFrame:
    """讀取 StationObservations 即時觀測資料表"""
    if not os.path.exists(db_path):
        if run_fetch_data:
            with st.spinner("資料庫初次建立中，正在連線氣象署下載最新即時觀測..."):
                run_fetch_data()
        else:
            return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    # 檢查表格是否存在
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='StationObservations';")
    if not cursor.fetchone():
        conn.close()
        if run_fetch_data:
            with st.spinner("表格初次建立中，正在連線氣象署下載最新即時觀測..."):
                run_fetch_data()
            conn = sqlite3.connect(db_path)
        else:
            return pd.DataFrame()

    query = """
        SELECT id, station_id, station_name, county, town, lat, lon,
               observed_at, temperature, humidity, wind_speed, weather,
               precipitation, daily_high, daily_low, created_at
        FROM StationObservations
        ORDER BY temperature DESC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_temperature_color(temp: float) -> str:
    """依據氣溫色階規範返回 HEX 顏色碼"""
    if temp < 15.0:
        return "#2B6CB0"  # 寒冷/偏涼 (深藍)
    elif 15.0 <= temp < 20.0:
        return "#3B82F6"  # 涼爽 (科技藍)
    elif 20.0 <= temp < 25.0:
        return "#10B981"  # 舒適 (翠綠)
    elif 25.0 <= temp < 30.0:
        return "#F59E0B"  # 溫暖/微熱 (琥珀黃)
    elif 30.0 <= temp < 35.0:
        return "#EF4444"  # 炎熱 (警戒紅)
    else:
        return "#991B1B"  # 極端酷熱 (赭紅)


# 3. 載入資料
df_all = load_observation_data()

# 側邊欄控制項 (Sidebar)
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/sun.png", width=110)
    st.markdown("### 🛠️ 儀表板控制面板")
    st.markdown("**AIoT_L3_CWA_HW1** · CWA O-A0003-001")
    
    st.markdown("---")
    
    # 重新擷取資料按鈕
    if st.button("🔄 立即連線氣象署更新資料", use_container_width=True):
        if run_fetch_data:
            with st.spinner("正在向中央氣象署抓取最新 O-A0003-001 資料..."):
                run_fetch_data()
                st.cache_data.clear()
                st.success("✅ 資料庫更新成功！")
                st.rerun()
        else:
            st.error("找不到 fetch_data 模組")

    st.markdown("---")
    
    # 縣市篩選器
    if not df_all.empty:
        all_counties = ["全部縣市"] + sorted([c for c in df_all["county"].dropna().unique().tolist() if c])
        selected_county = st.selectbox(
            "📍 選擇縣市過濾 (Filter by County)",
            options=all_counties,
            index=0,
            help="篩選特定縣市之測站清單與地圖顯示"
        )
        
        # 測站關鍵字快速搜尋
        search_kw = st.text_input(
            "🔍 搜尋測站名稱或鄉鎮",
            placeholder="例如：臺北、阿里山、玉山...",
            help="依測站名稱或鄉鎮關鍵字進行即時過濾"
        )
    else:
        selected_county = "全部縣市"
        search_kw = ""

    st.markdown("---")
    st.markdown("""
    **📚 課程重點涵蓋**：
    - CWA 即時測站 API (`O-A0003-001`)
    - JSON 巢狀結構與 300+ 測站座標解析
    - 異常值清洗（過濾 `-99` 缺測值）
    - SQLite `StationObservations` 表格設計
    - Plotly Top 10 高低溫排行榜
    - Folium 台灣 300+ 測站即時互動地圖
    - SQLite 後台 SQL 即時檢驗
    """)

# 主內容區塊 (Main Dashboard)
st.markdown('<div class="main-header">🌤️ Taiwan Weather Live Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">中央氣象署 (CWA) O-A0003-001 局屬與自動氣象站 · 全台 300+ 測站即時觀測儀表板</div>', unsafe_allow_html=True)

if df_all.empty:
    st.warning("⚠️ 目前資料庫為空，請點擊左側「🔄 立即連線氣象署更新資料」按鈕以擷取氣象觀測！")
    st.stop()

# 依縣市與搜尋關鍵字篩選資料
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

# 頂部關鍵指標 Cards
col1, col2, col3, col4, col5 = st.columns(5)
total_stations = len(df_filtered)
latest_time = df_all["observed_at"].iloc[0] if not df_all.empty else "未知"

if not df_filtered.empty:
    highest_row = df_filtered.loc[df_filtered["temperature"].idxmax()]
    lowest_row = df_filtered.loc[df_filtered["temperature"].idxmin()]
    avg_temp = round(df_filtered["temperature"].mean(), 1)
    avg_hum = round(df_filtered["humidity"].dropna().mean(), 1) if not df_filtered["humidity"].dropna().empty else None

    with col1:
        st.metric(label="📊 觀測測站數", value=f"{total_stations} 站", help=f"全台共 {len(df_all)} 站")
    with col2:
        st.metric(label="🔥 最高氣溫", value=f"{highest_row['temperature']} °C", delta=f"{highest_row['station_name']} ({highest_row['county']})")
    with col3:
        st.metric(label="❄️ 最低氣溫", value=f"{lowest_row['temperature']} °C", delta=f"{lowest_row['station_name']} ({lowest_row['county']})", delta_color="inverse")
    with col4:
        st.metric(label="🌡️ 平均氣溫", value=f"{avg_temp} °C")
    with col5:
        st.metric(label="💧 平均相對濕度", value=f"{avg_hum} %" if avg_hum else "無數據")

st.markdown("<br>", unsafe_allow_html=True)

# 頁籤分流：圖表與表格 / 台灣互動地圖 / 資料庫即時檢驗
tab_charts, tab_map, tab_db = st.tabs([
    "📊 全台氣溫排行與各縣市統計 (Charts & Table)",
    "🗺️ 台灣 300+ 測站即時互動地圖 (Interactive Map)",
    "🗄️ SQLite 資料庫即時檢驗 (SQL Query)"
])

# ----------------- Tab 1: 圖表與表格 -----------------
with tab_charts:
    st.subheader("📊 全台氣象測站即時高低溫排行榜與統計")
    
    col_chart_left, col_chart_right = st.columns(2)
    
    # 1. 最高溫 Top 10 測站長條圖
    with col_chart_left:
        st.markdown("**🔥 全台即時最高溫測站 Top 10**")
        top_hot = df_all.nlargest(10, "temperature").sort_values("temperature", ascending=True)
        top_hot["label"] = top_hot["station_name"] + " (" + top_hot["county"] + ")"
        
        fig_hot = px.bar(
            top_hot,
            x="temperature",
            y="label",
            orientation="h",
            text="temperature",
            labels={"temperature": "氣溫 (°C)", "label": "測站 (縣市)"},
            color="temperature",
            color_continuous_scale="Reds"
        )
        fig_hot.update_traces(texttemplate="%{text:.1f}°C", textposition="outside")
        fig_hot.update_layout(
            margin=dict(l=10, r=30, t=10, b=10),
            height=340,
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_hot, use_container_width=True)

    # 2. 最低溫 Top 10 測站長條圖
    with col_chart_right:
        st.markdown("**❄️ 全台即時最低溫測站 Top 10**")
        top_cold = df_all.nsmallest(10, "temperature").sort_values("temperature", ascending=False)
        top_cold["label"] = top_cold["station_name"] + " (" + top_cold["county"] + ")"
        
        fig_cold = px.bar(
            top_cold,
            x="temperature",
            y="label",
            orientation="h",
            text="temperature",
            labels={"temperature": "氣溫 (°C)", "label": "測站 (縣市)"},
            color="temperature",
            color_continuous_scale="Blues_r"
        )
        fig_cold.update_traces(texttemplate="%{text:.1f}°C", textposition="outside")
        fig_cold.update_layout(
            margin=dict(l=10, r=30, t=10, b=10),
            height=340,
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_cold, use_container_width=True)

    # 3. 各縣市平均氣溫比較長條圖
    st.markdown("---")
    st.markdown("**🏙️ 各縣市即時平均氣溫排行**")
    df_county_avg = df_all.groupby("county").agg(
        avg_temp=("temperature", "mean"),
        station_count=("station_id", "count")
    ).reset_index().sort_values("avg_temp", ascending=False)
    df_county_avg["avg_temp"] = df_county_avg["avg_temp"].round(1)

    fig_county = px.bar(
        df_county_avg,
        x="county",
        y="avg_temp",
        text="avg_temp",
        color="avg_temp",
        color_continuous_scale="Turbo",
        labels={"avg_temp": "平均氣溫 (°C)", "county": "縣市", "station_count": "測站數"}
    )
    fig_county.update_traces(texttemplate="%{text:.1f}°C", textposition="outside")
    fig_county.update_layout(
        margin=dict(l=10, r=10, t=20, b=20),
        height=320,
        coloraxis_showscale=False
    )
    st.plotly_chart(fig_county, use_container_width=True)

    # 4. 測站觀測明細數據表格
    st.markdown("---")
    st.markdown(f"**📋 測站詳細觀測數據列表 (目前顯示 {len(df_filtered)} 筆)**")
    
    df_table = df_filtered[[
        "station_id", "station_name", "county", "town", "temperature",
        "humidity", "wind_speed", "precipitation", "daily_high", "daily_low", "observed_at"
    ]].copy()
    
    df_table.rename(columns={
        "station_id": "測站編號",
        "station_name": "測站名稱",
        "county": "縣市",
        "town": "鄉鎮區",
        "temperature": "即時氣溫 (°C)",
        "humidity": "相對濕度 (%)",
        "wind_speed": "風速 (m/s)",
        "precipitation": "時雨量 (mm)",
        "daily_high": "當日最高溫 (°C)",
        "daily_low": "當日最低溫 (°C)",
        "observed_at": "觀測時間"
    }, inplace=True)
    
    st.dataframe(df_table, use_container_width=True, hide_index=True)


# ----------------- Tab 2: 台灣地圖視覺化 (Folium) -----------------
with tab_map:
    st.subheader(f"🗺️ 台灣 300+ 測站即時氣溫分佈互動地圖 ({selected_county})")
    st.markdown("地圖點位直接採用中央氣象署測站真實 **WGS84 GPS 座標**，圓點大小與顏色隨氣溫動態變化：")

    # 圖例展示
    st.markdown("""
    **氣溫色彩級距圖例**：
    <span class="legend-box" style="background:#2B6CB0;"></span> **< 15°C**（寒冷）&nbsp;&nbsp;&nbsp;
    <span class="legend-box" style="background:#3B82F6;"></span> **15 - 20°C**（涼爽）&nbsp;&nbsp;&nbsp;
    <span class="legend-box" style="background:#10B981;"></span> **20 - 25°C**（舒適）&nbsp;&nbsp;&nbsp;
    <span class="legend-box" style="background:#F59E0B;"></span> **25 - 30°C**（溫暖）&nbsp;&nbsp;&nbsp;
    <span class="legend-box" style="background:#EF4444;"></span> **30 - 35°C**（炎熱）&nbsp;&nbsp;&nbsp;
    <span class="legend-box" style="background:#991B1B;"></span> **> 35°C**（極端酷熱）
    """, unsafe_allow_html=True)

    # 地圖中心依據篩選結果動態計算
    if not df_filtered.empty and selected_county != "全部縣市":
        center_lat = df_filtered["lat"].mean()
        center_lon = df_filtered["lon"].mean()
        zoom_level = 10.0
    else:
        center_lat = 23.75
        center_lon = 120.95
        zoom_level = 7.4

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_level,
        tiles="OpenStreetMap",
        control_scale=True
    )

    # 繪製測站標記
    for _, row in df_filtered.iterrows():
        temp = row["temperature"]
        color = get_temperature_color(temp)
        st_name = row["station_name"]
        county_str = row["county"]
        town_str = row["town"] or ""
        hum = f"{row['humidity']}%" if pd.notnull(row["humidity"]) else "無"
        wind = f"{row['wind_speed']} m/s" if pd.notnull(row["wind_speed"]) else "無"
        rain = f"{row['precipitation']} mm" if pd.notnull(row["precipitation"]) else "0.0 mm"
        d_high = f"{row['daily_high']}°C" if pd.notnull(row["daily_high"]) else "無"
        d_low = f"{row['daily_low']}°C" if pd.notnull(row["daily_low"]) else "無"
        obs_t = str(row["observed_at"]).replace("T", " ")[:19]

        popup_html = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif; min-width:180px; padding:4px;">
            <div style="border-bottom:2px solid {color}; padding-bottom:4px; margin-bottom:6px;">
                <b style="font-size:1.1rem; color:#1E3A8A;">{st_name} 測站</b>
                <span style="font-size:0.85rem; color:#6B7280; margin-left:4px;">({county_str}{town_str})</span>
            </div>
            <div style="font-size:1.25rem; font-weight:700; color:{color}; margin-bottom:6px;">
                {temp} °C
            </div>
            <div style="font-size:0.85rem; line-height:1.5; color:#374151;">
                💧 <b>相對濕度</b>: {hum}<br/>
                💨 <b>即時風速</b>: {wind}<br/>
                🌧️ <b>時雨量</b>: {rain}<br/>
                📈 <b>今日極值</b>: {d_low} ~ {d_high}<br/>
                🕒 <b>觀測時間</b>: {obs_t}
            </div>
        </div>
        """

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=7,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{st_name} ({county_str}{town_str}): {temp}°C",
            color="#FFFFFF",
            weight=1.5,
            fill=True,
            fill_color=color,
            fill_opacity=0.88
        ).add_to(m)

    st_folium(m, width=950, height=560)


# ----------------- Tab 3: SQLite 即時查詢驗證 -----------------
with tab_db:
    st.subheader("🗄️ SQLite 資料庫結構與 SQL 查詢驗證")
    st.markdown("直接對 `data.db` 的 `StationObservations` 表格進行 SQL 查詢與統計分析：")

    col_sql1, col_sql2 = st.columns(2)
    
    with col_sql1:
        st.markdown("**1. 縣市分組統計 (GROUP BY county, 計算測站數與均溫)**")
        conn = sqlite3.connect(DB_PATH)
        df_sql_group = pd.read_sql_query("""
            SELECT county as 縣市,
                   COUNT(*) as 測站數量,
                   ROUND(AVG(temperature), 1) as 平均氣溫,
                   ROUND(MIN(temperature), 1) as 最低氣溫,
                   ROUND(MAX(temperature), 1) as 最高氣溫
            FROM StationObservations
            GROUP BY county
            ORDER BY 平均氣溫 DESC;
        """, conn)
        st.dataframe(df_sql_group, use_container_width=True, hide_index=True)
        conn.close()

    with col_sql2:
        st.markdown("**2. 全台測站氣溫前 15 名 (ORDER BY temperature DESC)**")
        conn = sqlite3.connect(DB_PATH)
        df_sql_top = pd.read_sql_query("""
            SELECT station_name as 測站名稱,
                   county as 縣市,
                   town as 鄉鎮,
                   temperature as 即時氣溫,
                   humidity as 濕度,
                   wind_speed as 風速,
                   observed_at as 觀測時間
            FROM StationObservations
            ORDER BY temperature DESC
            LIMIT 15;
        """, conn)
        st.dataframe(df_sql_top, use_container_width=True, hide_index=True)
        conn.close()

    # 自訂 SQL 查詢執行區
    st.markdown("---")
    st.markdown("**3. 自訂 SQL 查詢測試 (SQL Interactive Console)**")
    custom_query = st.text_area(
        "輸入欲執行的 SQL SELECT 語句：",
        value="SELECT station_name, county, temperature, humidity FROM StationObservations WHERE county='臺中市' ORDER BY temperature DESC LIMIT 10;",
        height=70
    )
    if st.button("執行 SQL 查詢"):
        try:
            if not custom_query.strip().lower().startswith("select"):
                st.error("基於安全考量，僅支援 SELECT 查詢語句！")
            else:
                conn = sqlite3.connect(DB_PATH)
                df_custom = pd.read_sql_query(custom_query, conn)
                conn.close()
                st.success(f"查詢成功，共回傳 {len(df_custom)} 筆紀錄：")
                st.dataframe(df_custom, use_container_width=True, hide_index=True)
        except Exception as err:
            st.error(f"SQL 執行失敗: {err}")

# 頁尾標註
st.markdown("---")
st.caption("AI 創新微課程 Taiwan Weather Live Dashboard · 資料來源：中央氣象署開放資料平台 (CWA OpenData O-A0003-001) · 煥哥與你一起用 AI 寫程式探索更大的世界！")
