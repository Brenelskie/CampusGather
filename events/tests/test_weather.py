from copy import deepcopy
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from events.weather import forecast_for_event


@override_settings(CACHES={
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "campusgather-weather-tests",
    },
})
class ForecastTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.now = datetime(2026, 11, 11, 4, tzinfo=datetime_timezone.utc)
        clock_patch = patch("events.weather.timezone.now", return_value=self.now)
        self.clock = clock_patch.start()
        self.addCleanup(clock_patch.stop)
        http_patch = patch("events.weather.requests.get")
        self.get = http_patch.start()
        self.addCleanup(http_patch.stop)
        self.response = Mock()
        self.get.return_value = self.response
        self.event = SimpleNamespace(
            title="Private event title",
            starts_at=self.now + timedelta(days=2),
            venue=SimpleNamespace(latitude=9.7392, longitude=118.7353),
        )
        self.target = date(2026, 11, 13)
        self.response.json.return_value = self.payload(self.target)

    def payload(self, *dates):
        return {"daily": {
            "time": [day.isoformat() for day in dates],
            "temperature_2m_min": [24.2] * len(dates),
            "temperature_2m_max": [31.6] * len(dates),
            "precipitation_probability_max": [30] * len(dates),
            "weather_code": [2] * len(dates),
        }}

    def assert_unavailable(self, result):
        self.assertIs(result["available"], False)
        self.assertTrue(result["message"])
        self.assertNotIn("temp_max", result)

    def test_matches_actual_event_date_and_sends_only_weather_parameters(self):
        payload = self.payload(date(2026, 11, 11), self.target)
        payload["daily"]["temperature_2m_max"] = [38, 31.6]
        payload["daily"]["precipitation_probability_max"] = [95, 30]
        self.response.json.return_value = payload

        result = forecast_for_event(self.event)

        self.assertIs(result["available"], True)
        self.assertEqual(result["date"], self.target)
        self.assertEqual(result["temp_min"], 24.2)
        self.assertEqual(result["temp_max"], 31.6)
        self.assertEqual(result["rain_probability"], 30)
        self.assertEqual(result["description"], "Partly cloudy")
        self.assertEqual(result["fetched_at"], self.now)
        self.assertTrue(timezone.is_aware(result["fetched_at"]))
        self.response.raise_for_status.assert_called_once_with()
        self.get.assert_called_once_with(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": 9.7392,
                "longitude": 118.7353,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "timezone": "Asia/Manila",
                "temperature_unit": "celsius",
                "start_date": "2026-11-13",
                "end_date": "2026-11-13",
            },
            timeout=(2, 3),
        )

    def test_caches_valid_success_for_fifteen_minutes(self):
        with patch("events.weather.cache.set", wraps=cache.set) as store:
            first = forecast_for_event(self.event)
            self.clock.return_value = self.now + timedelta(minutes=5)
            second = forecast_for_event(self.event)

        self.assertEqual(first, second)
        self.get.assert_called_once()
        self.assertEqual(store.call_args.kwargs["timeout"], 900)

    def test_changing_either_coordinate_or_event_date_uses_a_new_forecast(self):
        self.assertTrue(forecast_for_event(self.event)["available"])
        self.event.venue.latitude = 9.8
        self.assertTrue(forecast_for_event(self.event)["available"])
        self.event.venue.longitude = 118.8
        self.assertTrue(forecast_for_event(self.event)["available"])
        self.event.starts_at += timedelta(days=1)
        self.response.json.return_value = self.payload(self.target + timedelta(days=1))
        result = forecast_for_event(self.event)

        self.assertEqual(result["date"], self.target + timedelta(days=1))
        self.assertEqual(self.get.call_count, 4)

    def test_manila_date_is_used_across_utc_midnight_and_active_timezone(self):
        self.clock.return_value = datetime(2026, 11, 10, 17, tzinfo=datetime_timezone.utc)
        self.event.starts_at = datetime(2026, 11, 10, 18, tzinfo=datetime_timezone.utc)
        self.response.json.return_value = self.payload(date(2026, 11, 11))

        with timezone.override("UTC"):
            result = forecast_for_event(self.event)

        self.assertTrue(result["available"])
        self.assertEqual(result["date"], date(2026, 11, 11))
        self.assertEqual(self.get.call_args.kwargs["params"]["start_date"], "2026-11-11")

    def test_today_and_fifteenth_day_are_inside_the_forecast_horizon(self):
        for offset in (0, 15):
            with self.subTest(offset=offset):
                self.event.starts_at = self.now + timedelta(days=offset)
                target = date(2026, 11, 11) + timedelta(days=offset)
                self.response.json.return_value = self.payload(target)
                result = forecast_for_event(self.event)
                self.assertTrue(result["available"])
                self.assertEqual(result["date"], target)
        self.assertEqual(self.get.call_count, 2)

    def test_past_and_sixteenth_day_skip_cache_and_network(self):
        for offset in (-1, 16):
            with self.subTest(offset=offset):
                self.event.starts_at = self.now + timedelta(days=offset)
                with patch("events.weather.cache.get") as lookup:
                    self.assert_unavailable(forecast_for_event(self.event))
                lookup.assert_not_called()
        self.get.assert_not_called()

    def test_past_date_does_not_reuse_a_previous_success(self):
        self.assertTrue(forecast_for_event(self.event)["available"])
        self.clock.return_value = self.now + timedelta(days=3)

        with patch("events.weather.cache.get") as lookup:
            self.assert_unavailable(forecast_for_event(self.event))

        lookup.assert_not_called()
        self.get.assert_called_once()

    def test_network_errors_are_unavailable_and_are_not_cached(self):
        for error in (requests.Timeout("timed out"), requests.ConnectionError("offline")):
            with self.subTest(error=type(error).__name__):
                self.get.side_effect = error
                self.assert_unavailable(forecast_for_event(self.event))
        self.get.side_effect = None
        self.assertTrue(forecast_for_event(self.event)["available"])
        self.assertEqual(self.get.call_count, 3)

    def test_http_errors_are_unavailable(self):
        for status in (429, 500):
            with self.subTest(status=status):
                self.response.raise_for_status.side_effect = requests.HTTPError(str(status))
                self.assert_unavailable(forecast_for_event(self.event))
        self.response.json.assert_not_called()

    def test_malformed_json_is_unavailable_and_is_not_cached(self):
        self.response.json.side_effect = ValueError("Invalid JSON")
        self.assert_unavailable(forecast_for_event(self.event))
        self.response.json.side_effect = None
        self.assertTrue(forecast_for_event(self.event)["available"])
        self.assertEqual(self.get.call_count, 2)

    def test_missing_null_and_incompatible_daily_data_are_unavailable(self):
        valid = self.payload(self.target)
        cases = [None, [], {}, {"error": True, **valid}, {"daily": None}, {"daily": []}]
        for field in valid["daily"]:
            missing = deepcopy(valid)
            del missing["daily"][field]
            cases.append(missing)
            null_array = deepcopy(valid)
            null_array["daily"][field] = None
            cases.append(null_array)
            empty_array = deepcopy(valid)
            empty_array["daily"][field] = []
            cases.append(empty_array)
            null_value = deepcopy(valid)
            null_value["daily"][field] = [None]
            cases.append(null_value)
        unequal = deepcopy(valid)
        unequal["daily"]["temperature_2m_max"].append(32)
        cases.append(unequal)

        for index, payload in enumerate(cases):
            with self.subTest(case=index):
                self.response.json.return_value = payload
                self.assert_unavailable(forecast_for_event(self.event))

    def test_absent_or_malformed_event_date_never_falls_back_to_today(self):
        for day in ("2026-11-11", "2026-02-30", "20261113", None):
            with self.subTest(day=day):
                payload = self.payload(self.target)
                payload["daily"]["time"] = [day]
                self.response.json.return_value = payload
                self.assert_unavailable(forecast_for_event(self.event))

    def test_nonfinite_or_incompatible_measurements_are_unavailable(self):
        changes = (
            ("temperature_2m_min", float("nan")),
            ("temperature_2m_max", float("inf")),
            ("temperature_2m_max", 10 ** 400),
            ("temperature_2m_max", "31.6"),
            ("temperature_2m_min", 35),
            ("precipitation_probability_max", -1),
            ("precipitation_probability_max", 101),
            ("precipitation_probability_max", True),
            ("weather_code", None),
            ("weather_code", 2.5),
            ("weather_code", 999),
            ("weather_code", float("inf")),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                payload = self.payload(self.target)
                payload["daily"][field] = [value]
                self.response.json.return_value = payload
                self.assert_unavailable(forecast_for_event(self.event))
