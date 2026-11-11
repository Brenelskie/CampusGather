import hashlib
import json
import math
from zoneinfo import ZoneInfo

import requests
from django.core.cache import cache
from django.utils import timezone


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MANILA = ZoneInfo("Asia/Manila")
DAILY_FIELDS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "weather_code",
)
WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Heavy drizzle",
    56: "Light freezing drizzle",
    57: "Heavy freezing drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light rain showers",
    81: "Moderate rain showers",
    82: "Heavy rain showers",
    85: "Light snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with light hail",
    97: "Heavy thunderstorm",
    99: "Thunderstorm with heavy hail",
}


def _finite_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _daily_forecast(payload, target):
    if not isinstance(payload, dict) or payload.get("error"):
        return None
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        return None
    dates = daily.get("time")
    if not isinstance(dates, list) or dates.count(target.isoformat()) != 1:
        return None
    if any(not isinstance(daily.get(field), list) or len(daily[field]) != len(dates) for field in DAILY_FIELDS):
        return None

    index = dates.index(target.isoformat())
    temp_min = daily["temperature_2m_min"][index]
    temp_max = daily["temperature_2m_max"][index]
    rain = daily["precipitation_probability_max"][index]
    code = daily["weather_code"][index]
    if not all(_finite_number(value) for value in (temp_min, temp_max, rain, code)):
        return None
    if temp_min > temp_max or not 0 <= rain <= 100 or code not in WEATHER_DESCRIPTIONS:
        return None
    return {
        "date": target,
        "description": WEATHER_DESCRIPTIONS[code],
        "temp_min": temp_min,
        "temp_max": temp_max,
        "rain_probability": rain,
    }


def forecast_for_event(event):
    """Return a validated forecast or a readable unavailable state; cache successes."""
    target = timezone.localtime(event.starts_at, MANILA).date()
    today = timezone.localtime(timezone.now(), MANILA).date()
    offset = (target - today).days
    if offset < 0:
        return {"available": False, "message": "Forecasts are unavailable for past event dates."}
    if offset >= 16:
        return {"available": False, "message": "Forecast not yet available. Check again within 16 days of the event."}

    params = {
        "latitude": event.venue.latitude,
        "longitude": event.venue.longitude,
        "daily": ",".join(DAILY_FIELDS),
        "timezone": "Asia/Manila",
        "temperature_unit": "celsius",
        "start_date": target.isoformat(),
        "end_date": target.isoformat(),
    }
    signature = json.dumps(params, sort_keys=True, separators=(",", ":"))
    cache_key = "event-weather:" + hashlib.sha256(signature.encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    unavailable = {
        "available": False,
        "message": "Weather forecast is temporarily unavailable for this event date. Please try again later.",
    }
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=(2, 3))
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return unavailable

    forecast = _daily_forecast(payload, target)
    if forecast is None:
        return unavailable
    result = {"available": True, **forecast, "fetched_at": timezone.now()}
    cache.set(cache_key, result, timeout=900)
    return result
