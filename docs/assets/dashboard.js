/**
 * Weather Dashboard — Live mode + Snapshot mode
 * ES2022+ Vanilla JS, без фреймворков
 *
 * Архитектура:
 *   USE_LIVE = true  → fetch Open-Meteo API напрямую
 *   USE_LIVE = false → читает WEATHER_SNAPSHOT из data.js
 *
 * Кеш: localStorage с дифференцированным TTL (зеркало серверного TTL)
 * Числа: Intl.NumberFormat("ru-RU")
 * Даты:  Intl.DateTimeFormat("ru-RU", { timeZone })
 */

"use strict";

// ═══════════════════════════════════════════════════════════════════════════
// КОНФИГУРАЦИЯ
// ═══════════════════════════════════════════════════════════════════════════

/** Переключатель режимов. false → Snapshot mode (data.js) */
const USE_LIVE = false;

const API = {
  FORECAST:    "https://api.open-meteo.com/v1/forecast",
  GEOCODING:   "https://geocoding-api.open-meteo.com/v1/search",
  AIR_QUALITY: "https://air-quality-api.open-meteo.com/v1/air-quality",
  ELEVATION:   "https://api.open-meteo.com/v1/elevation",
};

/** TTL в миллисекундах — зеркало серверного TTL (ТЗ §3.3) */
const TTL = {
  current:    5  * 60 * 1000,
  hourly24h:  30 * 60 * 1000,
  daily7d:    3  * 60 * 60 * 1000,
  geocoding:  30 * 24 * 60 * 60 * 1000,
  elevation:  Infinity,
  airQuality: 60 * 60 * 1000,
};

const DEFAULT = {
  lat:      55.7558,
  lon:      37.6173,
  city:     "Москва",
  timezone: "Europe/Moscow",
};

const WMO_RU = {
  0:"Ясно",1:"Преимущественно ясно",2:"Переменная облачность",3:"Пасмурно",
  45:"Туман",48:"Изморозь",
  51:"Лёгкая морось",53:"Умеренная морось",55:"Сильная морось",
  61:"Слабый дождь",63:"Умеренный дождь",65:"Сильный дождь",
  71:"Слабый снег",73:"Умеренный снег",75:"Сильный снег",77:"Крупа",
  80:"Слабый ливень",81:"Умеренный ливень",82:"Сильный ливень",
  85:"Слабый снегопад",86:"Сильный снегопад",
  95:"Гроза",96:"Гроза с градом",99:"Сильная гроза с градом",
};

// ═══════════════════════════════════════════════════════════════════════════
// УТИЛИТЫ
// ═══════════════════════════════════════════════════════════════════════════

const fmtNum = (v, decimals = 1, fallback = "—") => {
  if (v == null || isNaN(v)) return fallback;
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(v);
};

const fmtDate = (isoStr, tz, opts) => {
  if (!isoStr) return "—";
  try {
    return new Intl.DateTimeFormat("ru-RU", { timeZone: tz, ...opts })
      .format(new Date(isoStr));
  } catch {
    return isoStr;
  }
};

const fmtWeekday = (isoDate, tz) =>
  fmtDate(`${isoDate}T12:00:00`, tz, { weekday: "short", day: "numeric", month: "short" });

const fmtTime = (isoStr, tz) =>
  fmtDate(isoStr, tz, { hour: "2-digit", minute: "2-digit" });

const degToDir = (deg) => {
  if (deg == null) return "—";
  const dirs = ["С","СВ","В","ЮВ","Ю","ЮЗ","З","СЗ"];
  return dirs[Math.round(deg / 45) % 8];
};

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/** Debounce — ES2022 */
const debounce = (fn, ms) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
};

// ═══════════════════════════════════════════════════════════════════════════
// localStorage КЕШ С TTL
// ═══════════════════════════════════════════════════════════════════════════

const Cache = {
  set(key, data, ttlMs) {
    try {
      localStorage.setItem(key, JSON.stringify({
        cachedAt: Date.now(),
        ttlMs,
        data,
      }));
    } catch { /* QuotaExceededError — игнорируем */ }
  },

  get(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      const { cachedAt, ttlMs, data } = JSON.parse(raw);
      if (ttlMs === Infinity || Date.now() - cachedAt < ttlMs) return data;
      localStorage.removeItem(key);
    } catch { /* корраптед кеш */ }
    return null;
  },

  /** Возвращает устаревший кеш (fallback при ошибке сети) */
  getStale(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      const { cachedAt, data } = JSON.parse(raw);
      return { data, cachedAt };
    } catch {}
    return null;
  },

  keyForecast: (lat, lon) => `forecast_${lat}_${lon}`,
  keyAQ:       (lat, lon) => `aq_${lat}_${lon}`,
  keyElev:     (lat, lon) => `elev_${lat}_${lon}`,
  keyGeo:      (q)        => `geo_${q.toLowerCase()}`,
};

// ═══════════════════════════════════════════════════════════════════════════
// HTTP — fetch с кешем
// ═══════════════════════════════════════════════════════════════════════════

async function apiFetch(url, params, cacheKey, ttlMs) {
  const cached = Cache.get(cacheKey);
  if (cached) return { data: cached, stale: false };

  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null)
  );
  const fullUrl = `${url}?${qs}`;

  let resp;
  try {
    resp = await fetch(fullUrl, {
      headers: { "Accept": "application/json" },
    });
  } catch (err) {
    // Сетевая ошибка — fallback на устаревший кеш
    const staleResult = Cache.getStale(cacheKey);
    if (staleResult) return { data: staleResult.data, stale: true, staleAt: staleResult.cachedAt };
    throw new NetworkError(`Нет соединения с сервером: ${err.message}`);
  }

  if (resp.status === 429) {
    const retryAfter = resp.headers.get("Retry-After");
    throw new RateLimitError(`Превышен лимит запросов. Повторите через ${retryAfter ?? "60"} с.`);
  }
  if (!resp.ok) {
    let detail = "";
    try { detail = (await resp.json()).reason ?? ""; } catch {}
    throw new APIError(resp.status, detail || `HTTP ${resp.status}`);
  }

  const data = await resp.json();
  Cache.set(cacheKey, data, ttlMs);
  return { data, stale: false };
}

// ── Кастомные ошибки ────────────────────────────────────────────────────
class APIError extends Error {
  constructor(status, detail) {
    super(detail);
    this.name = "APIError";
    this.status = status;
    this.detail = detail;
  }
}
class NetworkError extends Error { constructor(m) { super(m); this.name = "NetworkError"; } }
class RateLimitError extends Error { constructor(m) { super(m); this.name = "RateLimitError"; } }

// ═══════════════════════════════════════════════════════════════════════════
// ЗАПРОСЫ К API
// ═══════════════════════════════════════════════════════════════════════════

async function fetchForecast(lat, lon, timezone = "auto") {
  const params = {
    latitude:            lat,
    longitude:           lon,
    timezone,
    forecast_days:       7,
    past_days:           1,
    temperature_unit:    "celsius",
    wind_speed_unit:     "ms",
    precipitation_unit:  "mm",
    hourly: [
      "temperature_2m","apparent_temperature","precipitation","rain","snowfall",
      "precipitation_probability","wind_speed_10m","wind_direction_10m",
      "wind_gusts_10m","relative_humidity_2m","dew_point_2m",
      "surface_pressure","shortwave_radiation","uv_index","cloud_cover","visibility",
    ].join(","),
    daily: [
      "temperature_2m_max","temperature_2m_min","precipitation_sum",
      "wind_speed_10m_max","uv_index_max","sunrise","sunset",
    ].join(","),
    current: [
      "temperature_2m","apparent_temperature","wind_speed_10m",
      "relative_humidity_2m","precipitation","weather_code",
    ].join(","),
  };
  return apiFetch(API.FORECAST, params, Cache.keyForecast(lat, lon), TTL.daily7d);
}

async function fetchAirQuality(lat, lon) {
  const params = {
    latitude:  lat,
    longitude: lon,
    hourly:    "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone,european_aqi,us_aqi",
  };
  return apiFetch(API.AIR_QUALITY, params, Cache.keyAQ(lat, lon), TTL.airQuality);
}

async function fetchElevation(lat, lon) {
  const params = { latitude: lat, longitude: lon };
  const result = await apiFetch(API.ELEVATION, params, Cache.keyElev(lat, lon), TTL.elevation);
  return result.data?.elevation?.[0] ?? 0;
}

async function fetchGeocoding(query, count = 5) {
  const params = { name: query.trim(), count, language: "ru", format: "json" };
  const result = await apiFetch(API.GEOCODING, params, Cache.keyGeo(query), TTL.geocoding);
  return result.data?.results ?? [];
}

// ═══════════════════════════════════════════════════════════════════════════
// UX-СОСТОЯНИЯ
// ═══════════════════════════════════════════════════════════════════════════

const UI = {
  /** Показывает skeleton, скрывает контент */
  loading(sectionId) {
    const sk = document.getElementById(`${sectionId}-skeleton`);
    const ct = document.getElementById(`${sectionId}-content`);
    sk?.removeAttribute("hidden");
    ct?.setAttribute("hidden", "");
  },

  /** Скрывает skeleton, показывает контент */
  ready(sectionId) {
    const sk = document.getElementById(`${sectionId}-skeleton`);
    const ct = document.getElementById(`${sectionId}-content`);
    sk?.setAttribute("hidden", "");
    ct?.removeAttribute("hidden");
  },

  /** Состояние ошибки — человекопонятное сообщение + RFC 9457 детали */
  error(sectionId, err) {
    UI.ready(sectionId);
    const el = document.getElementById(`${sectionId}-error`);
    if (!el) return;
    el.removeAttribute("hidden");
    const msg = el.querySelector(".error-state__message");
    const pre = el.querySelector(".error-state__pre");
    if (msg) msg.textContent = _humanError(err);
    if (pre) pre.textContent = JSON.stringify({
      type: err.name ?? "Error",
      status: err.status ?? null,
      detail: err.message,
    }, null, 2);
  },

  /** Баннер устаревшего кеша */
  stale(cachedAt) {
    const banner = document.getElementById("stale-banner");
    const timeEl = document.getElementById("stale-time");
    if (!banner || !timeEl) return;
    banner.removeAttribute("hidden");
    timeEl.textContent = new Intl.DateTimeFormat("ru-RU", {
      timeStyle: "short", dateStyle: "short",
    }).format(new Date(cachedAt));
  },

  /** Пустое состояние */
  empty(sectionId) {
    UI.ready(sectionId);
    const el = document.getElementById(`${sectionId}-empty`);
    el?.removeAttribute("hidden");
  },

  /** Обновляет текст элемента */
  setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text ?? "—";
  },

  /** Обновляет innerHTML элемента */
  setHTML(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  },
};

function _humanError(err) {
  if (err instanceof NetworkError)
    return "Нет соединения с интернетом. Показаны кешированные данные.";
  if (err instanceof RateLimitError)
    return "Превышен лимит запросов к API. Пожалуйста, подождите.";
  if (err instanceof APIError && err.status === 400)
    return `Некорректный запрос: ${err.detail}`;
  if (err instanceof APIError)
    return `Ошибка сервера (${err.status}). Попробуйте позже.`;
  return "Произошла неожиданная ошибка. Попробуйте обновить страницу.";
}

// ═══════════════════════════════════════════════════════════════════════════
// РАСЧЁТ ИНДЕКСОВ (JS-реализация для Live mode)
// ═══════════════════════════════════════════════════════════════════════════

const Indices = {
  heatIndex(t, rh) {
    if (t < 27 || rh < 40) return t;
    const tf = t * 9 / 5 + 32;
    const hi = -42.379 + 2.04901523*tf + 10.14333127*rh
      - 0.22475541*tf*rh - 0.00683783*tf*tf - 0.05481717*rh*rh
      + 0.00122874*tf*tf*rh + 0.00085282*tf*rh*rh
      - 0.00000199*tf*tf*rh*rh;
    return (hi - 32) * 5 / 9;
  },

  windChill(t, v) {
    if (t > 10 || v < 1.3) return t;
    const vk = v * 3.6;
    return 13.12 + 0.6215*t - 11.37*(vk**0.16) + 0.3965*t*(vk**0.16);
  },

  dewPoint(t, rh) {
    if (rh <= 0) return t;
    const a = 17.625, b = 243.04;
    const g = Math.log(rh / 100) + a * t / (b + t);
    return b * g / (a - g);
  },

  uvRisk(uv) {
    if (uv <= 2)  return { label: "Низкий",        cls: "uv--low" };
    if (uv <= 5)  return { label: "Умеренный",      cls: "uv--moderate" };
    if (uv <= 7)  return { label: "Высокий",        cls: "uv--high" };
    if (uv <= 10) return { label: "Очень высокий",  cls: "uv--very-high" };
    return               { label: "Экстремальный",  cls: "uv--extreme" };
  },

  aqiCategoryEU(aqi) {
    if (aqi <= 20)  return { label: "Хороший",          cls: "aqi--good" };
    if (aqi <= 40)  return { label: "Удовлетворительный", cls: "aqi--fair" };
    if (aqi <= 60)  return { label: "Умеренный",        cls: "aqi--moderate" };
    if (aqi <= 80)  return { label: "Плохой",           cls: "aqi--poor" };
    if (aqi <= 100) return { label: "Очень плохой",     cls: "aqi--very-poor" };
    return                 { label: "Крайне плохой",    cls: "aqi--extremely-poor" };
  },

  comfortScore(t, rh, v, uv, precip) {
    const lin = (val, min, max) => clamp((val - min) / (max - min) * 100, 0, 100);
    const tSub  = t >= 18 && t <= 24 ? 100 :
                  t < 18  ? lin(t, -10, 18) : lin(38 - (t - 24), 0, 14);
    const rhSub = rh >= 40 && rh <= 60 ? 100 :
                  rh < 40 ? lin(rh, 10, 40) : lin(90 - (rh - 60), 0, 30);
    const vSub  = v <= 3 ? 100 : lin(15 - (v - 3), 0, 12);
    const uvSub = uv <= 2 ? 100 : lin(11 - (uv - 2), 0, 9);
    const pSub  = precip <= 0 ? 100 : lin(10 - precip, 0, 10);
    return clamp(0.35*tSub + 0.25*rhSub + 0.20*vSub + 0.10*uvSub + 0.10*pSub, 0, 100);
  },

  weatherTrend(means) {
    const n = means.length;
    if (n < 2) return null;
    const xMean = (n - 1) / 2;
    const yMean = means.reduce((a, b) => a + b, 0) / n;
    let ssXY = 0, ssXX = 0, ssYY = 0;
    for (let i = 0; i < n; i++) {
      ssXY += (i - xMean) * (means[i] - yMean);
      ssXX += (i - xMean) ** 2;
      ssYY += (means[i] - yMean) ** 2;
    }
    if (ssXX === 0) return { slope: 0, r2: 0, trend: "stable", confidence: "low" };
    const slope = ssXY / ssXX;
    const r2    = ssYY === 0 ? 0 : (ssXY ** 2) / (ssXX * ssYY);
    const trend = Math.abs(slope) < 0.1 ? "stable" : slope > 0 ? "warming" : "cooling";
    const confidence = r2 >= 0.8 ? "high" : r2 >= 0.5 ? "medium" : "low";
    return { slope, r2, trend, confidence };
  },
};

// ═══════════════════════════════════════════════════════════════════════════
// CHART.JS — ИНИЦИАЛИЗАЦИЯ ГРАФИКОВ
// ═══════════════════════════════════════════════════════════════════════════

/** Храним экземпляры Chart.js для обновления без пересоздания */
const Charts = {};

/** Общие опции для ru-RU */
const chartDefaults = () => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { font: { family: "system-ui, sans-serif" } } },
    tooltip: {
      callbacks: {
        label: (ctx) => ` ${fmtNum(ctx.parsed.y)} ${ctx.dataset.label ?? ""}`,
      },
    },
  },
  scales: {
    x: { ticks: { maxTicksLimit: 8, font: { size: 11 } } },
    y: { ticks: { font: { size: 11 } } },
  },
});

function initForecastChart(labels, tMax, tMin) {
  const ctx = document.getElementById("chart-forecast")?.getContext("2d");
  if (!ctx) return;

  Charts.forecast?.destroy();
  Charts.forecast = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "°C макс",
          data: tMax,
          borderColor: "#ef4444",
          backgroundColor: "rgba(239,68,68,0.15)",
          fill: "+1",
          tension: 0.4,
          pointRadius: 4,
        },
        {
          label: "°C мин",
          data: tMin,
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59,130,246,0.10)",
          fill: false,
          tension: 0.4,
          pointRadius: 4,
        },
      ],
    },
    options: {
      ...chartDefaults(),
      plugins: {
        ...chartDefaults().plugins,
        legend: { display: true },
        title: { display: true, text: "Температура (°C)" },
      },
    },
  });
}

function initHourlyChart(labels, precip, temps) {
  const ctx = document.getElementById("chart-hourly")?.getContext("2d");
  if (!ctx) return;

  Charts.hourly?.destroy();
  Charts.hourly = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: "bar",
          label: "мм",
          data: precip,
          backgroundColor: "rgba(59,130,246,0.6)",
          yAxisID: "yPrecip",
          order: 2,
        },
        {
          type: "line",
          label: "°C",
          data: temps,
          borderColor: "#f97316",
          backgroundColor: "transparent",
          tension: 0.4,
          pointRadius: 2,
          yAxisID: "yTemp",
          order: 1,
        },
      ],
    },
    options: {
      ...chartDefaults(),
      scales: {
        x:       { ticks: { maxTicksLimit: 12, font: { size: 10 } } },
        yTemp:   { position: "left",  title: { display: true, text: "°C" } },
        yPrecip: { position: "right", title: { display: true, text: "мм" },
                   grid: { drawOnChartArea: false } },
      },
    },
  });
}

function updateHourlyChart(labels, precip, temps) {
  if (!Charts.hourly) return initHourlyChart(labels, precip, temps);
  Charts.hourly.data.labels = labels;
  Charts.hourly.data.datasets[0].data = precip;
  Charts.hourly.data.datasets[1].data = temps;
  Charts.hourly.update("active");
}

function initAQIGauge(aqiValue) {
  const ctx = document.getElementById("chart-aqi-gauge")?.getContext("2d");
  if (!ctx) return;

  const v = aqiValue ?? 0;
  const pct = Math.min(v / 150, 1);
  const color = v <= 20 ? "#22c55e" : v <= 40 ? "#84cc16" :
                v <= 60 ? "#eab308" : v <= 80 ? "#f97316" :
                v <= 100 ? "#ef4444" : "#7f1d1d";

  Charts.aqiGauge?.destroy();
  Charts.aqiGauge = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data: [pct, 1 - pct],
        backgroundColor: [color, "rgba(0,0,0,0.08)"],
        borderWidth: 0,
        circumference: 180,
        rotation: 270,
      }],
    },
    options: {
      responsive: true,
      cutout: "72%",
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
}

function initPMChart(labels, pm25, pm10) {
  const ctx = document.getElementById("chart-pm")?.getContext("2d");
  if (!ctx) return;

  Charts.pm?.destroy();
  Charts.pm = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "PM2.5 мкг/м³",
          data: pm25,
          borderColor: "#a855f7",
          backgroundColor: "rgba(168,85,247,0.1)",
          fill: true,
          tension: 0.3,
          pointRadius: 2,
        },
        {
          label: "PM10 мкг/м³",
          data: pm10,
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6,182,212,0.08)",
          fill: true,
          tension: 0.3,
          pointRadius: 2,
        },
      ],
    },
    options: {
      ...chartDefaults(),
      plugins: {
        ...chartDefaults().plugins,
        title: { display: true, text: "PM2.5 / PM10 за 24 ч (мкг/м³)" },
      },
    },
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// РЕНДЕРИНГ СЕКЦИЙ
// ═══════════════════════════════════════════════════════════════════════════

function renderHero(data, tz) {
  const cur = data.current;
  const t   = cur.temperature_2m;
  const rh  = cur.relative_humidity_2m ?? 0;
  const v   = cur.wind_speed_10m ?? 0;
  const p   = cur.precipitation ?? 0;
  const uv0 = data.hourly?.uv_index?.[0] ?? 0;
  const g   = data.hourly?.wind_gusts_10m?.[0] ?? 0;

  UI.setText("hero-temp",   fmtNum(t, 1));
  UI.setText("hero-feels",  `${fmtNum(cur.apparent_temperature, 1)}°C`);
  UI.setText("hero-desc",   WMO_RU[cur.weather_code] ?? "—");
  UI.setText("hero-time",   fmtTime(cur.time, tz));
  UI.setText("metric-wind", `${fmtNum(v, 1)} м/с ${degToDir(data.hourly?.wind_direction_10m?.[0])}`);
  UI.setText("metric-humidity", `${fmtNum(rh, 0)}%`);

  const uvInfo = Indices.uvRisk(uv0);
  UI.setText("metric-uv", uvInfo.label);

  // Видимость (первый элемент hourly → км)
  const vis = data.hourly?.visibility?.[0];
  UI.setText("vis-value", vis != null ? fmtNum(vis / 1000, 1) : "—");

  // Давление
  const pres = data.hourly?.surface_pressure?.[0];
  UI.setText("pressure-value", fmtNum(pres, 0));

  // Comfort Score
  const score = Indices.comfortScore(t ?? 20, rh, v, uv0, p);
  _updateComfortRing(score);

  // Frost / Wind alert бейджи
  const minT = Math.min(...(data.hourly?.temperature_2m?.filter(x => x != null) ?? [0]));
  const frostEl = document.querySelector(".alert--frost");
  const windEl  = document.querySelector(".alert--wind");
  if (frostEl) frostEl.hidden = !(minT < 0);
  if (windEl)  windEl.hidden  = !(v >= 14 || g >= 14);

  // Индексы-карточки
  const dp = Indices.dewPoint(t ?? 20, rh || 1);
  const hi = Indices.heatIndex(t ?? 20, rh);
  const wc = Indices.windChill(t ?? 20, v);
  document.querySelector(".index-card[aria-label='Тепловой индекс'] .index-card__value")
    .firstChild.textContent = `${fmtNum(hi, 1)} `;
  document.querySelector(".index-card[aria-label='Охлаждение ветром'] .index-card__value")
    .firstChild.textContent = `${fmtNum(wc, 1)} `;
  document.querySelector(".index-card[aria-label='Точка росы'] .index-card__value")
    .firstChild.textContent = `${fmtNum(dp, 1)} `;

  UI.ready("hero");
}

function _updateComfortRing(score) {
  const ring     = document.querySelector(".comfort__ring-fill");
  const textEl   = document.querySelector(".comfort__ring-text");
  const descEl   = document.getElementById("comfort-desc");
  const wrapper  = document.querySelector(".comfort");
  if (!ring) return;

  const circumference = 339.29;
  const offset = circumference - (circumference * score / 100);
  ring.setAttribute("stroke-dashoffset", offset.toFixed(2));
  if (textEl) textEl.textContent = Math.round(score);

  const colorCls = score <= 40 ? "comfort--red" : score <= 70 ? "comfort--yellow" : "comfort--green";
  wrapper?.classList.remove("comfort--red","comfort--yellow","comfort--green");
  wrapper?.classList.add(colorCls);

  if (descEl) {
    descEl.textContent = score >= 71 ? "Комфортные условия" :
                         score >= 41 ? "Умеренные условия"  : "Дискомфортные условия";
  }
}

function renderForecast(data, tz) {
  const daily = data.daily;
  if (!daily?.time?.length) { UI.empty("forecast"); return; }

  // Карточки дней
  const cards = document.querySelectorAll(".forecast-card");
  daily.time.forEach((date, i) => {
    const card = cards[i];
    if (!card) return;
    card.querySelector(".forecast-card__day").textContent = fmtWeekday(date, tz);
    card.querySelector(".forecast-card__tmax").textContent = `${fmtNum(daily.temperature_2m_max?.[i], 0)}°`;
    card.querySelector(".forecast-card__tmin").textContent = `${fmtNum(daily.temperature_2m_min?.[i], 0)}°`;
  });

  // График
  const labels = daily.time.map(d => fmtWeekday(d, tz));
  initForecastChart(labels, daily.temperature_2m_max, daily.temperature_2m_min);

  // Тренд
  const means = daily.time.map((_, i) => {
    const hi = daily.temperature_2m_max?.[i] ?? 0;
    const lo = daily.temperature_2m_min?.[i] ?? 0;
    return (hi + lo) / 2;
  });
  _renderTrend(means);

  UI.ready("forecast");
}

function _renderTrend(means) {
  const t = Indices.weatherTrend(means);
  if (!t) return;
  const el = document.querySelector(".trend__text");
  if (!el) return;
  const trendRu  = t.trend === "warming" ? "Теплеет" : t.trend === "cooling" ? "Холодает" : "Стабильно";
  const icon     = t.trend === "warming" ? "↗" : t.trend === "cooling" ? "↘" : "→";
  const confRu   = t.confidence === "high" ? "высокая" : t.confidence === "medium" ? "средняя" : "низкая";
  document.querySelector(".trend__icon").textContent = icon;
  el.innerHTML = `${trendRu} (<strong>${fmtNum(t.slope, 1)}°C/день</strong>), достоверность: ${confRu}`;
}

function renderHourly(data, tz, dayOffset = 0) {
  const hourly = data.hourly;
  if (!hourly?.time?.length) { UI.empty("hourly"); return; }

  // Срезаем данные для выбранного дня
  const todayStr = hourly.time[0].slice(0, 10);
  const targetDate = new Date(todayStr);
  targetDate.setDate(targetDate.getDate() + dayOffset);
  const targetStr = targetDate.toISOString().slice(0, 10);

  const indices = hourly.time.reduce((acc, t, i) => {
    if (t.startsWith(targetStr)) acc.push(i);
    return acc;
  }, []);

  const labels  = indices.map(i => fmtTime(hourly.time[i], tz));
  const temps   = indices.map(i => hourly.temperature_2m?.[i] ?? null);
  const precips = indices.map(i => hourly.precipitation?.[i] ?? 0);
  const uvs     = indices.map(i => hourly.uv_index?.[i] ?? 0);

  updateHourlyChart(labels, precips, temps);
  _renderUVStrip(labels, uvs);

  UI.ready("hourly");
}

function _renderUVStrip(labels, uvs) {
  const container = document.getElementById("uv-cells");
  if (!container) return;
  container.innerHTML = "";
  uvs.forEach((uv, i) => {
    const info = Indices.uvRisk(uv);
    const cell = document.createElement("div");
    cell.className = `uv-cell ${info.cls}`;
    cell.setAttribute("role", "listitem");
    cell.setAttribute("title", `${labels[i]}: УФ ${fmtNum(uv, 1)} — ${info.label}`);
    cell.setAttribute("aria-label", `${labels[i]}: УФ ${fmtNum(uv, 1)}, ${info.label}`);
    cell.textContent = fmtNum(uv, 0);
    container.appendChild(cell);
  });
}

function renderAirQuality(aqData) {
  const h = aqData.hourly;
  if (!h) { UI.empty("aq"); return; }

  const aqi    = h.european_aqi?.find(x => x != null);
  const pm25   = h.pm2_5   ?? [];
  const pm10   = h.pm10    ?? [];
  const times  = h.time    ?? [];

  if (aqi != null) {
    const cat = Indices.aqiCategoryEU(aqi);
    UI.setText("gauge-aqi-val", Math.round(aqi));
    UI.setText("gauge-aqi-cat", cat.label);
    UI.setText("aqi-val", Math.round(aqi));
    UI.setText("aqi-cat", cat.label);
    initAQIGauge(aqi);
  }

  // График PM (последние 24 ч)
  const slice24 = times.length > 24 ? times.length - 24 : 0;
  const labels24 = times.slice(slice24).map(t => t.slice(11, 16));
  initPMChart(labels24, pm25.slice(slice24), pm10.slice(slice24));

  // Мини-карточки газов (первое не-null значение)
  UI.setText("aq-co",  fmtNum(h.carbon_monoxide?.find(x => x != null), 0));
  UI.setText("aq-no2", fmtNum(h.nitrogen_dioxide?.find(x => x != null), 1));
  UI.setText("aq-o3",  fmtNum(h.ozone?.find(x => x != null), 0));

  UI.ready("aq");
}

// ═══════════════════════════════════════════════════════════════════════════
// ПОИСК ГОРОДА
// ═══════════════════════════════════════════════════════════════════════════

function initSearch() {
  const input    = document.getElementById("city-search");
  const dropdown = document.getElementById("search-results");
  if (!input || !dropdown) return;

  const doSearch = debounce(async (q) => {
    if (q.trim().length < 2) {
      dropdown.innerHTML = "";
      dropdown.hidden = true;
      input.setAttribute("aria-expanded", "false");
      return;
    }
    try {
      const results = await fetchGeocoding(q);
      _renderSearchDropdown(results, dropdown, input);
    } catch {
      dropdown.innerHTML = "<li class='search__item search__item--error'>Ошибка поиска</li>";
      dropdown.hidden = false;
    }
  }, 300);

  input.addEventListener("input", (e) => doSearch(e.target.value));

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      dropdown.hidden = true;
      input.setAttribute("aria-expanded", "false");
    }
  });

  document.addEventListener("click", (e) => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.hidden = true;
      input.setAttribute("aria-expanded", "false");
    }
  });
}

function _renderSearchDropdown(results, dropdown, input) {
  dropdown.innerHTML = "";
  if (!results.length) {
    dropdown.innerHTML = "<li class='search__item search__item--empty'>Ничего не найдено</li>";
    dropdown.hidden = false;
    input.setAttribute("aria-expanded", "true");
    return;
  }
  results.slice(0, 5).forEach(r => {
    const li = document.createElement("li");
    li.className = "search__item";
    li.setAttribute("role", "option");
    li.setAttribute("tabindex", "0");
    const label = [r.name, r.admin1, r.country_code].filter(Boolean).join(", ");
    li.textContent = label;
    li.addEventListener("click", () => {
      input.value = r.name;
      dropdown.hidden = true;
      input.setAttribute("aria-expanded", "false");
      loadLocation(r.latitude, r.longitude, r.timezone ?? "auto", r.name);
    });
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter") li.click();
    });
    dropdown.appendChild(li);
  });
  dropdown.hidden = false;
  input.setAttribute("aria-expanded", "true");
}

// ═══════════════════════════════════════════════════════════════════════════
// ГЕОЛОКАЦИЯ
// ═══════════════════════════════════════════════════════════════════════════

function initGeolocation() {
  const btn = document.getElementById("geo-btn");
  if (!btn || !navigator.geolocation) {
    btn?.setAttribute("disabled", "");
    return;
  }
  btn.addEventListener("click", () => {
    btn.disabled = true;
    btn.setAttribute("aria-label", "Определение местоположения...");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        btn.disabled = false;
        btn.setAttribute("aria-label", "Определить местоположение автоматически");
        await loadLocation(lat, lon, "auto", "Моё местоположение");
      },
      () => {
        btn.disabled = false;
        btn.setAttribute("aria-label", "Определить местоположение автоматически");
      },
      { timeout: 10_000, maximumAge: 60_000 }
    );
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// ЗАГРУЗКА ДАННЫХ ДЛЯ ЛОКАЦИИ
// ═══════════════════════════════════════════════════════════════════════════

async function loadLocation(lat, lon, timezone = "auto", cityName = "") {
  ["hero","forecast","hourly","aq","indices"].forEach(s => UI.loading(s));

  try {
    const [forecastResult, aqResult] = await Promise.allSettled([
      fetchForecast(lat, lon, timezone),
      fetchAirQuality(lat, lon),
    ]);

    if (forecastResult.status === "fulfilled") {
      const { data, stale, staleAt } = forecastResult.value;
      if (stale) UI.stale(staleAt);

      // Обновляем заголовок
      const heading = document.getElementById("current-heading");
      if (heading && cityName) heading.textContent = cityName;

      renderHero(data, timezone);
      renderForecast(data, timezone);
      renderHourly(data, timezone, 0);
      UI.ready("indices");
    } else {
      UI.error("hero",     forecastResult.reason);
      UI.error("forecast", forecastResult.reason);
      UI.error("hourly",   forecastResult.reason);
    }

    if (aqResult.status === "fulfilled") {
      renderAirQuality(aqResult.value.data);
      if (aqResult.value.stale) UI.stale(aqResult.value.staleAt);
    } else {
      UI.empty("aq");
    }

  } catch (err) {
    ["hero","forecast","hourly","aq","indices"].forEach(s => UI.error(s, err));
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// ПОЧАСОВЫЕ ФИЛЬТРЫ (Сегодня / Завтра / Послезавтра)
// ═══════════════════════════════════════════════════════════════════════════

function initHourlyFilters() {
  const btns = document.querySelectorAll(".filter-btn");
  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      btns.forEach(b => {
        b.classList.remove("filter-btn--active");
        b.setAttribute("aria-pressed", "false");
      });
      btn.classList.add("filter-btn--active");
      btn.setAttribute("aria-pressed", "true");
      const dayOffset = parseInt(btn.dataset.day ?? "0", 10);
      // Берём данные из текущего состояния
      _rerenderHourly(dayOffset);
    });
  });
}

let _currentForecastData = null;
let _currentTimezone     = DEFAULT.timezone;

function _rerenderHourly(dayOffset) {
  if (!_currentForecastData) return;
  renderHourly(_currentForecastData, _currentTimezone, dayOffset);
}

// ═══════════════════════════════════════════════════════════════════════════
// ПЕРЕКЛЮЧАТЕЛЬ ГОРОДОВ (Snapshot mode)
// ═══════════════════════════════════════════════════════════════════════════

function initCitySwitcher() {
  const btns = document.querySelectorAll(".city-switcher__btn");
  if (!btns.length || typeof SERVER_DATA === "undefined") return;

  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      btns.forEach(b => {
        b.classList.remove("city-switcher__btn--active");
        b.setAttribute("aria-pressed", "false");
      });
      btn.classList.add("city-switcher__btn--active");
      btn.setAttribute("aria-pressed", "true");

      const idx = parseInt(btn.dataset.locationIdx ?? "0", 10);
      const loc = SERVER_DATA[idx];
      if (!loc) return;
      _renderFromSnapshot(loc);
    });
  });
}

function _renderFromSnapshot(loc) {
  // Snapshot mode: рендерим из уже загруженных серверных данных
  const heading = document.getElementById("current-heading");
  if (heading) heading.textContent = loc.name ?? "—";

  // Данные в server-формате → конвертируем для рендер-функций
  const syntheticForecast = {
    current: loc.current ?? {},
    hourly:  loc.hourly  ?? {},
    daily:   loc.daily   ?? {},
  };
  const tz = loc.timezone ?? "UTC";
  _currentForecastData = syntheticForecast;
  _currentTimezone     = tz;

  renderHero(syntheticForecast, tz);
  renderForecast(syntheticForecast, tz);
  renderHourly(syntheticForecast, tz, 0);

  if (loc.air_quality?.hourly) {
    renderAirQuality({ hourly: loc.air_quality.hourly });
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// КНОПКА ОБНОВЛЕНИЯ (stale-banner)
// ═══════════════════════════════════════════════════════════════════════════

function initRefreshBtn() {
  document.getElementById("refresh-btn")?.addEventListener("click", () => {
    loadLocation(DEFAULT.lat, DEFAULT.lon, DEFAULT.timezone, DEFAULT.city);
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// INTERSECTION OBSERVER — анимации появления секций
// ═══════════════════════════════════════════════════════════════════════════

function initIntersectionObserver() {
  if (!("IntersectionObserver" in window)) return;
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("section--visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1 }
  );
  document.querySelectorAll("[data-observe]").forEach(el => observer.observe(el));
}

// ═══════════════════════════════════════════════════════════════════════════
// SNAPSHOT TIME — локализованный вывод в footer
// ═══════════════════════════════════════════════════════════════════════════

function initSnapshotTime() {
  const el = document.getElementById("snapshot-time");
  if (!el) return;
  const iso = el.getAttribute("datetime");
  if (!iso) return;
  el.textContent = new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone:  "Europe/Moscow",
  }).format(new Date(iso)) + " МСК";
}

// ═══════════════════════════════════════════════════════════════════════════
// ИНИЦИАЛИЗАЦИЯ
// ═══════════════════════════════════════════════════════════════════════════

async function init() {
  initIntersectionObserver();
  initSearch();
  initGeolocation();
  initHourlyFilters();
  initRefreshBtn();
  initSnapshotTime();
  initCitySwitcher();

  if (USE_LIVE) {
    // Live mode: загружаем живые данные для дефолтной локации
    await loadLocation(DEFAULT.lat, DEFAULT.lon, DEFAULT.timezone, DEFAULT.city);
  } else {
    // Snapshot mode: данные из data.js
    if (typeof WEATHER_SNAPSHOT !== "undefined" && WEATHER_SNAPSHOT.locations?.length) {
      const loc = WEATHER_SNAPSHOT.locations[0];
      _currentForecastData = { current: loc.current, hourly: loc.hourly, daily: loc.daily };
      _currentTimezone     = loc.timezone ?? "UTC";
      _renderFromSnapshot(loc);
    }
  }
}

// Запуск после загрузки DOM
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}