import hashlib
import json
import logging
import math

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
logger = logging.getLogger(__name__)
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


def _icon(code):
    if code in (0, 1):
        return "☀"
    if code == 2:
        return "⛅"
    if code == 3:
        return "☁"
    if code in (45, 48):
        return "🌫"
    if code in (71, 73, 75, 77, 85, 86):
        return "❄"
    if code >= 95:
        return "⛈"
    return "🌧"


def _unavailable(state, message, reason=None):
    return {"available": False, "state": state, "reason": reason or state, "message": message}


def _provider_failure(reason, target, status=None):
    logger.warning("Open-Meteo forecast unavailable: reason=%s date=%s http_status=%s", reason, target, status)
    messages = {
        "timeout": "The weather provider took too long to respond. Please try again later.",
        "connection_error": "The weather provider could not be reached. Please check the connection and try again later.",
        "invalid_json": "The weather provider returned an unreadable response. Please try again later.",
        "invalid_payload": "The weather provider has not supplied a usable forecast for this event date. Please try again later.",
    }
    message = messages.get(reason, "The weather provider is temporarily unavailable. Please try again later.")
    return _unavailable("temporarily_unavailable", message, reason)


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
    required_fields = ("temperature_2m_min", "temperature_2m_max", "weather_code")
    if any(not isinstance(daily.get(field), list) or len(daily[field]) != len(dates) for field in required_fields):
        return None

    index = dates.index(target.isoformat())
    temp_min = daily["temperature_2m_min"][index]
    temp_max = daily["temperature_2m_max"][index]
    code = daily["weather_code"][index]
    if not all(_finite_number(value) for value in (temp_min, temp_max, code)):
        return None
    if temp_min > temp_max or code not in WEATHER_DESCRIPTIONS:
        return None
    rain_values = daily.get("precipitation_probability_max")
    rain = None
    if rain_values is not None:
        if not isinstance(rain_values, list) or len(rain_values) != len(dates):
            return None
        rain = rain_values[index]
        if rain is not None and (not _finite_number(rain) or not 0 <= rain <= 100):
            return None
    return {
        "date": target,
        "description": WEATHER_DESCRIPTIONS[code],
        "icon": _icon(code),
        "temp_min": temp_min,
        "temp_max": temp_max,
        "rain_probability": rain,
    }


def forecast_for_event(event):
    """Return a validated forecast or a readable unavailable state; cache successes."""
    event_timezone = timezone.get_default_timezone()
    target = timezone.localtime(event.starts_at, event_timezone).date()
    today = timezone.localtime(timezone.now(), event_timezone).date()
    offset = (target - today).days
    if offset < 0:
        return _unavailable("past", "A future forecast is no longer available for this past event date.")
    if offset >= 16:
        return _unavailable("out_of_range", "Forecast not yet available. Check again within 16 days of the event.")

    latitude, longitude = event.venue.latitude, event.venue.longitude
    if not (_finite_number(latitude) and _finite_number(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
        return _unavailable("invalid_location", "This venue's location needs to be corrected by its organizer before a forecast can be shown.")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(DAILY_FIELDS),
        "timezone": settings.TIME_ZONE,
        "temperature_unit": "celsius",
        "start_date": target.isoformat(),
        "end_date": target.isoformat(),
    }
    signature = json.dumps(params, sort_keys=True, separators=(",", ":"))
    cache_key = "event-weather:v2:" + hashlib.sha256(signature.encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(FORECAST_URL, params=params, timeout=(2, 3))
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout:
        return _provider_failure("timeout", target)
    except requests.ConnectionError:
        return _provider_failure("connection_error", target)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        return _provider_failure("http_error", target, status)
    except (requests.exceptions.JSONDecodeError, ValueError):
        return _provider_failure("invalid_json", target)
    except requests.RequestException:
        return _provider_failure("request_error", target)

    forecast = _daily_forecast(payload, target)
    if forecast is None:
        return _provider_failure("invalid_payload", target)
    result = {"available": True, "state": "available", "reason": "available", **forecast, "fetched_at": timezone.now()}
    cache.set(cache_key, result, timeout=900)
    return result
