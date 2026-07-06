"""
agent/tools/weather.py — Weather Tool
--------------------------------------
Returns weather data for a city.
In a real agent, this would call OpenWeatherMap or WeatherAPI.
Here it's mocked so you can run without an extra API key.

To make it real: replace the mock with an httpx.get() call.
"""

import random
from agent.tools.registry import tool


# Mock weather database
_WEATHER_DB = {
    "new york":     {"temp_c": 22, "condition": "Partly Cloudy", "humidity": 65},
    "london":       {"temp_c": 14, "condition": "Rainy",         "humidity": 85},
    "tokyo":        {"temp_c": 28, "condition": "Sunny",         "humidity": 70},
    "berlin":       {"temp_c": 18, "condition": "Overcast",      "humidity": 72},
    "bangalore":    {"temp_c": 26, "condition": "Sunny",         "humidity": 55},
    "san francisco":{"temp_c": 17, "condition": "Foggy",         "humidity": 80},
    "sydney":       {"temp_c": 20, "condition": "Clear",         "humidity": 60},
}


@tool(
    name="get_weather",
    description=(
        "Get current weather conditions for a city. "
        "Returns temperature, weather condition, and humidity."
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
    """Fetch weather for a given city (mocked)."""
    key = city.lower().strip()
    data = _WEATHER_DB.get(key)

    if not data:
        # For unknown cities, return a plausible random result
        temp = random.randint(10, 35)
        conditions = ["Sunny", "Partly Cloudy", "Overcast", "Rainy", "Clear"]
        return (
            f"Weather for {city.title()}: {temp}°C, "
            f"{random.choice(conditions)}, Humidity: {random.randint(40, 90)}%"
        )

    temp_f = round(data["temp_c"] * 9 / 5 + 32, 1)
    return (
        f"Weather for {city.title()}: "
        f"{data['temp_c']}°C ({temp_f}°F), "
        f"{data['condition']}, "
        f"Humidity: {data['humidity']}%"
    )
