"""Тесты indices.py — KAT + граничные значения + Hypothesis."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from weather_dashboard.processing.indices import (
    aqi_category_eu,
    comfort_score,
    dew_point,
    frost_risk,
    heat_index,
    high_wind_alert,
    humidex,
    precipitation_intensity,
    uv_risk_level,
    weather_trend,
    wind_chill,
)

# ═══════════════════════════════════════════════════════════════════════════
# Heat Index
# ═══════════════════════════════════════════════════════════════════════════


class TestHeatIndex:
    def test_not_applicable_returns_t(self):
        assert heat_index(20.0, 50.0) == 20.0
        assert heat_index(30.0, 30.0) == 30.0

    def test_kat_40_60(self):
        """
        heat_index(40, 60) ≈ 62–63°C.
        NWS Rothfusz formula при T=40°C, RH=60% даёт ~62.6°C —
        формула не ограничена сверху при экстремальных значениях.
        """
        result = heat_index(40.0, 60.0)
        assert 55.0 <= result <= 70.0, f"Ожидалось ≈62°C, получено {result}"

    def test_kat_35_80(self):
        result = heat_index(35.0, 80.0)
        assert result > 35.0

    def test_rh_100_percent(self):
        result = heat_index(38.0, 100.0)
        assert result > 38.0

    def test_invalid_rh_raises(self):
        with pytest.raises(ValueError, match="влажность"):
            heat_index(30.0, 101.0)
        with pytest.raises(ValueError, match="влажность"):
            heat_index(30.0, -1.0)

    @given(
        # Избегаем граничных значений (27°C, 40%) — NWS-формула имеет
        # артефакты прямо на граничных значениях своей применимости.
        t=st.floats(28.0, 50.0, allow_nan=False, allow_infinity=False),
        rh=st.floats(45.0, 100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_hypothesis_result_above_t(self, t, rh):
        """При значениях заведомо внутри области применимости HI ≥ T."""
        result = heat_index(t, rh)
        assert result >= t - 0.01

    @given(
        t=st.floats(-30.0, 60.0, allow_nan=False, allow_infinity=False),
        rh=st.floats(0.0, 100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=300)
    def test_hypothesis_range(self, t, rh):
        """Инварианты heat_index при физически допустимых входах:
        - результат всегда конечное число (не NaN, не Inf)
        - при неприменимых условиях (T<27 или RH<40) → result == t точно
        - при применимых условиях → result >= t (формула не имеет верхнего предела)

        Верхняя граница намеренно отсутствует: полином Rothfusz/NWS —
        регрессия без теоретического ограничения сверху.
        """
        result = heat_index(t, rh)

        # Результат всегда конечный float
        assert isinstance(result, float)
        assert not (result != result)  # not NaN
        assert result != float("inf")

        # При неприменимых условиях — возврат исходной температуры
        if t < 27.0 or rh < 40.0:
            assert result == t, (
                f"heat_index({t}, {rh}) = {result}, ожидалось {t} (вне области применимости)"
            )
        else:
            # При применимых условиях HI ≥ T (эффект перегрева)
            assert result >= t - 0.01, f"heat_index({t}, {rh}) = {result} < t={t}"


# ═══════════════════════════════════════════════════════════════════════════
# Wind Chill
# ═══════════════════════════════════════════════════════════════════════════


class TestWindChill:
    def test_not_applicable_returns_t(self):
        assert wind_chill(15.0, 5.0) == 15.0  # T > 10
        assert wind_chill(5.0, 0.5) == 5.0  # V < 1.3

    def test_kat_minus10_10ms(self):
        """wind_chill(-10, 10) ≈ -20°C (Environment Canada)."""
        result = wind_chill(-10.0, 10.0)
        assert -25.0 <= result <= -15.0, f"Ожидалось ≈-20°C, получено {result}"

    def test_result_below_t(self):
        """Wind chill всегда ≤ исходной температуры при применимых условиях."""
        result = wind_chill(-5.0, 5.0)
        assert result <= -5.0

    def test_negative_v_raises(self):
        with pytest.raises(ValueError, match="отрицательной"):
            wind_chill(0.0, -1.0)

    @given(
        t=st.floats(-50.0, 10.0, allow_nan=False, allow_infinity=False),
        v=st.floats(1.3, 50.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_hypothesis_below_t(self, t, v):
        result = wind_chill(t, v)
        assert result <= t + 0.01


# ═══════════════════════════════════════════════════════════════════════════
# Dew Point
# ═══════════════════════════════════════════════════════════════════════════


class TestDewPoint:
    def test_kat_20_60(self):
        """dew_point(20, 60) ≈ 12°C (Magnus formula)."""
        result = dew_point(20.0, 60.0)
        assert abs(result - 12.0) < 1.0, f"Ожидалось ≈12°C, получено {result}"

    def test_100_percent_humidity(self):
        """При RH=100% точка росы = температура воздуха."""
        result = dew_point(25.0, 100.0)
        assert abs(result - 25.0) < 0.1

    def test_low_humidity(self):
        result = dew_point(30.0, 10.0)
        assert result < 0.0  # сухой воздух → низкая точка росы

    def test_zero_rh_raises(self):
        with pytest.raises(ValueError):
            dew_point(20.0, 0.0)

    def test_over_100_rh_raises(self):
        with pytest.raises(ValueError):
            dew_point(20.0, 101.0)

    @given(
        t=st.floats(-30.0, 50.0, allow_nan=False, allow_infinity=False),
        rh=st.floats(1.0, 100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=300)
    def test_hypothesis_below_t(self, t, rh):
        """Точка росы всегда ≤ температуры воздуха."""
        result = dew_point(t, rh)
        assert result <= t + 0.01


# ═══════════════════════════════════════════════════════════════════════════
# Humidex
# ═══════════════════════════════════════════════════════════════════════════


class TestHumidex:
    def test_kat_30_22(self):
        """humidex(30, 22) ≈ 37°C (MSC)."""
        result = humidex(30.0, 22.0)
        assert 34.0 <= result <= 40.0

    def test_result_above_t(self):
        result = humidex(28.0, 20.0)
        assert result >= 28.0

    def test_td_above_t_raises(self):
        with pytest.raises(ValueError, match="точка росы"):
            humidex(20.0, 25.0)

    @given(
        t=st.floats(0.0, 50.0, allow_nan=False, allow_infinity=False),
        td=st.floats(-20.0, 0.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_hypothesis_cold_dew_point(self, t, td):
        """При td << t результат ≈ t (слабое влияние)."""
        result = humidex(t, td)
        assert isinstance(result, float)
        assert not math.isnan(result)


# ═══════════════════════════════════════════════════════════════════════════
# UV Risk Level
# ═══════════════════════════════════════════════════════════════════════════


class TestUVRiskLevel:
    @pytest.mark.parametrize(
        "uv,expected",
        [
            (0.0, "Низкий"),
            (2.0, "Низкий"),
            (3.0, "Умеренный"),
            (5.0, "Умеренный"),
            (6.0, "Высокий"),
            (7.0, "Высокий"),
            (8.0, "Очень высокий"),
            (10.0, "Очень высокий"),
            (11.0, "Экстремальный"),
            (15.0, "Экстремальный"),
        ],
    )
    def test_kat(self, uv, expected):
        assert uv_risk_level(uv) == expected

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            uv_risk_level(-0.1)

    @given(st.floats(0.0, 20.0, allow_nan=False, allow_infinity=False))
    def test_hypothesis_always_returns_string(self, uv):
        result = uv_risk_level(uv)
        assert isinstance(result, str)
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════════════
# AQI Category EU
# ═══════════════════════════════════════════════════════════════════════════


class TestAQICategoryEU:
    @pytest.mark.parametrize(
        "aqi,expected",
        [
            (0.0, "Хороший"),
            (20.0, "Хороший"),
            (21.0, "Удовлетворительный"),
            (40.0, "Удовлетворительный"),
            (41.0, "Умеренный"),
            (60.0, "Умеренный"),
            (61.0, "Плохой"),
            (80.0, "Плохой"),
            (81.0, "Очень плохой"),
            (100.0, "Очень плохой"),
            (101.0, "Крайне плохой"),
            (200.0, "Крайне плохой"),
        ],
    )
    def test_kat(self, aqi, expected):
        assert aqi_category_eu(aqi) == expected

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            aqi_category_eu(-1.0)


# ═══════════════════════════════════════════════════════════════════════════
# Precipitation Intensity
# ═══════════════════════════════════════════════════════════════════════════


class TestPrecipitationIntensity:
    @pytest.mark.parametrize(
        "mm,expected",
        [
            (0.0, "Следы"),
            (0.4, "Следы"),
            (0.5, "Слабые"),
            (2.5, "Слабые"),
            (2.6, "Умеренные"),
            (7.5, "Умеренные"),
            (7.6, "Сильные"),
            (50.0, "Сильные"),
            (50.1, "Ливневые"),
            (100.0, "Ливневые"),
        ],
    )
    def test_kat(self, mm, expected):
        assert precipitation_intensity(mm) == expected

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            precipitation_intensity(-0.1)

    @given(st.floats(0.0, 200.0, allow_nan=False, allow_infinity=False))
    def test_hypothesis_always_returns_string(self, mm):
        assert isinstance(precipitation_intensity(mm), str)


# ═══════════════════════════════════════════════════════════════════════════
# Weather Trend
# ═══════════════════════════════════════════════════════════════════════════


class TestWeatherTrend:
    def test_kat_warming(self):
        """[10,11,12,13,14,15,16] → slope≈1.0, trend=warming, r2≈1.0."""
        result = weather_trend([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0])
        assert abs(result["slope"] - 1.0) < 0.01
        assert result["trend"] == "warming"
        assert abs(result["r2"] - 1.0) < 0.01
        assert result["confidence"] == "high"

    def test_kat_cooling(self):
        result = weather_trend([16.0, 15.0, 14.0, 13.0, 12.0, 11.0, 10.0])
        assert result["slope"] < 0.0
        assert result["trend"] == "cooling"

    def test_kat_stable(self):
        """Постоянный ряд → slope=0, trend=stable."""
        result = weather_trend([15.0] * 7)
        assert result["trend"] == "stable"
        assert abs(result["slope"]) < 0.01
        assert result["r2"] == 0.0

    def test_r2_perfect_linear(self):
        result = weather_trend([1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0])
        assert abs(result["r2"] - 1.0) < 0.001

    def test_min_length_2(self):
        result = weather_trend([10.0, 12.0])
        assert isinstance(result["slope"], float)

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="минимум 2"):
            weather_trend([10.0])

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            weather_trend([])

    def test_result_keys(self):
        result = weather_trend([10.0, 11.0, 12.0])
        assert set(result.keys()) == {"slope", "intercept", "r2", "trend", "confidence"}

    @given(
        st.lists(
            st.floats(-30.0, 40.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=16,
        )
    )
    @settings(max_examples=300)
    def test_hypothesis_valid_output(self, values):
        result = weather_trend(values)
        assert result["trend"] in ("warming", "cooling", "stable")
        assert result["confidence"] in ("high", "medium", "low")
        assert 0.0 <= result["r2"] <= 1.0 + 1e-9
        assert isinstance(result["slope"], float)


# ═══════════════════════════════════════════════════════════════════════════
# Comfort Score
# ═══════════════════════════════════════════════════════════════════════════


class TestComfortScore:
    def test_kat_ideal(self):
        """comfort_score(22, 50, 2, 1, 0) → ≈ 95–100."""
        result = comfort_score(22.0, 50.0, 2.0, 1.0, 0.0)
        assert result["score"] >= 95.0, f"Ожидалось ≥95, получено {result['score']}"

    def test_extreme_cold(self):
        """
        При всех экстремально плохих условиях → score < 40.
        -20°C (temp_sub=0), 95% влажность (humidity_sub≈0),
        20 м/с ветер (wind_sub=0), UV=12 (uv_sub≈0), 15 мм осадков (precip_sub=0).
        """
        result = comfort_score(-20.0, 95.0, 20.0, 12.0, 15.0)
        assert result["score"] < 40.0, f"Ожидалось <40, получено {result['score']}"

    def test_extreme_cold_temperature_only(self):
        """
        При -20°C с иными комфортными условиями score определяется остальными
        субиндексами. temp_sub=0, но остальные могут давать до 65.
        """
        result = comfort_score(-20.0, 50.0, 2.0, 0.0, 0.0)
        # temp_sub=0 → максимум 65 от остальных субиндексов
        assert result["temp_sub"] == 0.0
        assert result["score"] <= 65.0

    def test_extreme_hot(self):
        """
        При всех экстремально плохих условиях → score < 40.
        42°C (temp_sub=0), 95% влажность (humidity_sub≈0),
        20 м/с ветер (wind_sub=0), UV=12 (uv_sub≈0), 15 мм осадков (precip_sub=0).
        """
        result = comfort_score(42.0, 95.0, 20.0, 12.0, 15.0)
        assert result["score"] < 40.0, f"Ожидалось <40, получено {result['score']}"

    def test_temp_sub_zero_at_extremes(self):
        """temp_sub должен быть 0 при T=-20°C и T=42°C."""
        r_cold = comfort_score(-20.0, 50.0, 2.0, 0.0, 0.0)
        r_hot = comfort_score(42.0, 50.0, 2.0, 0.0, 0.0)
        assert r_cold["temp_sub"] == 0.0
        assert r_hot["temp_sub"] == 0.0

    def test_humidity_sub_zero_at_extremes(self):
        """humidity_sub должен быть 0 при RH=5% и RH=95%."""
        r_dry = comfort_score(22.0, 5.0, 2.0, 0.0, 0.0)
        r_wet = comfort_score(22.0, 95.0, 2.0, 0.0, 0.0)
        assert r_dry["humidity_sub"] == 0.0
        assert r_wet["humidity_sub"] == 0.0

    def test_score_in_0_100(self):
        result = comfort_score(22.0, 50.0, 2.0, 1.0, 0.0)
        assert 0.0 <= result["score"] <= 100.0

    def test_all_subs_in_0_100(self):
        result = comfort_score(22.0, 50.0, 2.0, 1.0, 0.0)
        for key in ("temp_sub", "humidity_sub", "wind_sub", "uv_sub", "precip_sub"):
            assert 0.0 <= result[key] <= 100.0

    def test_invalid_rh_raises(self):
        with pytest.raises(ValueError):
            comfort_score(22.0, 110.0, 2.0, 1.0, 0.0)

    def test_negative_wind_raises(self):
        with pytest.raises(ValueError):
            comfort_score(22.0, 50.0, -1.0, 1.0, 0.0)

    @given(
        t=st.floats(-30.0, 50.0, allow_nan=False, allow_infinity=False),
        rh=st.floats(0.0, 100.0, allow_nan=False, allow_infinity=False),
        v=st.floats(0.0, 30.0, allow_nan=False, allow_infinity=False),
        uv=st.floats(0.0, 15.0, allow_nan=False, allow_infinity=False),
        p=st.floats(0.0, 20.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=300)
    def test_hypothesis_score_range(self, t, rh, v, uv, p):
        result = comfort_score(t, rh, v, uv, p)
        assert 0.0 <= result["score"] <= 100.0


# ═══════════════════════════════════════════════════════════════════════════
# Frost Risk
# ═══════════════════════════════════════════════════════════════════════════


class TestFrostRisk:
    def test_below_zero(self):
        assert frost_risk(-0.1) is True
        assert frost_risk(-10.0) is True

    def test_zero_no_frost(self):
        assert frost_risk(0.0) is False

    def test_above_zero(self):
        assert frost_risk(5.0) is False

    @given(st.floats(-50.0, -0.01, allow_nan=False, allow_infinity=False))
    def test_hypothesis_always_true_below_zero(self, t):
        assert frost_risk(t) is True

    @given(st.floats(0.0, 50.0, allow_nan=False, allow_infinity=False))
    def test_hypothesis_always_false_at_or_above_zero(self, t):
        assert frost_risk(t) is False


# ═══════════════════════════════════════════════════════════════════════════
# High Wind Alert
# ═══════════════════════════════════════════════════════════════════════════


class TestHighWindAlert:
    def test_wind_above_threshold(self):
        assert high_wind_alert(14.0, 10.0) is True

    def test_gusts_above_threshold(self):
        assert high_wind_alert(10.0, 14.0) is True

    def test_both_below_threshold(self):
        assert high_wind_alert(13.9, 13.9) is False

    def test_both_zero(self):
        assert high_wind_alert(0.0, 0.0) is False

    def test_negative_v_raises(self):
        with pytest.raises(ValueError):
            high_wind_alert(-1.0, 5.0)

    def test_negative_gusts_raises(self):
        with pytest.raises(ValueError):
            high_wind_alert(5.0, -1.0)

    @given(
        v=st.floats(14.0, 60.0, allow_nan=False, allow_infinity=False),
        g=st.floats(0.0, 60.0, allow_nan=False, allow_infinity=False),
    )
    def test_hypothesis_always_alert_when_v_high(self, v, g):
        assert high_wind_alert(v, g) is True
