"""
agent/tools/weather.py — Weather Tool
--------------------------------------
Returns live weather data for any city, powered by Open-Meteo
(https://open-meteo.com) — free, no API key required.

Flow: city name → geocoding API → lat/lon → forecast API → current conditions.
"""

import httpx
from agent.tools.registry import tool

_GEOCODE_URL  = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 10.0

# WMO weather interpretation codes → human-readable condition
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Dense freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light rain showers", 81: "Rain showers", 82: "Violent rain showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


@tool(
    name="get_weather",
    description=(
        "Get live current weather conditions for any city worldwide. "
        "Returns temperature, weather condition, humidity, and wind speed."
    ),
    parameters={
        "city": {
            "type": "string",
            "description": "City name, e.g. 'London' or 'Tokyo'",
        }
    },
    examples=[
        {"city": "Tokyo",   "result": "28°C, Sunny, Humidity: 70%"},
        {"city": "London",  "result": "14°C, Rainy, Humidity: 85%"},
    ],
)
def get_weather(city: str) -> str:
    """Fetch live weather for a given city via Open-Meteo."""
    city = city.strip().strip("?.!,")
    if not city:
        return "Error: no city name provided."

    try:
        # Step 1: resolve city name to coordinates
        geo_resp = httpx.get(
            _GEOCODE_URL, params={"name": city, "count": 1}, timeout=_TIMEOUT
        )
        geo_resp.raise_for_status()
        results = geo_resp.json().get("results")
        if not results:
            return f"Error: could not find a city named '{city}'. Check the spelling."

        place = results[0]
        label = place["name"]
        if place.get("country"):
            label += f", {place['country']}"

        # Step 2: fetch current conditions for those coordinates
        wx_resp = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            },
            timeout=_TIMEOUT,
        )
        wx_resp.raise_for_status()
        current = wx_resp.json()["current"]

    except httpx.HTTPError as e:
        return f"Error: weather service unavailable ({e}). Try again shortly."

    temp_c = current["temperature_2m"]
    temp_f = round(temp_c * 9 / 5 + 32, 1)
    condition = _WMO_CODES.get(current["weather_code"], "Unknown conditions")

    return (
        f"Weather for {label}: "
        f"{temp_c}°C ({temp_f}°F), "
        f"{condition}, "
        f"Humidity: {current['relative_humidity_2m']}%, "
        f"Wind: {current['wind_speed_10m']} km/h"
    )
