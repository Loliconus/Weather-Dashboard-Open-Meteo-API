/**
 * Weather Dashboard — Snapshot mode
 * ES2022+ Vanilla JS, без фреймворков
 *
 * Данные: WEATHER_SNAPSHOT из /assets/data.js (генерируется Python-пайплайном)
 * Числа: Intl.NumberFormat("ru-RU")
 * Даты:  Intl.DateTimeFormat("ru-RU", { timeZone })
 */

"use strict";

// ═══════════════════════════════════════════════════════════════════════════
// КОНСТАНТЫ
// ═══════════════════════════════════════════════════════════════════════════

const WMO_RU = {
  0:  "Ясно",
  1:  "Преимущественно ясно",
  2:  "Переменная облачность",
  3:  "Пасмурно",
  45: "Туман",
  48: "Изморозь",
  51: "Лёгкая морось",
  53: "Умеренная морось",
  55: "Сильная морось",
  61: "Слабый дождь",
  63: "Умеренный дождь",
  65: "Сильный дождь",
  71: "Слабый снег",
  73: "Умеренный снег",
  75: "Сильный снег",
  77: "Крупа",
  80: "Слабый ливень",
  81: "Умеренный ливень",
  82: "Сильный ливень",
  85: "Слабый снегопад",
  86: "Сильный снегопад",
  95: "Гроза",
  96: "Гроза с градом",
  99: "Сильная гроза с градом",
};

// ═══════════════════════════════════════════════════════════════════════════
// УТИЛИТЫ
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Форматирует число в ru-RU стиле.
 * @param {number|null|undefined} v
 * @param {number} decimals
 * @param {string} fallback
 * @returns {string}
 */
const fmtNum = (v, decimals = 1, fallback = "—") => {
  if (v == null || Number.isNaN(v)) return fallback;
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(v);
};

/**
 * Форматирует ISO-дату с учётом часового пояса.
 * @param {string} isoStr
 * @param {string} tz  IANA timezone
 * @param {Intl.DateTimeFormatOptions} opts
 * @returns {string}
 */
const fmtDate = (isoStr, tz, opts) => {
  if (!isoStr) return "—";
  try {
    return new Intl.DateTimeFormat("ru-RU", { timeZone: tz, ...opts })
      .format(new Date(isoStr));
  } catch {
    return isoStr;
  }
};

/** Короткий день недели + дата: "пн, 9 июн." */
const fmtWeekday = (isoDate, tz) =>
  fmtDate(`${isoDate}T12:00:00`, tz, {
    weekday: "short",
    day:     "numeric",
    month:   "short",
  });

/** Время ЧЧ:ММ */
const fmtTime = (isoStr, tz) =>
  fmtDate(isoStr, tz, { hour: "2-digit", minute: "2-digit" });

/** Градусы → сторона света (8 румбов, ru-RU) */
const degToDir = (deg) => {
  if (deg == null) return "—";
  const dirs = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"];
  return dirs[Math.round(deg / 45) % 8];
};

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// ═══════════════════════════════════════════════════════════════════════════
// UI-ХЕЛПЕРЫ
// ═══════════════════════════════════════════════════════════════════════════

const UI = {
  /** Показывает skeleton, скрывает контент. */
  loading(sectionId) {
    document.getElementById(`${sectionId}-skeleton`)?.removeAttribute("hidden");
    document.getElementById(`${sectionId}-content`)?.setAttribute("hidden", "");
  },

  /** Скрывает skeleton, показывает контент. */
  ready(sectionId) {
    document.getElementById(`${sectionId}-skeleton`)?.setAttribute("hidden", "");
    document.getElementById(`${sectionId}-content`)?.removeAttribute("hidden");
  },

  /** Показывает пустое состояние (нет данных). */
  empty(sectionId) {
    UI.ready(sectionId);
    document.getElementById(`${sectionId}-empty`)?.removeAttribute("hidden");
  },

  setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text ?? "—";
  },

  setHTML(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  },
};

// ═══════════════════════════════════════════════════════════════════════════
// РАСЧЁТ ИНДЕКСОВ
// ═══════════════════════════════════════════════════════════════════════════

const Indices = {
  /**
   * Тепловой индекс Ротча (°C).
   * Применяется при t ≥ 27 °C и rh ≥ 40 %.
   */
  heatIndex(t, rh) {
    if (t < 27 || rh < 40) return t;
    const tf = t * 9 / 5 + 32;
    const hi =
      -42.379
      + 2.04901523  * tf
      + 10.14333127 * rh
      - 0.22475541  * tf * rh
      - 0.00683783  * tf * tf
      - 0.05481717  * rh * rh
      + 0.00122874  * tf * tf * rh
      + 0.00085282  * tf * rh * rh
      - 0.00000199  * tf * tf * rh * rh;
    return (hi - 32) * 5 / 9;
  },

  /**
   * Индекс охлаждения ветром JAG/TI (°C).
   * Применяется при t ≤ 10 °C и v ≥ 1,3 м/с.
   */
  windChill(t, v) {
    if (t > 10 || v < 1.3) return t;
    const vk = v * 3.6; // м/с → км/ч
    return 13.12 + 0.6215 * t - 11.37 * vk ** 0.16 + 0.3965 * t * vk ** 0.16;
  },

  /**
   * Точка росы по формуле Августа-Магнуса (°C).
   */
  dewPoint(t, rh) {
    if (rh <= 0) return t;
    const a = 17.625;
    const b = 243.04;
    const g = Math.log(rh / 100) + (a * t) / (b + t);
    return (b * g) / (a - g);
  },

  /**
   * Категория УФ-индекса (ВОЗ).
   * @returns {{ label: string, cls: string }}
   */
  uvRisk(uv) {
    if (uv <= 2)  return { label: "Низкий",        cls: "uv--low"       };
    if (uv <= 5)  return { label: "Умеренный",      cls: "uv--moderate"  };
    if (uv <= 7)  return { label: "Высокий",        cls: "uv--high"      };
    if (uv <= 10) return { label: "Очень высокий",  cls: "uv--very-high" };
    return               { label: "Экстремальный",  cls: "uv--extreme"   };
  },

  /**
   * Категория European AQI (EEA).
   * @returns {{ label: string, cls: string }}
   */
  aqiCategoryEU(aqi) {
    if (aqi <= 20)  return { label: "Хороший",             cls: "aqi--good"           };
    if (aqi <= 40)  return { label: "Удовлетворительный",  cls: "aqi--fair"           };
    if (aqi <= 60)  return { label: "Умеренный",           cls: "aqi--moderate"       };
    if (aqi <= 80)  return { label: "Плохой",              cls: "aqi--poor"           };
    if (aqi <= 100) return { label: "Очень плохой",        cls: "aqi--very-poor"      };
    return                 { label: "Крайне плохой",       cls: "aqi--extremely-poor" };
  },

  /**
   * Индекс комфорта [0–100].
   * Веса: температура 35 %, влажность 25 %, ветер 20 %, УФ 10 %, осадки 10 %.
   */
  comfortScore(t, rh, v, uv, precip) {
    const lin = (val, min, max) => clamp((val - min) / (max - min) * 100, 0, 100);

    const tSub =
      t >= 18 && t <= 24 ? 100 :
      t < 18              ? lin(t, -10, 18) :
                            lin(38 - (t - 24), 0, 14);

    const rhSub =
      rh >= 40 && rh <= 60 ? 100 :
      rh < 40               ? lin(rh, 10, 40) :
                              lin(90 - (rh - 60), 0, 30);

    const vSub    = v      <= 3 ? 100 : lin(15 - (v - 3),       0, 12);
    const uvSub   = uv     <= 2 ? 100 : lin(11 - (uv - 2),      0,  9);
    const precipSub = precip <= 0 ? 100 : lin(10 - precip,      0, 10);

    return clamp(
      0.35 * tSub + 0.25 * rhSub + 0.20 * vSub + 0.10 * uvSub + 0.10 * precipSub,
      0, 100,
    );
  },

  /**
   * Линейный тренд температур методом МНК.
   * @param {number[]} means - среднесуточные температуры
   * @returns {{ slope: number, r2: number, trend: string, confidence: string }|null}
   */
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
    const trend =
      Math.abs(slope) < 0.1 ? "stable" :
      slope > 0              ? "warming" : "cooling";
    const confidence = r2 >= 0.8 ? "high" : r2 >= 0.5 ? "medium" : "low";
    return { slope, r2, trend, confidence };
  },
};

// ═══════════════════════════════════════════════════════════════════════════
// CHART.JS — ГРАФИКИ
// ═══════════════════════════════════════════════════════════════════════════

/** Экземпляры Chart.js: обновляем без пересоздания. */
const Charts = {};

/** Базовые опции (шрифты, tooltip в ru-RU). */
const chartDefaults = () => ({
  responsive:          true,
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
    x: { ticks: { maxTicksLimit: 8,  font: { size: 11 } } },
    y: { ticks: { font: { size: 11 } } },
  },
});

/**
 * График 7-дневного прогноза температур (line, две серии).
 * @param {string[]} labels
 * @param {number[]} tMax
 * @param {number[]} tMin
 */
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
          label:           "°C макс",
          data:            tMax,
          borderColor:     "#ef4444",
          backgroundColor: "rgba(239,68,68,0.15)",
          fill:            "+1",
          tension:         0.4,
          pointRadius:     4,
        },
        {
          label:           "°C мин",
          data:            tMin,
          borderColor:     "#3b82f6",
          backgroundColor: "rgba(59,130,246,0.10)",
          fill:            false,
          tension:         0.4,
          pointRadius:     4,
        },
      ],
    },
    options: {
      ...chartDefaults(),
      plugins: {
        ...chartDefaults().plugins,
        title: { display: true, text: "Температура (°C)" },
      },
    },
  });
}

/**
 * Почасовой график: осадки (bar) + температура (line), двойная ось Y.
 * @param {string[]} labels
 * @param {number[]} precip
 * @param {number[]} temps
 */
function initHourlyChart(labels, precip, temps) {
  const ctx = document.getElementById("chart-hourly")?.getContext("2d");
  if (!ctx) return;
  Charts.hourly?.destroy();
  Charts.hourly = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type:            "bar",
          label:           "мм",
          data:            precip,
          backgroundColor: "rgba(59,130,246,0.6)",
          yAxisID:         "yPrecip",
          order:           2,
        },
        {
          type:            "line",
          label:           "°C",
          data:            temps,
          borderColor:     "#f97316",
          backgroundColor: "transparent",
          tension:         0.4,
          pointRadius:     2,
          yAxisID:         "yTemp",
          order:           1,
        },
      ],
    },
    options: {
      ...chartDefaults(),
      scales: {
        x:       { ticks: { maxTicksLimit: 12, font: { size: 10 } } },
        yTemp:   { position: "left",  title: { display: true, text: "°C" } },
        yPrecip: {
          position: "right",
          title:    { display: true, text: "мм" },
          grid:     { drawOnChartArea: false },
        },
      },
    },
  });
}

/** Обновляет почасовой график без пересоздания. */
function updateHourlyChart(labels, precip, temps) {
  if (!Charts.hourly) return initHourlyChart(labels, precip, temps);
  Charts.hourly.data.labels             = labels;
  Charts.hourly.data.datasets[0].data   = precip;
  Charts.hourly.data.datasets[1].data   = temps;
  Charts.hourly.update("active");
}

/**
 * Полукруговой gauge AQI (doughnut 180°).
 * @param {number} aqiValue
 */
function initAQIGauge(aqiValue) {
  const ctx = document.getElementById("chart-aqi-gauge")?.getContext("2d");
  if (!ctx) return;
  const v   = aqiValue ?? 0;
  const pct = Math.min(v / 150, 1);
  const color =
    v <= 20  ? "#22c55e" :
    v <= 40  ? "#84cc16" :
    v <= 60  ? "#eab308" :
    v <= 80  ? "#f97316" :
    v <= 100 ? "#ef4444" :
               "#7f1d1d";

  Charts.aqiGauge?.destroy();
  Charts.aqiGauge = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data:            [pct, 1 - pct],
        backgroundColor: [color, "rgba(0,0,0,0.08)"],
        borderWidth:     0,
        circumference:   180,
        rotation:        270,
      }],
    },
    options: {
      responsive: true,
      cutout:     "72%",
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
}

/**
 * График PM2.5 / PM10 за 24 ч.
 * @param {string[]} labels
 * @param {number[]} pm25
 * @param {number[]} pm10
 */
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
          label:           "PM2.5 мкг/м³",
          data:            pm25,
          borderColor:     "#a855f7",
          backgroundColor: "rgba(168,85,247,0.1)",
          fill:            true,
          tension:         0.3,
          pointRadius:     2,
        },
        {
          label:           "PM10 мкг/м³",
          data:            pm10,
          borderColor:     "#06b6d4",
          backgroundColor: "rgba(6,182,212,0.08)",
          fill:            true,
          tension:         0.3,
          pointRadius:     2,
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

/**
 * Hero-секция: текущие условия + индексы + комфорт.
 * @param {{ current: object, hourly: object }} data
 * @param {string} tz  IANA timezone
 */
function renderHero(data, tz) {
  const cur = data.current ?? {};

  // Текущие значения (имена полей = Open-Meteo)
  const t      = cur.temperature_2m       ?? 0;
  const rh     = cur.relative_humidity_2m ?? 0;
  const v      = cur.wind_speed_10m       ?? 0;
  const precip = cur.precipitation        ?? 0;

  // Первые элементы hourly (индекс 0 = текущий час)
  const uv0   = data.hourly?.uv_index?.[0]          ?? 0;
  const gusts = data.hourly?.wind_gusts_10m?.[0]    ?? 0;
  const windDir = data.hourly?.wind_direction_10m?.[0] ?? null;

  // Основные метрики
  UI.setText("hero-temp",        fmtNum(t, 1));
  UI.setText("hero-feels",       `${fmtNum(cur.apparent_temperature, 1)}°C`);
  UI.setText("hero-desc",        WMO_RU[cur.weather_code] ?? "—");
  UI.setText("hero-time",        fmtTime(cur.time, tz));
  UI.setText("metric-wind",      `${fmtNum(v, 1)} м/с ${degToDir(windDir)}`);
  UI.setText("metric-humidity",  `${fmtNum(rh, 0)}%`);
  UI.setText("metric-uv",        Indices.uvRisk(uv0).label);

  // Видимость (м → км)
  const vis = data.hourly?.visibility?.[0];
  UI.setText("vis-value", vis != null ? fmtNum(vis / 1000, 1) : "—");

  // Давление
  UI.setText("pressure-value", fmtNum(data.hourly?.surface_pressure?.[0], 0));

  // Алерты: мороз / сильный ветер
  const minT = Math.min(
    ...(data.hourly?.temperature_2m?.filter((x) => x != null) ?? [0]),
  );
  document.querySelector(".alert--frost")?.toggleAttribute("hidden", !(minT < 0));
  document.querySelector(".alert--wind")?.toggleAttribute("hidden", !(v >= 14 || gusts >= 14));

  // Comfort Score → кольцо
  _updateComfortRing(Indices.comfortScore(t, rh, v, uv0, precip));

  // Карточки индексов
  _setIndexCard("Тепловой индекс",    fmtNum(Indices.heatIndex(t, rh), 1));
  _setIndexCard("Охлаждение ветром",  fmtNum(Indices.windChill(t, v),  1));
  _setIndexCard("Точка росы",         fmtNum(Indices.dewPoint(t, rh),  1));

  UI.ready("hero");
}

/**
 * Обновляет первый текстовый узел значения в карточке индекса.
 * Ожидает разметку: .index-card[aria-label="…"] > .index-card__value
 */
function _setIndexCard(label, value) {
  const card = document.querySelector(`.index-card[aria-label="${label}"]`);
  const valueEl = card?.querySelector(".index-card__value");
  if (valueEl?.firstChild) valueEl.firstChild.textContent = `${value} `;
}

/** Обновляет SVG-кольцо Comfort Score и его CSS-класс. */
function _updateComfortRing(score) {
  const CIRCUMFERENCE = 339.29; // 2π × r54
  const ring    = document.querySelector(".comfort__ring-fill");
  const textEl  = document.querySelector(".comfort__ring-text");
  const descEl  = document.getElementById("comfort-desc");
  const wrapper = document.querySelector(".comfort");

  if (!ring) return;

  ring.setAttribute(
    "stroke-dashoffset",
    (CIRCUMFERENCE - (CIRCUMFERENCE * score) / 100).toFixed(2),
  );
  if (textEl) textEl.textContent = Math.round(score);

  const cls =
    score <= 40 ? "comfort--red" :
    score <= 70 ? "comfort--yellow" :
                  "comfort--green";

  wrapper?.classList.remove("comfort--red", "comfort--yellow", "comfort--green");
  wrapper?.classList.add(cls);

  if (descEl) {
    descEl.textContent =
      score >= 71 ? "Комфортные условия"    :
      score >= 41 ? "Умеренные условия"     :
                    "Дискомфортные условия";
  }
}

/**
 * 7-дневный прогноз: карточки дней + график + тренд.
 * @param {{ daily: object }} data
 * @param {string} tz
 */
function renderForecast(data, tz) {
  const daily = data.daily;
  if (!daily?.time?.length) { UI.empty("forecast"); return; }

  // Карточки
  document.querySelectorAll(".forecast-card").forEach((card, i) => {
    const date = daily.time[i];
    if (!date) return;
    card.querySelector(".forecast-card__day")
      .textContent = fmtWeekday(date, tz);
    card.querySelector(".forecast-card__tmax")
      .textContent = `${fmtNum(daily.temperature_2m_max?.[i], 0)}°`;
    card.querySelector(".forecast-card__tmin")
      .textContent = `${fmtNum(daily.temperature_2m_min?.[i], 0)}°`;
  });

  // График
  initForecastChart(
    daily.time.map((d) => fmtWeekday(d, tz)),
    daily.temperature_2m_max,
    daily.temperature_2m_min,
  );

  // Тренд по среднесуточным
  const means = daily.time.map((_, i) => (
    ((daily.temperature_2m_max?.[i] ?? 0) + (daily.temperature_2m_min?.[i] ?? 0)) / 2
  ));
  _renderTrend(means);

  UI.ready("forecast");
}

/** Обновляет блок тренда температур. */
function _renderTrend(means) {
  const t = Indices.weatherTrend(means);
  if (!t) return;

  const icon   = t.trend === "warming" ? "↗" : t.trend === "cooling" ? "↘" : "→";
  const textRu = t.trend === "warming" ? "Теплеет" : t.trend === "cooling" ? "Холодает" : "Стабильно";
  const confRu = t.confidence === "high" ? "высокая" : t.confidence === "medium" ? "средняя" : "низкая";

  const iconEl = document.querySelector(".trend__icon");
  const textEl = document.querySelector(".trend__text");
  if (iconEl) iconEl.textContent = icon;
  if (textEl) textEl.innerHTML =
    `${textRu} (<strong>${fmtNum(t.slope, 1)}°C/день</strong>), достоверность: ${confRu}`;
}

/**
 * Почасовой график + УФ-полоска для выбранного дня.
 * @param {{ hourly: object }} data
 * @param {string} tz
 * @param {number} dayOffset  0 = сегодня, 1 = завтра, 2 = послезавтра
 */
function renderHourly(data, tz, dayOffset = 0) {
  const hourly = data.hourly;
  if (!hourly?.time?.length) { UI.empty("hourly"); return; }

  // Определяем строку целевой даты (YYYY-MM-DD)
  const baseDate = new Date(`${hourly.time[0].slice(0, 10)}T12:00:00`);
  baseDate.setDate(baseDate.getDate() + dayOffset);
  const targetStr = baseDate.toISOString().slice(0, 10);

  // Индексы часов целевого дня
  const idxs = hourly.time.reduce((acc, t, i) => {
    if (t.startsWith(targetStr)) acc.push(i);
    return acc;
  }, []);

  const labels = idxs.map((i) => fmtTime(hourly.time[i], tz));
  const temps  = idxs.map((i) => hourly.temperature_2m?.[i]  ?? null);
  const precip = idxs.map((i) => hourly.precipitation?.[i]   ?? 0);
  const uvs    = idxs.map((i) => hourly.uv_index?.[i]        ?? 0);

  updateHourlyChart(labels, precip, temps);
  _renderUVStrip(labels, uvs);

  UI.ready("hourly");
}

/** УФ-полоска (цветные ячейки по часам). */
function _renderUVStrip(labels, uvs) {
  const container = document.getElementById("uv-cells");
  if (!container) return;
  container.innerHTML = "";
  uvs.forEach((uv, i) => {
    const info = Indices.uvRisk(uv);
    const cell = document.createElement("div");
    cell.className = `uv-cell ${info.cls}`;
    cell.setAttribute("role",       "listitem");
    cell.setAttribute("title",      `${labels[i]}: УФ ${fmtNum(uv, 1)} — ${info.label}`);
    cell.setAttribute("aria-label", `${labels[i]}: УФ ${fmtNum(uv, 1)}, ${info.label}`);
    cell.textContent = fmtNum(uv, 0);
    container.appendChild(cell);
  });
}

/**
 * Секция качества воздуха: gauge, PM-график, газы.
 * @param {{ hourly: object }} aqData
 */
function renderAirQuality(aqData) {
  const h = aqData?.hourly;
  if (!h) { UI.empty("aq"); return; }

  const aqi   = h.european_aqi?.find((x) => x != null);
  const times = h.time ?? [];
  const pm25  = h.pm2_5 ?? [];
  const pm10  = h.pm10  ?? [];

  if (aqi != null) {
    const cat = Indices.aqiCategoryEU(aqi);
    UI.setText("gauge-aqi-val", Math.round(aqi));
    UI.setText("gauge-aqi-cat", cat.label);
    UI.setText("aqi-val",       Math.round(aqi));
    UI.setText("aqi-cat",       cat.label);
    initAQIGauge(aqi);
  }

  // PM за последние 24 ч
  const slice24 = Math.max(0, times.length - 24);
  initPMChart(
    times.slice(slice24).map((t) => t.slice(11, 16)),
    pm25.slice(slice24),
    pm10.slice(slice24),
  );

  // Газы: первое ненулевое значение
  UI.setText("aq-co",  fmtNum(h.carbon_monoxide?.find((x) => x != null),   0));
  UI.setText("aq-no2", fmtNum(h.nitrogen_dioxide?.find((x) => x != null),  1));
  UI.setText("aq-o3",  fmtNum(h.ozone?.find((x) => x != null),             0));

  UI.ready("aq");
}

// ═══════════════════════════════════════════════════════════════════════════
// ПЕРЕКЛЮЧЕНИЕ ГОРОДОВ
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Текущее состояние рендера — нужно для перерисовки почасового
 * при смене дня без перезагрузки данных.
 * @type {{ forecast: object|null, tz: string }}
 */
const State = {
  forecast: null,
  tz:       "Europe/Moscow",
};

/**
 * Рендерит все секции из одного объекта локации (Snapshot mode).
 * @param {object} loc - элемент WEATHER_SNAPSHOT.locations
 */
function renderLocation(loc) {
  const tz = loc.timezone ?? "UTC";

  // Обновляем State для почасовых фильтров
  State.forecast = {
    current: loc.current ?? {},
    hourly:  loc.hourly  ?? {},
    daily:   loc.daily   ?? {},
  };
  State.tz = tz;

  // Заголовок
  const heading = document.getElementById("current-heading");
  if (heading) heading.textContent = loc.name ?? "—";

  renderHero(State.forecast, tz);
  renderForecast(State.forecast, tz);
  renderHourly(State.forecast, tz, 0);

  if (loc.air_quality?.hourly) {
    renderAirQuality({ hourly: loc.air_quality.hourly });
  }

  // Сбрасываем активный фильтр дня на «Сегодня»
  _resetDayFilter();
}

/** Инициализирует переключатель городов. */
function initCitySwitcher() {
  document.querySelectorAll(".city-switcher__btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".city-switcher__btn").forEach((b) => {
        b.classList.remove("city-switcher__btn--active");
        b.setAttribute("aria-pressed", "false");
      });
      btn.classList.add("city-switcher__btn--active");
      btn.setAttribute("aria-pressed", "true");

      const idx = parseInt(btn.dataset.locationIdx ?? "0", 10);
      const loc = WEATHER_SNAPSHOT.locations[idx];
      if (loc) renderLocation(loc);
    });
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// ФИЛЬТРЫ ПОЧАСОВОГО ПРОГНОЗА (Сегодня / Завтра / Послезавтра)
// ═══════════════════════════════════════════════════════════════════════════

function initHourlyFilters() {
  document.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach((b) => {
        b.classList.remove("filter-btn--active");
        b.setAttribute("aria-pressed", "false");
      });
      btn.classList.add("filter-btn--active");
      btn.setAttribute("aria-pressed", "true");

      if (State.forecast) {
        renderHourly(State.forecast, State.tz, parseInt(btn.dataset.day ?? "0", 10));
      }
    });
  });
}

/** Сбрасывает визуальный активный день на «Сегодня» (dayOffset = 0). */
function _resetDayFilter() {
  document.querySelectorAll(".filter-btn").forEach((btn) => {
    const isToday = (btn.dataset.day ?? "0") === "0";
    btn.classList.toggle("filter-btn--active", isToday);
    btn.setAttribute("aria-pressed", isToday ? "true" : "false");
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// ВСПОМОГАТЕЛЬНЫЕ ИНИЦИАЛИЗАТОРЫ
// ═══════════════════════════════════════════════════════════════════════════

/** IntersectionObserver: анимация появления секций при скролле. */
function initIntersectionObserver() {
  if (!("IntersectionObserver" in window)) return;
  const observer = new IntersectionObserver(
    (entries) => entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add("section--visible");
        observer.unobserve(e.target);
      }
    }),
    { threshold: 0.1 },
  );
  document.querySelectorAll("[data-observe]").forEach((el) => observer.observe(el));
}

/**
 * Локализует <time id="snapshot-time"> в footer.
 * Python записывает datetime в атрибут datetime="ISO8601".
 */
function initSnapshotTime() {
  const el  = document.getElementById("snapshot-time");
  const iso = el?.getAttribute("datetime");
  if (!el || !iso) return;
  el.textContent =
    new Intl.DateTimeFormat("ru-RU", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone:  "Europe/Moscow",
    }).format(new Date(iso)) + " МСК";
}

// ═══════════════════════════════════════════════════════════════════════════
// ТОЧКА ВХОДА
// ═══════════════════════════════════════════════════════════════════════════

function init() {
  // Проверяем наличие снапшота
  if (typeof WEATHER_SNAPSHOT === "undefined" || !WEATHER_SNAPSHOT.locations?.length) {
    console.error("WEATHER_SNAPSHOT не найден или пуст. Проверьте /assets/data.js.");
    return;
  }

  initIntersectionObserver();
  initHourlyFilters();
  initSnapshotTime();
  initCitySwitcher();

  // Рендерим первую локацию
  renderLocation(WEATHER_SNAPSHOT.locations[0]);
}

// Запускаем после готовности DOM
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}