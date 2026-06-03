// =============================================================
// ПУТЬ        : docs/assets/app.js
// ОБОЗНАЧЕНИЕ : WD.UI.02
// НАИМЕНОВАНИЕ: Клиентский JS — графики, геокодинг, обновление
// ДОКУМЕНТ    : КС-СТО-1.04.СК
// ПРОГРАММА   : Weather Dashboard
// ЗАВИСИМОСТИ : Chart.js CDN, Bootstrap 5 CDN
// =============================================================
// Назначение:
//   1. Инициализация графиков Chart.js из inline JSON.
//   2. Геокодинг через Open-Meteo API (client-side fetch).
//   3. Управление избранным через localStorage.
//   4. Кнопка "Обновить" — fetch данных + перезагрузка метрик.
// =============================================================

// -------------------------------------------------------------
// Раздел 0. Константы
// -------------------------------------------------------------

const GEO_API = "https://geocoding-api.open-meteo.com/v1/search";
const FORECAST_API = "https://api.open-meteo.com/v1/forecast";
const FAVORITES_KEY = "wd_favorites";

// Цвета графиков
const COLORS = {
  temp:        "rgba(183, 28, 28, 0.9)",
  apparent:    "rgba(183, 28, 28, 0.4)",
  precip_prob: "rgba(21, 101, 192, 0.8)",
  precip:      "rgba(21, 101, 192, 0.4)",
  wind:        "rgba(27, 94, 32, 0.9)",
  gusts:       "rgba(27, 94, 32, 0.4)",
  humidity:    "rgba(74, 20, 140, 0.7)",
};

// -------------------------------------------------------------
// Раздел 1. Инициализация при загрузке
// -------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  initCharts();
  initSearch();
  initFavorites();
  initRefreshButton();
});

// -------------------------------------------------------------
// Раздел 2. Графики
// -------------------------------------------------------------

function initCharts() {
  const dataEl = document.getElementById("data-hourly48");
  if (!dataEl) return;

  let data;
  try {
    data = JSON.parse(dataEl.textContent);
  } catch (e) {
    console.error("[WD] Ошибка парсинга данных графика:", e);
    return;
  }

  const labels = data.labels || [];

  // --- График температуры ---
  const ctxTemp = document.getElementById("chart-temp");
  if (ctxTemp) {
    new Chart(ctxTemp, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Температура °C",
            data: data.temperature_2m,
            borderColor: COLORS.temp,
            backgroundColor: "rgba(183,28,28,0.05)",
            tension: 0.3,
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "Ощущается °C",
            data: data.apparent_temperature,
            borderColor: COLORS.apparent,
            borderDash: [5, 3],
            tension: 0.3,
            fill: false,
            pointRadius: 0,
            borderWidth: 1.5,
          },
        ],
      },
      options: chartOptions("°C"),
    });
  }

  // --- График осадков ---
  const ctxPrecip = document.getElementById("chart-precip");
  if (ctxPrecip) {
    new Chart(ctxPrecip, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Вероятность %",
            data: data.precipitation_probability,
            backgroundColor: "rgba(21,101,192,0.5)",
            borderColor: COLORS.precip_prob,
            borderWidth: 1,
            yAxisID: "y",
          },
          {
            label: "Осадки мм",
            data: data.precipitation,
            backgroundColor: "rgba(21,101,192,0.3)",
            borderColor: COLORS.precip,
            borderWidth: 1,
            type: "line",
            tension: 0.2,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        ...chartOptions("%"),
        scales: {
          x: xAxis(),
          y: { ...yAxis("Вероятность %"), position: "left", max: 100 },
          y1: { ...yAxis("Осадки мм"), position: "right", grid: { drawOnChartArea: false } },
        },
      },
    });
  }

  // --- График ветра ---
  const ctxWind = document.getElementById("chart-wind");
  if (ctxWind) {
    new Chart(ctxWind, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Ветер м/с",
            data: data.wind_speed_10m,
            borderColor: COLORS.wind,
            backgroundColor: "rgba(27,94,32,0.05)",
            tension: 0.3,
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "Порывы м/с",
            data: data.wind_gusts_10m,
            borderColor: COLORS.gusts,
            borderDash: [4, 2],
            tension: 0.3,
            fill: false,
            pointRadius: 0,
            borderWidth: 1.5,
          },
        ],
      },
      options: chartOptions("м/с"),
    });
  }

  // --- График влажности ---
  const ctxHum = document.getElementById("chart-hum");
  if (ctxHum) {
    new Chart(ctxHum, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Влажность %",
            data: data.relative_humidity_2m || [],
            borderColor: COLORS.humidity,
            backgroundColor: "rgba(74,20,140,0.05)",
            tension: 0.3,
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: chartOptions("%"),
    });
  }
}

// Базовые опции Chart.js в советском стиле
function chartOptions(unit) {
  return {
    responsive: true,
    animation: { duration: 300 },
    plugins: {
      legend: {
        labels: {
          font: { family: "Courier New", size: 10 },
          boxWidth: 12,
        },
      },
    },
    scales: {
      x: xAxis(),
      y: yAxis(unit),
    },
  };
}

function xAxis() {
  return {
    ticks: {
      font: { family: "Courier New", size: 9 },
      maxRotation: 45,
      maxTicksLimit: 12,
    },
    grid: { color: "rgba(0,0,0,0.06)" },
  };
}

function yAxis(unit) {
  return {
    ticks: { font: { family: "Courier New", size: 9 } },
    grid: { color: "rgba(0,0,0,0.06)" },
    title: {
      display: !!unit,
      text: unit,
      font: { family: "Courier New", size: 9 },
    },
  };
}

// -------------------------------------------------------------
// Раздел 3. Геокодинг
// -------------------------------------------------------------

function initSearch() {
  const input   = document.getElementById("geo-input");
  const btn     = document.getElementById("geo-search-btn");
  const results = document.getElementById("geo-results");

  if (!input || !btn || !results) return;

  btn.addEventListener("click", () => doSearch(input.value.trim()));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch(input.value.trim());
    if (e.key === "Escape") hideResults();
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#section-search")) hideResults();
  });

  function hideResults() {
    results.style.display = "none";
    results.innerHTML = "";
  }

  async function doSearch(query) {
    if (!query || query.length < 2) return;

    btn.textContent = "…";
    btn.disabled = true;

    try {
      const url = new URL(GEO_API);
      url.searchParams.set("name", query);
      url.searchParams.set("count", "8");
      url.searchParams.set("language", "ru");
      url.searchParams.set("format", "json");

      const resp = await fetch(url.toString());
      const data = await resp.json();
      const items = data.results || [];

      if (items.length === 0) {
        results.innerHTML = '<div class="geo-item">Ничего не найдено</div>';
        results.style.display = "block";
        return;
      }

      results.innerHTML = items.map((item) => {
        const parts = [item.name];
        if (item.admin1) parts.push(item.admin1);
        if (item.country) parts.push(item.country);
        const display = parts.join(", ");
        return `<div class="geo-item"
                     data-lat="${item.latitude}"
                     data-lon="${item.longitude}"
                     data-name="${display}"
                     data-tz="${item.timezone || 'auto'}">
                  ${display}
                </div>`;
      }).join("");
      results.style.display = "block";

      results.querySelectorAll(".geo-item").forEach((el) => {
        el.addEventListener("click", () => {
          const { lat, lon, name, tz } = el.dataset;
          hideResults();
          input.value = "";
          loadLocation(parseFloat(lat), parseFloat(lon), name, tz);
        });
      });

    } catch (err) {
      results.innerHTML = `<div class="geo-item text-danger">Ошибка: ${err.message}</div>`;
      results.style.display = "block";
    } finally {
      btn.textContent = "ПОИСК";
      btn.disabled = false;
    }
  }
}

// -------------------------------------------------------------
// Раздел 4. Загрузка данных для выбранной локации
// -------------------------------------------------------------

async function loadLocation(lat, lon, name, timezone) {
  const status = document.getElementById("refresh-status");
  if (status) status.textContent = `Загрузка данных для «${name}»…`;

  try {
    const url = new URL(FORECAST_API);
    url.searchParams.set("latitude", lat);
    url.searchParams.set("longitude", lon);
    url.searchParams.set("timezone", timezone || "auto");
    url.searchParams.set("forecast_days", "7");
    url.searchParams.set("hourly", [
      "temperature_2m","apparent_temperature","relative_humidity_2m",
      "dew_point_2m","precipitation","precipitation_probability",
      "weather_code","wind_speed_10m","wind_direction_10m","wind_gusts_10m"
    ].join(","));
    url.searchParams.set("daily", [
      "temperature_2m_max","temperature_2m_min",
      "apparent_temperature_max","apparent_temperature_min",
      "precipitation_sum","precipitation_probability_max",
      "sunrise","sunset","wind_gusts_10m_max","shortwave_radiation_sum"
    ].join(","));

    const resp = await fetch(url.toString());
    const data = await resp.json();

    if (data.error) throw new Error(data.reason || "API error");

    // Обновить заголовок
    const hdr = document.getElementById("hdr-location");
    if (hdr) hdr.textContent = name;

    // Обновить текущие условия
    updateCurrentConditions(data);

    // Обновить графики
    updateCharts(data);

    // Сохранить в избранное
    addToFavorites(lat, lon, name, timezone);

    if (status) status.textContent = `✓ Данные обновлены для «${name}»`;

  } catch (err) {
    if (status) status.textContent = `✗ Ошибка загрузки: ${err.message}`;
  }
}

function updateCurrentConditions(data) {
  const h = data.hourly || {};
  const get0 = (arr) => (arr && arr.length > 0 ? arr[0] : null);

  const map = {
    "cur-temp":   () => `${(get0(h.temperature_2m) || 0).toFixed(1)}°C`,
    "cur-hum":    () => `${Math.round(get0(h.relative_humidity_2m) || 0)}%`,
    "cur-wind":   () => `${(get0(h.wind_speed_10m) || 0).toFixed(1)} м/с`,
    "cur-precip": () => `${Math.round(get0(h.precipitation_probability) || 0)}%`,
  };

  for (const [id, fn] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (el) el.textContent = fn();
  }
}

function updateCharts(data) {
  // Пересоздание всех графиков с новыми данными через перезагрузку
  // (упрощённый вариант — полная перезагрузка страницы с сохранёнными данными)
  // В production: Chart.js data update через chart.data.datasets[i].data = ...
  const h = data.hourly || {};
  const limit = Math.min(48, (h.time || []).length);

  const labels = (h.time || []).slice(0, limit).map((t) => {
    const dt = new Date(t);
    return `${String(dt.getDate()).padStart(2,"0")}.${String(dt.getMonth()+1).padStart(2,"0")} ${String(dt.getHours()).padStart(2,"0")}:00`;
  });

  // Обновляем Chart.js инстанции через глобальный реестр
  const registry = Chart.instances;
  for (const id in registry) {
    const chart = registry[id];
    chart.data.labels = labels;

    const canvas = chart.canvas.id;
    const datasets = chart.data.datasets;

    if (canvas === "chart-temp") {
      datasets[0].data = (h.temperature_2m || []).slice(0, limit);
      datasets[1].data = (h.apparent_temperature || []).slice(0, limit);
    } else if (canvas === "chart-precip") {
      datasets[0].data = (h.precipitation_probability || []).slice(0, limit);
      datasets[1].data = (h.precipitation || []).slice(0, limit);
    } else if (canvas === "chart-wind") {
      datasets[0].data = (h.wind_speed_10m || []).slice(0, limit);
      datasets[1].data = (h.wind_gusts_10m || []).slice(0, limit);
    } else if (canvas === "chart-hum") {
      datasets[0].data = (h.relative_humidity_2m || []).slice(0, limit);
    }

    chart.update("active");
  }
}

// -------------------------------------------------------------
// Раздел 5. Кнопка "Обновить"
// -------------------------------------------------------------

function initRefreshButton() {
  const btn = document.getElementById("btn-refresh");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    // Читаем последнюю локацию из latest.json
    const status = document.getElementById("refresh-status");
    if (status) status.textContent = "Загрузка latest.json…";

    try {
      const resp = await fetch("data/latest.json?t=" + Date.now());
      const data = await resp.json();
      const loc = data.location || {};
      const name = loc.name || "Неизвестно";
      const lat  = loc.latitude || 0;
      const lon  = loc.longitude || 0;
      const tz   = loc.timezone || "auto";

      await loadLocation(lat, lon, name, tz);
    } catch (err) {
      if (status) status.textContent = `✗ Ошибка: ${err.message}`;
    }
  });
}

// -------------------------------------------------------------
// Раздел 6. Избранное (localStorage)
// -------------------------------------------------------------

function initFavorites() {
  renderFavorites();
}

function addToFavorites(lat, lon, name, tz) {
  const favs = loadFavorites();
  const key = `${lat.toFixed(3)}_${lon.toFixed(3)}`;

  const exists = favs.some((f) => f.key === key);
  if (!exists) {
    favs.unshift({ key, lat, lon, name, tz });
    // Хранить не более 5 элементов
    const limited = favs.slice(0, 5);
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(limited));
    renderFavorites();
  }
}

function loadFavorites() {
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
  } catch {
    return [];
  }
}

function renderFavorites() {
  const container = document.getElementById("favorites-list");
  if (!container) return;

  const favs = loadFavorites();
  if (favs.length === 0) {
    container.innerHTML = '<span class="text-muted" style="font-size:11px">Нет избранного</span>';
    return;
  }

  container.innerHTML = favs.map((f) =>
    `<button class="fav-btn"
             data-lat="${f.lat}" data-lon="${f.lon}"
             data-name="${f.name}" data-tz="${f.tz}">
       ${f.name.split(",")[0]}
     </button>`
  ).join("");

  container.querySelectorAll(".fav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const { lat, lon, name, tz } = btn.dataset;
      loadLocation(parseFloat(lat), parseFloat(lon), name, tz);
    });
  });
}