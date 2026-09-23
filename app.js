/**
 * app.js — 台灣即時氣象地圖 (Taiwan Live Weather Map)
 * 前端核心地圖互動、API 資料同步與資料視覺化邏輯
 */

// 全域狀態
let map;
let baseTileLayer;
let markerLayer;
let allStations = [];
let currentLayer = 'temp'; // 'temp', 'humidity', 'wind', 'rain'
let showLabels = false; // 預設為使用者偏好的質感發光圓點
let isDarkMode = true;

// 底圖 URL 定義 (無浮水印高品質深色圖磚)
const TILE_DARK = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';
const ATTR_DARK = 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ';
const TILE_LIGHT = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTR_LIGHT = '&copy; OpenStreetMap contributors';

// 顏色映射 (完全對齊 taiwan-weather-map.vercel.app 色階)
function getTempColor(t) {
  if (t === null || t === undefined || isNaN(t)) return '#6b7280';
  if (t < 5.0) return '#2c7bb6';
  if (t < 10.0) return '#5aa2cf';
  if (t < 15.0) return '#abd9e9';
  if (t < 20.0) return '#7fcdbb';
  if (t < 24.0) return '#d9ef8b';
  if (t < 28.0) return '#fee08b';
  if (t < 32.0) return '#fdae61';
  if (t < 36.0) return '#f46d43';
  return '#d73027';
}

function getHumidityColor(h) {
  if (h === null || isNaN(h)) return '#6b7280';
  if (h < 40) return '#fbbf24';
  if (h < 60) return '#34d399';
  if (h < 80) return '#38bdf8';
  return '#2563eb';
}

function getWindColor(w) {
  if (w === null || isNaN(w)) return '#6b7280';
  if (w < 2) return '#94a3b8';
  if (w < 5) return '#38bdf8';
  if (w < 10) return '#f59e0b';
  return '#ef4444';
}

function getRainColor(r) {
  if (r === null || isNaN(r) || r === 0) return '#94a3b8';
  if (r < 5) return '#38bdf8';
  if (r < 15) return '#0ea5e9';
  if (r < 40) return '#eab308';
  return '#ef4444';
}

function getValueAndColor(st) {
  if (currentLayer === 'temp') {
    return { val: st.temperature, unit: '°C', color: getTempColor(st.temperature) };
  } else if (currentLayer === 'humidity') {
    return { val: st.humidity, unit: '%', color: getHumidityColor(st.humidity) };
  } else if (currentLayer === 'wind') {
    return { val: st.wind_speed, unit: 'm/s', color: getWindColor(st.wind_speed) };
  } else if (currentLayer === 'rain') {
    return { val: st.precipitation, unit: 'mm', color: getRainColor(st.precipitation) };
  }
  return { val: st.temperature, unit: '°C', color: getTempColor(st.temperature) };
}

// 1. 初始化 Leaflet 地圖
function initMap() {
  map = L.map('map', {
    center: [23.75, 120.95],
    zoom: 7.5,
    zoomControl: false,
    attributionControl: true
  });

  L.control.zoom({ position: 'bottomleft' }).addTo(map);

  baseTileLayer = L.tileLayer(TILE_DARK, {
    attribution: ATTR_DARK,
    maxZoom: 18
  }).addTo(map);

  markerLayer = L.layerGroup().addTo(map);
}

// 2. 獲取氣象資料 (優先呼叫 /api/weather，若失敗則回退本地 data/latest.json)
async function fetchWeatherData() {
  const statusText = document.getElementById('status-text');
  statusText.textContent = '同步資料中...';

  let data = null;

  try {
    const res = await fetch('/api/weather');
    if (res.ok) {
      data = await res.json();
    }
  } catch (err) {
    console.warn('Vercel API endpoint unavailable, falling back to local cached data:', err);
  }

  // 若 Serverless API 回傳失敗，嘗試回退讀取本地 data/latest.json
  if (!data || !data.stations) {
    try {
      const fallbackRes = await fetch('data/latest.json');
      if (fallbackRes.ok) {
        data = await fallbackRes.json();
      }
    } catch (fallbackErr) {
      console.error('Fallback data load failed:', fallbackErr);
    }
  }

  if (data && data.stations && data.stations.length > 0) {
    allStations = data.stations;
    updateTopMetrics(allStations, data.updated_at);
    populateCountySelect(allStations);
    renderMarkers();
    statusText.textContent = `即時同步完成 (${allStations.length} 站)`;
  } else {
    statusText.textContent = '資料載入異常';
  }
}

// 3. 更新頂部指標卡
function updateTopMetrics(stations, updatedAt) {
  if (!stations || stations.length === 0) return;

  const validTemps = stations.filter(s => s.temperature !== null && !isNaN(s.temperature));
  if (validTemps.length === 0) return;

  const highest = validTemps.reduce((prev, curr) => (curr.temperature > prev.temperature ? curr : prev), validTemps[0]);
  const lowest = validTemps.reduce((prev, curr) => (curr.temperature < prev.temperature ? curr : prev), validTemps[0]);
  const avgTemp = (validTemps.reduce((acc, curr) => acc + curr.temperature, 0) / validTemps.length).toFixed(1);

  document.getElementById('metric-count').textContent = `${stations.length} 站`;
  document.getElementById('metric-hot').textContent = `${highest.temperature} °C`;
  document.getElementById('metric-cold').textContent = `${lowest.temperature} °C`;
  document.getElementById('metric-avg').textContent = `${avgTemp} °C`;

  if (updatedAt) {
    const formatted = updatedAt.replace('T', ' ').substring(0, 16);
    document.getElementById('obs-time').textContent = `觀測時間：${formatted}`;
  }
}

// 4. 填充縣市下拉選單
function populateCountySelect(stations) {
  const select = document.getElementById('select-county');
  const counties = Array.from(new Set(stations.map(s => s.county).filter(Boolean))).sort();

  select.innerHTML = '<option value="ALL">全台所有縣市 (全部)</option>';
  counties.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = c;
    select.appendChild(opt);
  });
}

// 5. 渲染測站點位
function renderMarkers() {
  if (!markerLayer) return;
  markerLayer.clearLayers();

  const selectedCounty = document.getElementById('select-county').value;
  const searchKw = document.getElementById('input-search').value.trim().toLowerCase();

  const filtered = allStations.filter(st => {
    const matchCounty = (selectedCounty === 'ALL' || st.county === selectedCounty);
    const matchSearch = (!searchKw || 
      st.station_name.toLowerCase().includes(searchKw) || 
      (st.town && st.town.toLowerCase().includes(searchKw)) ||
      (st.county && st.county.toLowerCase().includes(searchKw))
    );
    return matchCounty && matchSearch;
  });

  filtered.forEach(st => {
    const { val, unit, color } = getValueAndColor(st);
    const displayVal = val !== null && val !== undefined ? `${val} ${unit}` : '無數據';

    // 格式化彈跳視窗卡片內容
    const hum = st.humidity !== null ? `${st.humidity} %` : '無數據';
    const wind = st.wind_speed !== null ? `${st.wind_speed} m/s` : '無數據';
    const rain = st.precipitation !== null ? `${st.precipitation} mm` : '0.0 mm';
    const dHigh = st.daily_high !== null ? `${st.daily_high} °C` : '無';
    const dLow = st.daily_low !== null ? `${st.daily_low} °C` : '無';
    const timeStr = st.observed_at ? st.observed_at.replace('T', ' ').substring(0, 19) : '';

    const popupHtml = `
      <div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif; min-width:190px; color:#f3f4f6;">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.12); padding-bottom:6px; margin-bottom:8px;">
          <b style="font-size:1.15rem; color:#f9fafb;">${st.station_name} 測站</b>
          <span style="font-size:0.75rem; background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px; color:#9ca3af;">${st.county}${st.town || ''}</span>
        </div>
        <div style="display:flex; align-items:baseline; gap:8px; margin-bottom:8px;">
          <span style="font-size:1.8rem; font-weight:800; color:${color}; line-height:1;">${val !== null ? val : '--'}</span>
          <span style="font-size:1.1rem; color:${color}; font-weight:600;">${unit}</span>
          <span style="font-size:0.8rem; color:#9ca3af; margin-left:auto;">${st.weather || '即時實測'}</span>
        </div>
        <div style="font-size:0.82rem; line-height:1.6; color:#d1d5db;">
          <div>🌡️ <b>即時氣溫</b>：<span style="color:#f87171;">${st.temperature !== null ? st.temperature + ' °C' : '無'}</span></div>
          <div>💧 <b>相對濕度</b>：<span style="color:#38bdf8;">${hum}</span></div>
          <div>💨 <b>即時風速</b>：<span style="color:#34d399;">${wind}</span></div>
          <div>🌧️ <b>時雨量</b>：<span style="color:#60a5fa;">${rain}</span></div>
          <div>📈 <b>今日極值</b>：<span style="color:#f59e0b;">${dLow} ~ ${dHigh}</span></div>
          <div style="font-size:0.72rem; color:#6b7280; margin-top:5px;">🕒 觀測時間：${timeStr}</div>
        </div>
      </div>
    `;

    if (showLabels) {
      // 膠囊數字標籤模式
      const labelHtml = `<div class="temp-label" style="background:${color};">${val !== null ? val : '--'}</div>`;
      const icon = L.divIcon({
        className: 'temp-marker-icon',
        html: labelHtml,
        iconSize: [32, 18],
        iconAnchor: [16, 9]
      });
      L.marker([st.lat, st.lon], { icon })
        .bindPopup(popupHtml, { maxWidth: 290 })
        .bindTooltip(`${st.station_name} (${st.county}${st.town || ''}): ${displayVal}`)
        .addTo(markerLayer);
    } else {
      // 經典發光圓點模式 (預設，使用者喜愛版)
      L.circleMarker([st.lat, st.lon], {
        radius: 7.5,
        color: '#ffffff',
        weight: 1.5,
        fillColor: color,
        fillOpacity: 0.88
      })
        .bindPopup(popupHtml, { maxWidth: 290 })
        .bindTooltip(`${st.station_name} (${st.county}${st.town || ''}): ${displayVal}`)
        .addTo(markerLayer);
    }
  });

  // 自動對焦選取縣市
  if (selectedCounty !== 'ALL' && filtered.length > 0) {
    const lats = filtered.map(s => s.lat);
    const lons = filtered.map(s => s.lon);
    map.setView([
      lats.reduce((a, b) => a + b, 0) / lats.length,
      lons.reduce((a, b) => a + b, 0) / lons.length
    ], 10);
  }
}

// 6. 圖表與排行榜渲染 (Chart.js)
let chartHotInstance = null;
let chartColdInstance = null;
let chartCountyInstance = null;

function renderChartsAndTable() {
  if (!allStations || allStations.length === 0) return;

  const validTemps = allStations.filter(s => s.temperature !== null && !isNaN(s.temperature));
  
  // 1. 最高溫 Top 10
  const topHot = [...validTemps].sort((a, b) => b.temperature - a.temperature).slice(0, 10);
  const ctxHot = document.getElementById('chart-hot').getContext('2d');
  if (chartHotInstance) chartHotInstance.destroy();
  chartHotInstance = new Chart(ctxHot, {
    type: 'bar',
    data: {
      labels: topHot.map(s => `${s.station_name} (${s.county})`),
      datasets: [{
        label: '氣溫 (°C)',
        data: topHot.map(s => s.temperature),
        backgroundColor: '#ef4444',
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#9ca3af' } },
        y: { grid: { display: false }, ticks: { color: '#f3f4f6' } }
      }
    }
  });

  // 2. 最低溫 Top 10
  const topCold = [...validTemps].sort((a, b) => a.temperature - b.temperature).slice(0, 10);
  const ctxCold = document.getElementById('chart-cold').getContext('2d');
  if (chartColdInstance) chartColdInstance.destroy();
  chartColdInstance = new Chart(ctxCold, {
    type: 'bar',
    data: {
      labels: topCold.map(s => `${s.station_name} (${s.county})`),
      datasets: [{
        label: '氣溫 (°C)',
        data: topCold.map(s => s.temperature),
        backgroundColor: '#38bdf8',
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#9ca3af' } },
        y: { grid: { display: false }, ticks: { color: '#f3f4f6' } }
      }
    }
  });

  // 3. 各縣市均溫
  const countyMap = {};
  validTemps.forEach(s => {
    if (!s.county) return;
    if (!countyMap[s.county]) countyMap[s.county] = [];
    countyMap[s.county].push(s.temperature);
  });
  const countyList = Object.keys(countyMap).map(c => {
    const arr = countyMap[c];
    return { county: c, avg: Number((arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(1)) };
  }).sort((a, b) => b.avg - a.avg);

  const ctxCounty = document.getElementById('chart-county').getContext('2d');
  if (chartCountyInstance) chartCountyInstance.destroy();
  chartCountyInstance = new Chart(ctxCounty, {
    type: 'bar',
    data: {
      labels: countyList.map(item => item.county),
      datasets: [{
        label: '平均氣溫 (°C)',
        data: countyList.map(item => item.avg),
        backgroundColor: '#10b981',
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#9ca3af', maxRotation: 45, minRotation: 45 } },
        y: { grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#9ca3af' } }
      }
    }
  });

  // 4. 填充表格
  const tbody = document.getElementById('table-body');
  tbody.innerHTML = '';
  document.getElementById('table-count').textContent = `${allStations.length} 站`;

  allStations.forEach(st => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${st.station_id}</td>
      <td style="font-weight:600; color:#fff;">${st.station_name}</td>
      <td>${st.county || '--'}</td>
      <td>${st.town || '--'}</td>
      <td style="font-weight:700; color:${getTempColor(st.temperature)}">${st.temperature !== null ? st.temperature : '--'}</td>
      <td>${st.humidity !== null ? st.humidity : '--'}</td>
      <td>${st.wind_speed !== null ? st.wind_speed : '--'}</td>
      <td>${st.precipitation !== null ? st.precipitation : '--'}</td>
      <td>${st.daily_high !== null ? st.daily_high : '--'}</td>
      <td>${st.daily_low !== null ? st.daily_low : '--'}</td>
      <td style="color:#9ca3af; font-size:0.75rem;">${st.observed_at ? st.observed_at.replace('T', ' ').substring(0, 16) : '--'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// 7. 綁定事件監聽
document.addEventListener('DOMContentLoaded', () => {
  initMap();
  fetchWeatherData();

  // 圖層切換按鈕
  document.querySelectorAll('.layer-btn[data-layer]').forEach(btn => {
    btn.addEventListener('click', e => {
      document.querySelectorAll('.layer-btn[data-layer]').forEach(b => b.classList.remove('active'));
      const target = e.currentTarget;
      target.classList.add('active');
      currentLayer = target.dataset.layer;
      
      // 更新圖例標題與單位
      const legendUnit = document.getElementById('legend-unit');
      const legendTitle = document.getElementById('legend-title');
      if (currentLayer === 'temp') {
        legendUnit.textContent = '°C';
        legendTitle.textContent = '即時地面氣溫色階';
      } else if (currentLayer === 'humidity') {
        legendUnit.textContent = '%';
        legendTitle.textContent = '即時相對濕度色階';
      } else if (currentLayer === 'wind') {
        legendUnit.textContent = 'm/s';
        legendTitle.textContent = '即時地面風速色階';
      } else if (currentLayer === 'rain') {
        legendUnit.textContent = 'mm';
        legendTitle.textContent = '時雨量累積色階';
      }

      renderMarkers();
    });
  });

  // 標籤樣式切換
  document.getElementById('toggle-label').addEventListener('change', e => {
    showLabels = e.target.checked;
    renderMarkers();
  });

  // 底圖切換
  document.getElementById('toggle-basemap').addEventListener('change', e => {
    isDarkMode = e.target.checked;
    map.removeLayer(baseTileLayer);
    if (isDarkMode) {
      baseTileLayer = L.tileLayer(TILE_DARK, { attribution: ATTR_DARK, maxZoom: 18 }).addTo(map);
    } else {
      baseTileLayer = L.tileLayer(TILE_LIGHT, { attribution: ATTR_LIGHT, maxZoom: 18 }).addTo(map);
    }
  });

  // 縣市與關鍵字過濾
  document.getElementById('select-county').addEventListener('change', renderMarkers);
  document.getElementById('input-search').addEventListener('input', renderMarkers);

  // 手動同步按鈕
  document.getElementById('btn-refresh').addEventListener('click', fetchWeatherData);

  // Modal 彈窗控制
  const modal = document.getElementById('modal-rankings');
  document.getElementById('btn-open-modal').addEventListener('click', () => {
    modal.classList.add('open');
    renderChartsAndTable();
  });
  document.getElementById('btn-close-modal').addEventListener('click', () => {
    modal.classList.remove('open');
  });
  modal.addEventListener('click', e => {
    if (e.target === modal) modal.classList.remove('open');
  });
});
