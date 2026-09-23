"""
api/weather.py
Vercel Serverless Function: 中央氣象署 (CWA) O-A0003-001 即時測站觀測 API
端點路徑：GET /api/weather
"""

import os
import json
import ssl
import urllib.request
from http.server import BaseHTTPRequestHandler

# 氣象署 API 設定
CWA_API_KEY = os.environ.get("CWA_API_KEY", "CWA-4078E566-C632-4356-8C9F-D1B4AE74E894")
DATASET_ID = "O-A0003-001"


def _clean_float(val, min_val=None, max_val=None, digits=1):
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
        if digits is not None:
            return round(f, digits)
        return f
    except (ValueError, TypeError):
        return None


def get_weather_data():
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{DATASET_ID}?Authorization={CWA_API_KEY}"
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CWA-Vercel-Weather/1.0"}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
        if response.status != 200:
            raise ConnectionError(f"CWA API error status: {response.status}")
        raw = response.read().decode("utf-8")
        data = json.loads(raw)
        if not data.get("success"):
            raise ValueError("CWA API returned failure")

    stations = data.get("records", {}).get("Station", [])
    cleaned = []

    for st in stations:
        station_id = st.get("StationId")
        station_name = st.get("StationName")
        obs_time = st.get("ObsTime", {}).get("DateTime")
        if not station_id or not station_name or not obs_time:
            continue

        geo_info = st.get("GeoInfo", {})
        county = geo_info.get("CountyName", "其他")
        town = geo_info.get("TownName", "")
        coords_list = geo_info.get("Coordinates", [])

        lat, lon = None, None
        for coord in coords_list:
            if coord.get("CoordinateName") == "WGS84":
                lat = _clean_float(coord.get("StationLatitude"), min_val=20.0, max_val=27.5, digits=4)
                lon = _clean_float(coord.get("StationLongitude"), min_val=118.0, max_val=123.5, digits=4)
                break
        if lat is None or lon is None:
            if coords_list:
                lat = _clean_float(coords_list[0].get("StationLatitude"), min_val=20.0, max_val=27.5, digits=4)
                lon = _clean_float(coords_list[0].get("StationLongitude"), min_val=118.0, max_val=123.5, digits=4)

        if lat is None or lon is None:
            continue

        weather_elem = st.get("WeatherElement", {})
        temp = _clean_float(weather_elem.get("AirTemperature"), min_val=-20.0, max_val=50.0, digits=1)
        if temp is None:
            continue

        humidity = _clean_float(weather_elem.get("RelativeHumidity"), min_val=0.0, max_val=100.0, digits=1)
        wind_speed = _clean_float(weather_elem.get("WindSpeed"), min_val=0.0, max_val=100.0, digits=1)
        weather = weather_elem.get("Weather") or "多雲"
        precipitation = _clean_float(weather_elem.get("Now", {}).get("Precipitation"), min_val=0.0, max_val=1000.0, digits=1)

        daily_high_info = weather_elem.get("DailyExtreme", {}).get("DailyHigh", {}).get("TemperatureInfo", {})
        daily_high = _clean_float(daily_high_info.get("AirTemperature"), min_val=-20.0, max_val=50.0, digits=1)

        daily_low_info = weather_elem.get("DailyExtreme", {}).get("DailyLow", {}).get("TemperatureInfo", {})
        daily_low = _clean_float(daily_low_info.get("AirTemperature"), min_val=-20.0, max_val=50.0, digits=1)

        cleaned.append({
            "station_id": station_id,
            "station_name": station_name,
            "county": county,
            "town": town,
            "lat": lat,
            "lon": lon,
            "temperature": temp,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "weather": weather,
            "precipitation": precipitation,
            "daily_high": daily_high,
            "daily_low": daily_low,
            "observed_at": obs_time
        })

    # 依照氣溫降序排序
    cleaned.sort(key=lambda x: x["temperature"], reverse=True)
    return cleaned


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = get_weather_data()
            latest_time = data[0]["observed_at"] if data else ""
            res_payload = {
                "status": "ok",
                "source": "CWA O-A0003-001",
                "updated_at": latest_time,
                "count": len(data),
                "stations": data
            }
            body = json.dumps(res_payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, s-maxage=300, stale-while-revalidate=600")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err_payload = {"status": "error", "message": str(e)}
            body = json.dumps(err_payload).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
