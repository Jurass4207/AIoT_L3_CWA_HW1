"""
fetch_data.py
中央氣象署 (CWA) 一週天氣預報資料擷取與 SQLite 資料庫存儲程式
對應課程步驟：
- 步驟 03: 中央氣象署 CWA Open Data 平台 (API Key)
- 步驟 04: API 資料取得 (Requests)
- 步驟 05: JSON 資料結構解析
- 步驟 06: 提取最高與最低氣溫 (MinT / MaxT)
- 步驟 07: 資料整理與預覽 (Pandas)
- 步驟 08: 建立 SQLite 資料庫 (data.db)
- 步驟 09: 資料庫設計 (TemperatureForecasts 表格)
- 步驟 10: 查詢資料驗證 (SQL 檢查)
- 步驟 20: 程式碼品質與優化 (防重複插入、例外處理、結構模組化)
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
DATASET_ID = "F-D0047-091"  # 臺灣各縣市未來 1 週天氣預報
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

# 區域與縣市映射表 (對應海報分區及全台縣市)
REGION_MAPPING = {
    "北部地區": ["基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣"],
    "中部地區": ["臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣"],
    "南部地區": ["臺南市", "高雄市", "屏東縣"],
    "東北部地區": ["宜蘭縣"],
    "東部地區": ["花蓮縣"],
    "東南部地區": ["臺東縣"],
    "離島地區": ["澎湖縣", "金門縣", "連江縣"]
}


def fetch_cwa_forecast(api_key: str = CWA_API_KEY) -> dict:
    """呼叫中央氣象署 OpenData API 取得一週天氣預報 JSON 資料"""
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{DATASET_ID}?Authorization={api_key}"
    print(f"📡 正在向中央氣象署請求資料集 ({DATASET_ID})...")

    # 建立 SSL 上下文 (解決 Windows 平台憑證鏈問題)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CWA-Weather-Forecast-App/1.0"}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
        if response.status != 200:
            raise ConnectionError(f"CWA API 回應錯誤，狀態碼: {response.status}")
        raw_data = response.read().decode("utf-8")
        data = json.loads(raw_data)
        if not data.get("success"):
            raise ValueError(f"CWA API 回傳失敗訊息: {data}")
        print("✅ 成功獲取氣象預報資料！")
        return data


def parse_temperature_data(json_data: dict) -> list[dict]:
    """
    解析 JSON 結構，提取各縣市及彙總分區每日之最高溫 (MaxT) 與最低溫 (MinT)
    """
    records = json_data.get("records", {})
    location_groups = records.get("Locations", [])
    if not location_groups:
        raise ValueError("氣象資料中未找到 Locations 欄位")

    locations = location_groups[0].get("Location", [])
    raw_records = []

    # 1. 提取全台 22 縣市每日數據
    for loc in locations:
        city_name = loc.get("LocationName")
        elements = loc.get("WeatherElement", [])
        
        max_t_list = []
        min_t_list = []

        for elem in elements:
            elem_name = elem.get("ElementName")
            if elem_name == "最高溫度":
                max_t_list = elem.get("Time", [])
            elif elem_name == "最低溫度":
                min_t_list = elem.get("Time", [])

        # 依日期 (YYYY-MM-DD) 整合 12 小時區間的溫度
        daily_temps = {}
        for item in max_t_list:
            start_time = item.get("StartTime", "")
            date_str = start_time[:10]
            val = float(item["ElementValue"][0]["MaxTemperature"])
            daily_temps.setdefault(date_str, {})
            daily_temps[date_str]["maxT"] = max(daily_temps[date_str].get("maxT", -999), val)

        for item in min_t_list:
            start_time = item.get("StartTime", "")
            date_str = start_time[:10]
            val = float(item["ElementValue"][0]["MinTemperature"])
            daily_temps.setdefault(date_str, {})
            daily_temps[date_str]["minT"] = min(daily_temps[date_str].get("minT", 999), val)

        for date_str, temp in daily_temps.items():
            if "minT" in temp and "maxT" in temp:
                raw_records.append({
                    "regionName": city_name,
                    "dataDate": date_str,
                    "minT": round(temp["minT"], 1),
                    "maxT": round(temp["maxT"], 1)
                })

    # 2. 彙整海報指定之六大/七大代表分區（北部、中部、南部、東北部、東部、東南部、離島）
    df_raw = pd.DataFrame(raw_records)
    region_records = []

    for region, cities in REGION_MAPPING.items():
        subset = df_raw[df_raw["regionName"].isin(cities)]
        if not subset.empty:
            grouped = subset.groupby("dataDate").agg({
                "minT": "mean",
                "maxT": "mean"
            }).reset_index()
            for _, row in grouped.iterrows():
                region_records.append({
                    "regionName": region,
                    "dataDate": row["dataDate"],
                    "minT": round(float(row["minT"]), 1),
                    "maxT": round(float(row["maxT"]), 1)
                })

    all_records = region_records + raw_records
    return all_records


def init_database(db_path: str = DB_PATH) -> sqlite3.Connection:
    """建立 SQLite 資料庫與 TemperatureForecasts 表格 (設定 UNIQUE 鍵防重複插入)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS TemperatureForecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regionName TEXT NOT NULL,
            dataDate TEXT NOT NULL,
            minT REAL NOT NULL,
            maxT REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(regionName, dataDate)
        );
    """)
    conn.commit()
    return conn


def save_to_database(records: list[dict], db_path: str = DB_PATH) -> int:
    """將解析後之氣象資料批次寫入 SQLite，若已存在則覆蓋更新 (INSERT OR REPLACE)"""
    conn = init_database(db_path)
    cursor = conn.cursor()

    insert_sql = """
        INSERT OR REPLACE INTO TemperatureForecasts (regionName, dataDate, minT, maxT)
        VALUES (?, ?, ?, ?);
    """
    data_tuples = [(r["regionName"], r["dataDate"], r["minT"], r["maxT"]) for r in records]
    cursor.executemany(insert_sql, data_tuples)
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count


def verify_database(db_path: str = DB_PATH):
    """資料庫驗證查詢 (對應海報步驟 10)"""
    conn = sqlite3.connect(db_path)
    print("\n🔍 正在驗證資料庫內容...")

    # 1. 查詢所有不重複地區
    df_regions = pd.read_sql_query("SELECT DISTINCT regionName FROM TemperatureForecasts;", conn)
    regions = df_regions["regionName"].tolist()
    print(f"📊 已存入地區清單 ({len(regions)} 個): {regions[:8]} ...")

    # 2. 查詢「中部地區」範例資料 (如海報所示)
    df_sample = pd.read_sql_query(
        "SELECT regionName, dataDate, minT, maxT FROM TemperatureForecasts WHERE regionName='中部地區' ORDER BY dataDate ASC;",
        conn
    )
    print("\n📋 範例驗證【中部地區】未來一週預報：")
    print(df_sample.to_string(index=False))

    conn.close()


def main():
    print("=" * 60)
    print("🌤️ Taiwan Weather Forecast — 資料庫擷取更新作業")
    print("=" * 60)
    try:
        # 1. 擷取資料
        json_data = fetch_cwa_forecast(CWA_API_KEY)
        
        # 2. 解析資料
        records = parse_temperature_data(json_data)
        print(f"📊 解析完成，總計產生 {len(records)} 筆預報紀錄。")

        # 3. 寫入資料庫
        save_to_database(records, DB_PATH)
        print(f"💾 成功存入 SQLite 資料庫: {DB_PATH}")

        # 4. 驗證資料
        verify_database(DB_PATH)
        print("\n🎉 資料更新與驗證全部完成！")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        raise e


if __name__ == "__main__":
    main()
