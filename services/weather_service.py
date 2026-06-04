"""
Weather service — auto-fetches historical weather for a run date/location.

Uses Open-Meteo (https://open-meteo.com/) — completely FREE, no API key required.
- Historical data via:  https://archive-api.open-meteo.com/v1/archive
- Current/future data:  https://api.open-meteo.com/v1/forecast
- Geocoding (city→lat/lng): https://geocoding-api.open-meteo.com/v1/search
"""

import urllib.request
import urllib.parse
import json
from datetime import date, datetime


# ── WMO Weather Code → (description, emoji) ──────────────────────────────────
WMO_CODES = {
    0:  ("Clear sky",         "☀️"),
    1:  ("Mainly clear",      "🌤️"),
    2:  ("Partly cloudy",     "⛅"),
    3:  ("Overcast",          "☁️"),
    45: ("Foggy",             "🌫️"),
    48: ("Icy fog",           "🌫️"),
    51: ("Light drizzle",     "🌦️"),
    53: ("Drizzle",           "🌦️"),
    55: ("Heavy drizzle",     "🌧️"),
    61: ("Light rain",        "🌧️"),
    63: ("Rain",              "🌧️"),
    65: ("Heavy rain",        "🌧️"),
    71: ("Light snow",        "❄️"),
    73: ("Snow",              "❄️"),
    75: ("Heavy snow",        "❄️"),
    77: ("Snow grains",       "❄️"),
    80: ("Rain showers",      "🌦️"),
    81: ("Rain showers",      "🌧️"),
    82: ("Violent showers",   "⛈️"),
    85: ("Snow showers",      "🌨️"),
    86: ("Heavy snow showers","🌨️"),
    95: ("Thunderstorm",      "⛈️"),
    96: ("Thunderstorm + hail","⛈️"),
    99: ("Thunderstorm + hail","⛈️"),
}


def _wmo_to_text(code):
    """Convert WMO weather code to (description, emoji) tuple."""
    if code is None:
        return "Unknown", "🌡️"
    entry = WMO_CODES.get(int(code))
    if entry:
        return entry
    # Round down to nearest known code
    for threshold in sorted(WMO_CODES.keys(), reverse=True):
        if int(code) >= threshold:
            return WMO_CODES[threshold]
    return "Unknown", "🌡️"


def geocode_city(city_name):
    """
    Convert a city name to (latitude, longitude) using Open-Meteo's free geocoding API.

    Args:
        city_name: e.g. "New Delhi", "London", "Mumbai"

    Returns:
        tuple: (latitude, longitude, resolved_name) or (None, None, None) on failure
    """
    if not city_name or not city_name.strip():
        return None, None, None

    try:
        params = urllib.parse.urlencode({
            "name": city_name.strip(),
            "count": 1,
            "language": "en",
            "format": "json"
        })
        url = f"https://geocoding-api.open-meteo.com/v1/search?{params}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())

        results = data.get("results", [])
        if not results:
            return None, None, None

        top = results[0]
        name = f"{top.get('name', city_name)}, {top.get('country', '')}"
        return round(top["latitude"], 4), round(top["longitude"], 4), name.strip(", ")

    except Exception:
        return None, None, None


def fetch_weather(run_date_str, latitude, longitude):
    """
    Fetch weather conditions for a specific date and location.

    Uses historical archive for past runs and the forecast API for today's runs.

    Args:
        run_date_str: Date string in YYYY-MM-DD format
        latitude:     Latitude (float)
        longitude:    Longitude (float)

    Returns:
        dict with keys:
            temp_c       – temperature in Celsius (float)
            humidity     – relative humidity % (int)
            wind_kph     – wind speed in km/h (float)
            condition    – human-readable description (str)
            emoji        – weather emoji (str)
            feels_like_c – apparent temperature (float, may be None)
        or None if fetch fails.
    """
    if latitude is None or longitude is None:
        return None

    try:
        run_date = datetime.strptime(run_date_str, "%Y-%m-%d").date()
        today = date.today()

        hourly_vars = [
            "temperature_2m",
            "relativehumidity_2m",
            "windspeed_10m",
            "weathercode",
            "apparent_temperature",
        ]

        if run_date >= today:
            # Today or future → use forecast API
            base_url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": ",".join(hourly_vars),
                "timezone": "auto",
                "forecast_days": 1,
            }
        else:
            # Past run → use historical archive API
            base_url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": run_date_str,
                "end_date": run_date_str,
                "hourly": ",".join(hourly_vars),
                "timezone": "auto",
            }

        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read())

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            return None

        # Pick the noon (12:00) reading as representative of the run day
        # Fall back to first available reading
        noon_str = f"{run_date_str}T12:00"
        idx = 0
        for i, t in enumerate(times):
            if t.startswith(noon_str):
                idx = i
                break
            if t.startswith(run_date_str):
                idx = i  # first reading of the day as fallback

        def safe_get(key, default=None):
            vals = hourly.get(key, [])
            return vals[idx] if idx < len(vals) and vals[idx] is not None else default

        temp       = safe_get("temperature_2m")
        humidity   = safe_get("relativehumidity_2m")
        wind       = safe_get("windspeed_10m")
        wmo_code   = safe_get("weathercode")
        feels_like = safe_get("apparent_temperature")

        condition, emoji = _wmo_to_text(wmo_code)

        return {
            "temp_c":       round(temp, 1)       if temp       is not None else None,
            "humidity":     int(humidity)         if humidity   is not None else None,
            "wind_kph":     round(wind, 1)        if wind       is not None else None,
            "condition":    condition,
            "emoji":        emoji,
            "feels_like_c": round(feels_like, 1) if feels_like is not None else None,
        }

    except Exception:
        return None


def weather_summary_str(weather):
    """
    Produce a short one-line summary string from a weather dict.
    E.g. "☀️ Clear sky · 24°C · 60% humidity · 12 km/h wind"

    Args:
        weather: dict returned by fetch_weather(), or None

    Returns:
        str or None
    """
    if not weather:
        return None

    parts = [f"{weather['emoji']} {weather['condition']}"]

    if weather.get("temp_c") is not None:
        parts.append(f"{weather['temp_c']}°C")

    if weather.get("humidity") is not None:
        parts.append(f"{weather['humidity']}% humidity")

    if weather.get("wind_kph") is not None:
        parts.append(f"{weather['wind_kph']} km/h wind")

    return " · ".join(parts)
