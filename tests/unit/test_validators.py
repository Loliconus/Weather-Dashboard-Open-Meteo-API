"""Тесты validators.py."""

from __future__ import annotations

import warnings

import pytest

from weather_dashboard.processing.validators import (
    validate_coordinates,
    validate_forecast_days,
    validate_humidity,
    validate_temperature,
    validate_wind_speed,
)


class TestValidateCoordinates:
    def test_valid_moscow(self):
        validate_coordinates(55.7558, 37.6173)  # не бросает

    def test_valid_extremes(self):
        validate_coordinates(-90.0, -180.0)
        validate_coordinates(90.0, 180.0)
        validate_coordinates(0.0, 0.0)

    def test_lat_too_high(self):
        with pytest.raises(ValueError, match="Широта"):
            validate_coordinates(91.0, 0.0)

    def test_lat_too_low(self):
        with pytest.raises(ValueError, match="Широта"):
            validate_coordinates(-90.1, 0.0)

    def test_lon_too_high(self):
        with pytest.raises(ValueError, match="Долгота"):
            validate_coordinates(0.0, 180.1)

    def test_lon_too_low(self):
        with pytest.raises(ValueError, match="Долгота"):
            validate_coordinates(0.0, -181.0)

    def test_error_message_contains_value(self):
        with pytest.raises(ValueError, match="95.0"):
            validate_coordinates(95.0, 0.0)


class TestValidateForecastDays:
    @pytest.mark.parametrize("n", [1, 7, 16])
    def test_valid(self, n):
        validate_forecast_days(n)  # не бросает

    @pytest.mark.parametrize("n", [0, -1, 17, 100])
    def test_invalid(self, n):
        with pytest.raises(ValueError, match="1 до 16"):
            validate_forecast_days(n)


class TestValidateTemperature:
    def test_normal_no_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            validate_temperature(22.5)  # не предупреждает

    def test_extreme_low_warns(self):
        with pytest.warns(UserWarning, match="правдоподобный"):
            validate_temperature(-95.0)

    def test_extreme_high_warns(self):
        with pytest.warns(UserWarning, match="правдоподобный"):
            validate_temperature(65.0)

    def test_boundary_no_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            validate_temperature(-90.0)
            validate_temperature(60.0)

    def test_no_exception_raised(self):
        """validate_temperature никогда не бросает ValueError."""
        validate_temperature(-200.0)  # только warn
        validate_temperature(1000.0)  # только warn


class TestValidateHumidity:
    @pytest.mark.parametrize("rh", [0.0, 50.0, 100.0])
    def test_valid(self, rh):
        validate_humidity(rh)

    @pytest.mark.parametrize("rh", [-0.1, 100.1, 150.0])
    def test_invalid(self, rh):
        with pytest.raises(ValueError, match="влажность"):
            validate_humidity(rh)


class TestValidateWindSpeed:
    @pytest.mark.parametrize("v", [0.0, 10.0, 120.0])
    def test_valid(self, v):
        validate_wind_speed(v)

    @pytest.mark.parametrize("v", [-1.0, -0.1, 120.1])
    def test_invalid(self, v):
        with pytest.raises(ValueError, match="ветра"):
            validate_wind_speed(v)
