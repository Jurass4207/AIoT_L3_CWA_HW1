"""
app.py
Taiwan Weather Forecast — 從氣象資料到互動式天氣預報應用
Streamlit 互動式 Web App 主程式
對應課程步驟：
- 步驟 11: Streamlit 入門 (Web App 介面)
- 步驟 12: 從 SQLite 資料庫讀取資料 (SQL 查詢)
- 步驟 13: 下拉選單選擇地區
- 步驟 14: 繪製一週最高與最低氣溫折線圖
- 步驟 15: 顯示清晰的一週資料表格
- 步驟 16: 整合 Web App 介面
- 步驟 17: 進階：台灣地圖視覺化 (Folium + Streamlit)
- 步驟 18: 選擇日期顯示動態氣象地圖
- 步驟 19: 完整成果展示 (Taiwan Weather Dashboard)
"""

import os
import sqlite3
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
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
    page_title="Taiwan Weather Forecast | 台灣天氣預報",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 提升介面美觀與質感
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
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
        padding: 16px;
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
def load_forecast_data(db_path: str = DB_PATH) -> pd.DataFrame:
    if not os.path.exists(db_path):
        if run_fetch_data:
            with st.spinner("資料庫初次建立中，正在連線氣象署下載最新預報..."):
                run_fetch_data()
        else:
            return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    query = """
        SELECT id, regionName, dataDate, minT, maxT, created_at 
        FROM TemperatureForecasts 
        ORDER BY dataDate ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# 3. 台灣主要分區及縣市代表座標 (供 Folium 地圖標記使用)
LOCATION_COORDS = {
    # 主要大分區 (依海報設計)
    "北部地區": {"lat": 25.04, "lon": 121.55},
    "中部地區": {"lat": 24.15, "lon": 120.68},
    "南部地區": {"lat": 22.99, "lon": 120.21},
    "東北部地區": {"lat": 24.75, "lon": 121.75},
    "東部地區": {"lat": 23.99, "lon": 121.60},
    "東南部地區": {"lat": 22.75, "lon": 121.15},
    "離島地區": {"lat": 23.57, "lon": 119.58},
    # 22 縣市代表座標
    "臺北市": {"lat": 25.0375, "lon": 121.5637},
    "新北市": {"lat": 25.0123, "lon": 121.4657},
    "基隆市": {"lat": 25.1322, "lon": 121.7410},
    "桃園市": {"lat": 24.9936, "lon": 121.3010},
    "新竹市": {"lat": 24.8138, "lon": 120.9675},
    "新竹縣": {"lat": 24.8387, "lon": 121.0177},
    "苗栗縣": {"lat": 24.5602, "lon": 120.8214},
    "臺中市": {"lat": 24.1625, "lon": 120.6477},
    "彰化縣": {"lat": 24.0816, "lon": 120.5385},
    "南投縣": {"lat": 23.9099, "lon": 120.6850},
    "雲林縣": {"lat": 23.7092, "lon": 120.4313},
    "嘉義市": {"lat": 23.4800, "lon": 120.4491},
    "嘉義縣": {"lat": 23.4518, "lon": 120.2559},
    "臺南市": {"lat": 22.9997, "lon": 120.2270},
    "高雄市": {"lat": 22.6273, "lon": 120.3014},
    "屏東縣": {"lat": 22.6761, "lon": 120.4885},
    "宜蘭縣": {"lat": 24.7570, "lon": 121.7530},
    "花蓮縣": {"lat": 23.9871, "lon": 121.6016},
    "臺東縣": {"lat": 22.7583, "lon": 121.1444},
    "澎湖縣": {"lat": 23.5711, "lon": 119.5793},
    "金門縣": {"lat": 24.4327, "lon": 118.3766},
    "連江縣": {"lat": 26.1505, "lon": 119.9499},
}


def get_temperature_color(avg_temp: float) -> str:
    """依照海報定義的溫度區間進行著色"""
    if avg_temp < 20.0:
        return "#3B82F6"  # 藍色 (< 20°C)
    elif 20.0 <= avg_temp < 25.0:
        return "#10B981"  # 綠色 (20 - 25°C)
    elif 25.0 <= avg_temp < 30.0:
        return "#F59E0B"  # 黃色/橙色 (25 - 30°C)
    else:
        return "#EF4444"  # 紅色 (> 30°C)


# 4. 主介面流程
df_all = load_forecast_data()

# 側邊欄控制項 (Sidebar)
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/sun.png", width=110)
    st.markdown("### 🛠️ 儀表板控制面板")
    st.markdown("**AIoT_L3_CWA_HW1** · AI 創新微課程")
    
    st.markdown("---")
    
    # 重新擷取資料按鈕
    if st.button("🔄 立即連線氣象署更新資料", use_container_width=True):
        if run_fetch_data:
            with st.spinner("正在向中央氣象署抓取最新資料..."):
                run_fetch_data()
                st.cache_data.clear()
                st.success("✅ 資料庫更新成功！")
                st.rerun()
        else:
            st.error("找不到 fetch_data 模組")

    st.markdown("---")
    
    # 地區下拉選單 (步驟 13)
    if not df_all.empty:
        all_regions = df_all["regionName"].unique().tolist()
        
        # 排序：優先呈現海報指定的大分區，接著為各縣市
        primary_regions = ["北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區", "離島地區"]
        available_primary = [r for r in primary_regions if r in all_regions]
        other_regions = [r for r in all_regions if r not in primary_regions]
        sorted_regions = available_primary + sorted(other_regions)
        
        default_index = sorted_regions.index("中部地區") if "中部地區" in sorted_regions else 0
        selected_region = st.selectbox(
            "📍 選擇預報地區 (Select Region)",
            options=sorted_regions,
            index=default_index,
            help="切換欲查看一週氣溫走勢與預報表格之地區"
        )
    else:
        selected_region = None

    st.markdown("---")
    st.markdown("""
    **📚 課程重點涵蓋**：
    - CWA API (F-D0047-091)
    - JSON 氣候資料解析
    - SQLite `TemperatureForecasts` 表格
    - Pandas 聚合分析
    - Streamlit 互動儀表板
    - Folium 互動地圖
    """)

# 主內容區塊 (Main Dashboard)
st.markdown('<div class="main-header">🌤️ Taiwan Weather Forecast</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">從氣象資料到互動式天氣預報應用 · 中央氣象署 (CWA) Open Data 實作</div>', unsafe_allow_html=True)

if df_all.empty:
    st.warning("⚠️ 目前資料庫為空，請點擊左側「🔄 立即連線氣象署更新資料」按鈕以擷取氣象預報！")
    st.stop()

# 篩選目前選取地區的一週資料
df_region = df_all[df_all["regionName"] == selected_region].sort_values("dataDate").copy()

# 頂部關鍵指標 Cards
col1, col2, col3, col4 = st.columns(4)
if not df_region.empty:
    today_row = df_region.iloc[0]
    min_week = df_region["minT"].min()
    max_week = df_region["maxT"].max()
    avg_week = round((df_region["minT"].mean() + df_region["maxT"].mean()) / 2, 1)

    with col1:
        st.metric(label=f"今日最高溫 ({selected_region})", value=f"{today_row['maxT']} °C", delta=f"{round(today_row['maxT'] - avg_week, 1)} °C vs 週均")
    with col2:
        st.metric(label=f"今日最低溫 ({selected_region})", value=f"{today_row['minT']} °C")
    with col3:
        st.metric(label="一週平均氣溫", value=f"{avg_week} °C")
    with col4:
        st.metric(label="一週極端溫差", value=f"{round(max_week - min_week, 1)} °C", help=f"最低 {min_week}°C ~ 最高 {max_week}°C")

st.markdown("<br>", unsafe_allow_html=True)

# 頁籤分流：折線圖與表格 / 台灣互動地圖 / 資料庫即時檢驗
tab_chart, tab_map, tab_db = st.tabs([
    "📈 一週氣溫走勢圖與表格 (Chart & Table)",
    "🗺️ 台灣地圖視覺化 (Interactive Map)",
    "🗄️ SQLite 資料庫即時驗證 (SQL Query)"
])

# ----------------- Tab 1: 折線圖與表格 -----------------
with tab_chart:
    st.subheader(f"📊 【{selected_region}】未來一週氣溫趨勢預報")
    
    col_chart, col_table = st.columns([3, 2])
    
    with col_chart:
        # 使用 Plotly 繪製符合海報視覺的平滑折線圖 (步驟 14)
        fig = go.Figure()
        
        # 最高溫線 (MaxT, 紅色)
        fig.add_trace(go.Scatter(
            x=df_region["dataDate"],
            y=df_region["maxT"],
            mode="lines+markers+text",
            name="最高氣溫 (MaxT)",
            text=[f"{v}°C" for v in df_region["maxT"]],
            textposition="top center",
            line=dict(color="#EF4444", width=3, shape="spline"),
            marker=dict(size=8, color="#DC2626")
        ))
        
        # 最低溫線 (MinT, 藍色)
        fig.add_trace(go.Scatter(
            x=df_region["dataDate"],
            y=df_region["minT"],
            mode="lines+markers+text",
            name="最低氣溫 (MinT)",
            text=[f"{v}°C" for v in df_region["minT"]],
            textposition="bottom center",
            line=dict(color="#3B82F6", width=3, shape="spline"),
            marker=dict(size=8, color="#2563EB")
        ))
        
        fig.update_layout(
            title=f"{selected_region} 一週最高與最低氣溫走勢",
            xaxis_title="預報日期 (Date)",
            yaxis_title="溫度 (°C)",
            yaxis=dict(range=[df_region["minT"].min() - 3, df_region["maxT"].max() + 4]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            margin=dict(l=20, r=20, t=50, b=20),
            height=380
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        # 顯示清晰的一週資料表格 (步驟 15)
        st.markdown(f"**📋 {selected_region} 每日詳細預報數據**")
        df_display = df_region[["dataDate", "minT", "maxT"]].copy()
        df_display["日溫差"] = (df_display["maxT"] - df_display["minT"]).round(1).astype(str) + " °C"
        df_display["minT"] = df_display["minT"].astype(str) + " °C"
        df_display["maxT"] = df_display["maxT"].astype(str) + " °C"
        df_display.rename(columns={
            "dataDate": "預報日期",
            "minT": "最低氣溫 (MinT)",
            "maxT": "最高氣溫 (MaxT)"
        }, inplace=True)
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)


# ----------------- Tab 2: 台灣地圖視覺化 (Folium) -----------------
with tab_map:
    st.subheader("🗺️ 台灣分區互動式氣象地圖 (Folium Map)")
    st.markdown("依據選擇之預報日期，將全台各分區／縣市之平均氣溫以不同色階標記呈現：")

    # 日期選擇器 (步驟 18)
    available_dates = sorted(df_all["dataDate"].unique().tolist())
    selected_date = st.selectbox("📅 選擇預報日期 (Select Date)", options=available_dates, index=0)

    # 圖例展示 (對應海報步驟 17 圖例)
    st.markdown("""
    **平均溫度色彩級距圖例**：
    <span class="legend-box" style="background:#3B82F6;"></span> **< 20°C**（寒冷/涼爽）&nbsp;&nbsp;&nbsp;
    <span class="legend-box" style="background:#10B981;"></span> **20 - 25°C**（舒適宜人）&nbsp;&nbsp;&nbsp;
    <span class="legend-box" style="background:#F59E0B;"></span> **25 - 30°C**（溫暖/微熱）&nbsp;&nbsp;&nbsp;
    <span class="legend-box" style="background:#EF4444;"></span> **> 30°C**（酷熱高溫）
    """, unsafe_allow_html=True)

    # 建立 Folium 地圖實例 (中心聚焦於台灣)
    m = folium.Map(
        location=[23.75, 120.95],
        zoom_start=7.3,
        tiles="OpenStreetMap",
        control_scale=True
    )

    # 篩選選定日期的全台預報資料
    df_date = df_all[df_all["dataDate"] == selected_date]

    # 在地圖上繪製測站/分區標記
    for _, row in df_date.iterrows():
        reg_name = row["regionName"]
        if reg_name in LOCATION_COORDS:
            coords = LOCATION_COORDS[reg_name]
            min_t = row["minT"]
            max_t = row["maxT"]
            avg_t = round((min_t + max_t) / 2, 1)
            marker_color = get_temperature_color(avg_t)

            popup_html = f"""
            <div style="font-family:sans-serif; min-width:130px;">
                <h4 style="margin:0 0 6px 0; color:#1E3A8A;">{reg_name}</h4>
                <b>預報日期</b>: {selected_date}<br/>
                <b>最低氣溫</b>: <span style="color:#2563EB;">{min_t} °C</span><br/>
                <b>最高氣溫</b>: <span style="color:#DC2626;">{max_t} °C</span><br/>
                <b>平均溫度</b>: <b>{avg_t} °C</b>
            </div>
            """

            folium.CircleMarker(
                location=[coords["lat"], coords["lon"]],
                radius=11 if "地區" in reg_name else 8,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{reg_name}: {avg_t}°C ({min_t}~{max_t}°C)",
                color="#FFFFFF",
                weight=2,
                fill=True,
                fill_color=marker_color,
                fill_opacity=0.88
            ).add_to(m)

    # 渲染至 Streamlit
    st_folium(m, width=950, height=520)


# ----------------- Tab 3: SQLite 即時查詢驗證 -----------------
with tab_db:
    st.subheader("🗄️ SQLite 資料庫結構與 SQL 查詢驗證")
    st.markdown("對應課程步驟 09 與步驟 10，直接對 `data.db` 進行 SQL 查詢檢驗：")

    col_sql1, col_sql2 = st.columns(2)
    
    with col_sql1:
        st.markdown("**1. 查詢所有不重複地區 (SELECT DISTINCT regionName)**")
        conn = sqlite3.connect(DB_PATH)
        distinct_df = pd.read_sql_query("SELECT DISTINCT regionName FROM TemperatureForecasts;", conn)
        st.dataframe(distinct_df, use_container_width=True)
        conn.close()

    with col_sql2:
        st.markdown(f"**2. 查詢當前選取地區原始資料 (WHERE regionName='{selected_region}')**")
        conn = sqlite3.connect(DB_PATH)
        sample_df = pd.read_sql_query(
            f"SELECT id, regionName, dataDate, minT, maxT, created_at FROM TemperatureForecasts WHERE regionName='{selected_region}' ORDER BY dataDate ASC;",
            conn
        )
        st.dataframe(sample_df, use_container_width=True)
        conn.close()

# 頁尾標註
st.markdown("---")
st.caption("AI 創新微課程 Taiwan Weather Forecast · 資料來源：中央氣象署開放資料平台 (CWA OpenData) · 煥哥與你一起用 AI 寫程式探索更大的世界！")
