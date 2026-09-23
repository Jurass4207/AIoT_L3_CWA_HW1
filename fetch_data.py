"""
fetch_data.py
中央氣象署 (CWA) O-A0003-001 即時氣象測站觀測資料擷取與 SQLite 資料庫存儲程式
對應課程步驟：
- 步驟 03: 中央氣象署 CWA Open Data 平台 (API Key)
- 步驟 04: API 資料取得 (HTTP Requests)
- 步驟 05: JSON 資料結構解析 (O-A0003-001 即時觀測)
- 步驟 06: 提取測站座標、即時氣溫與各項氣象要素
- 步驟 07: 資料清洗與數值常理驗證 (過濾 -99 缺測與異常值)
- 步驟 08: 建立 SQLite 資料庫 (data.db)
- 步驟 09: 資料庫設計 (StationObservations 表格，防重複插入)
- 步驟 10: 查詢資料驗證 (SQL 統計分析與極值檢驗)
- 步驟 20: 程式碼品質與優化 (例外處理、結構模組化、.env 配置)
"""

import os
import sys
import ssl
import json
import sqlite3
import urllib.request
from datetime import datetime
import pandas as pd

# 解決 Windows 主控台 cp950 編碼無法輸出 Emoji/UTF-8 字元問題
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 自動讀取專案目錄下的 .env 檔案 (若存在)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# 1. 氣象署 API 設定
CWA_API_KEY = os.getenv("CWA_API_KEY", "CWA-4078E566-C632-4356-8C9F-D1B4AE74E894")
DATASET_ID = "O-A0003-001"  # 局屬氣象站-現在天氣觀測報告 (即時測站觀測實況)
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")


def _clean_float(val, min_val=None, max_val=None):
    """輔助函式：安全轉換浮點數，過濾特殊缺測字串與超出合理範圍的值"""
    if val is None:
        return None
    val_str = str(val).strip()
    if val_str in ("", "X", "NA", "null", "-99", "-999", "-99.0", "-999.0"):
        return None
    try:
        f = float(val_str)
        if min_val is not None and f < min_val:
            return None
        if max_val is not None and f > max_val:
            return None
        return round(f, 1)
    except (ValueError, TypeError):
        return None


def fetch_cwa_observations(api_key: str = CWA_API_KEY) -> dict:
    """呼叫中央氣象署 OpenData API 取得 O-A0003-001 即時氣象測站觀測 JSON 資料"""
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{DATASET_ID}?Authorization={api_key}"
    print(f"📡 正在向中央氣象署請求即時觀測資料集 ({DATASET_ID})...")

    # 建立 SSL 上下文 (解決 Windows 平台憑證鏈問題)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CWA-Weather-Observation-App/2.0"}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
        if response.status != 200:
            raise ConnectionError(f"CWA API 回應錯誤，狀態碼: {response.status}")
        raw_data = response.read().decode("utf-8")
        data = json.loads(raw_data)
        if not data.get("success"):
            raise ValueError(f"CWA API 回傳失敗訊息: {data}")
        print("✅ 成功獲取中央氣象署即時觀測資料！")
        return data


def parse_station_observations(json_data: dict) -> list[dict]:
    """
    解析 O-A0003-001 JSON 結構，過濾無效值，提取全台 300+ 測站真實經緯度與即時氣溫
    """
    records = json_data.get("records", {})
    stations = records.get("Station", [])
    if not stations:
        raise ValueError("氣象資料中未找到 Station 欄位")

    cleaned_records = []
    skipped_count = 0

    for st in stations:
        station_id = st.get("StationId")
        station_name = st.get("StationName")
        obs_time = st.get("ObsTime", {}).get("DateTime")

        if not station_id or not station_name or not obs_time:
            skipped_count += 1
            continue

        # 1. 經緯度座標解析 (優先提取 WGS84 座標)
        geo_info = st.get("GeoInfo", {})
        county = geo_info.get("CountyName", "其他")
        town = geo_info.get("TownName", "")
        coords_list = geo_info.get("Coordinates", [])

        lat, lon = None, None
        for coord in coords_list:
            if coord.get("CoordinateName") == "WGS84":
                lat = _clean_float(coord.get("StationLatitude"), min_val=20.0, max_val=27.5)
                lon = _clean_float(coord.get("StationLongitude"), min_val=118.0, max_val=123.5)
                break
        
        # 若無標註 WGS84 則回退使用第一組座標
        if lat is None or lon is None:
            if coords_list:
                lat = _clean_float(coords_list[0].get("StationLatitude"), min_val=20.0, max_val=27.5)
                lon = _clean_float(coords_list[0].get("StationLongitude"), min_val=118.0, max_val=123.5)

        if lat is None or lon is None:
            skipped_count += 1
            continue

        # 2. 氣象要素解析與數值過濾
        weather_elem = st.get("WeatherElement", {})
        
        # 氣溫：合理範圍 -20°C ~ 50°C，且剔除 -99 / 空值
        raw_temp = weather_elem.get("AirTemperature")
        temp = _clean_float(raw_temp, min_val=-20.0, max_val=50.0)
        if temp is None:
            skipped_count += 1
            continue  # 氣溫缺測或異常者不納入

        # 相對濕度 (0 ~ 100%)
        humidity = _clean_float(weather_elem.get("RelativeHumidity"), min_val=0.0, max_val=100.0)
        # 風速 (m/s)
        wind_speed = _clean_float(weather_elem.get("WindSpeed"), min_val=0.0, max_val=100.0)
        # 天氣現象
        weather = weather_elem.get("Weather") or "多雲"
        # 時雨量 (mm)
        precipitation = _clean_float(weather_elem.get("Now", {}).get("Precipitation"), min_val=0.0, max_val=1000.0)
        
        # 當日極端氣溫
        daily_high_info = weather_elem.get("DailyExtreme", {}).get("DailyHigh", {}).get("TemperatureInfo", {})
        daily_high = _clean_float(daily_high_info.get("AirTemperature"), min_val=-20.0, max_val=50.0)

        daily_low_info = weather_elem.get("DailyExtreme", {}).get("DailyLow", {}).get("TemperatureInfo", {})
        daily_low = _clean_float(daily_low_info.get("AirTemperature"), min_val=-20.0, max_val=50.0)

        cleaned_records.append({
            "station_id": station_id,
            "station_name": station_name,
            "county": county,
            "town": town,
            "lat": lat,
            "lon": lon,
            "observed_at": obs_time,
            "temperature": temp,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "weather": weather,
            "precipitation": precipitation,
            "daily_high": daily_high,
            "daily_low": daily_low
        })

    print(f"🧹 資料清洗完成：成功解析 {len(cleaned_records)} 座有效觀測測站（已過濾 {skipped_count} 筆缺測/異常紀錄）。")
    return cleaned_records


def init_database(db_path: str = DB_PATH) -> sqlite3.Connection:
    """建立 SQLite 資料庫與 StationObservations 表格 (設定 UNIQUE 鍵防重複插入)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS StationObservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT NOT NULL,
            station_name TEXT NOT NULL,
            county TEXT NOT NULL,
            town TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            observed_at TEXT NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL,
            wind_speed REAL,
            weather TEXT,
            precipitation REAL,
            daily_high REAL,
            daily_low REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(station_id, observed_at)
        );
    """)
    conn.commit()
    return conn


def save_to_database(records: list[dict], db_path: str = DB_PATH) -> int:
    """將清洗後之測站氣象資料批次寫入 SQLite，若已存在則覆蓋更新 (INSERT OR REPLACE)"""
    conn = init_database(db_path)
    cursor = conn.cursor()

    insert_sql = """
        INSERT OR REPLACE INTO StationObservations (
            station_id, station_name, county, town, lat, lon,
            observed_at, temperature, humidity, wind_speed, weather,
            precipitation, daily_high, daily_low
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    data_tuples = [
        (
            r["station_id"], r["station_name"], r["county"], r["town"],
            r["lat"], r["lon"], r["observed_at"], r["temperature"],
            r["humidity"], r["wind_speed"], r["weather"], r["precipitation"],
            r["daily_high"], r["daily_low"]
        )
        for r in records
    ]
    cursor.executemany(insert_sql, data_tuples)
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count


def verify_database(db_path: str = DB_PATH):
    """資料庫驗證查詢 (檢視統計與極值)"""
    conn = sqlite3.connect(db_path)
    print("\n🔍 正在驗證資料庫內容...")

    # 1. 測站總數與涵蓋縣市
    df_counties = pd.read_sql_query("""
        SELECT county, COUNT(*) as station_count, ROUND(AVG(temperature), 1) as avg_temp
        FROM StationObservations
        GROUP BY county
        ORDER BY station_count DESC;
    """, conn)
    print(f"📊 涵蓋縣市數：{len(df_counties)} 個縣市")
    print("📋 測站數量前 5 縣市：")
    print(df_counties.head(5).to_string(index=False))

    # 2. 全台最熱測站 Top 3
    df_hot = pd.read_sql_query("""
        SELECT station_name, county, town, temperature, humidity, observed_at
        FROM StationObservations
        ORDER BY temperature DESC
        LIMIT 3;
    """, conn)
    print("\n🔥 全台即時最高溫測站 Top 3：")
    print(df_hot.to_string(index=False))

    # 3. 全台最冷測站 Top 3
    df_cold = pd.read_sql_query("""
        SELECT station_name, county, town, temperature, humidity, observed_at
        FROM StationObservations
        ORDER BY temperature ASC
        LIMIT 3;
    """, conn)
    print("\n❄️ 全台即時最低溫測站 Top 3：")
    print(df_cold.to_string(index=False))

    conn.close()


def main():
    print("=" * 60)
    print("🌤️ Taiwan CWA O-A0003-001 — 即時測站觀測資料庫擷取作業")
    print("=" * 60)
    try:
        # 1. 擷取資料
        json_data = fetch_cwa_observations(CWA_API_KEY)
        
        # 2. 解析與清洗資料
        records = parse_station_observations(json_data)

        # 3. 寫入資料庫
        save_to_database(records, DB_PATH)
        print(f"💾 成功存入 SQLite 資料庫: {DB_PATH}")

        # 4. 驗證資料
        verify_database(DB_PATH)
        print("\n🎉 O-A0003-001 即時觀測資料更新與驗證全部完成！")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        raise e


if __name__ == "__main__":
    main()
