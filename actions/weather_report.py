import webbrowser
from urllib.parse import quote_plus

from core.logger import get_logger
from core.validator import validate_params, ValidationError

log = get_logger(__name__)


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    parameters = validate_params(parameters, VALIDATOR, tool_name="weather_report")
    city     = parameters.get("city")
    when     = parameters.get("time", "today")  

    if not city or not isinstance(city, str) or not city.strip():
        msg = "Sir, the city is missing for the weather report."
        _log(msg, player)
        return msg

    city = city.strip()
    when = (when or "today").strip()

    search_query  = f"weather in {city} {when}"
    url           = f"https://www.google.com/search?q={quote_plus(search_query)}"

    try:
        opened = webbrowser.open(url)
        if not opened:
            raise RuntimeError("webbrowser.open returned False")
    except Exception as e:
        msg = f"Sir, I couldn't open the browser for the weather report: {e}"
        _log(msg, player)
        return msg

    msg = f"Showing the weather for {city}, {when}, sir."
    _log(msg, player)

    if session_memory:
        try:
            session_memory.set_last_search(query=search_query, response=msg)
        except Exception as e:
            log.debug("%s", e)

    return msg


def _log(message: str, player=None) -> None:
    log.info(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"OPERO: {message}")
        except Exception as e:
            log.debug("%s", e)


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "weather_report",
    "description": "Gives the weather report to user",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {
                "type": "STRING",
                "description": "City name"
            }
        },
        "required": [
            "city"
        ]
    },
    "handler": weather_action,
}

VALIDATOR = {
    "city": [{"type": str, "required": True, "max_len": 200}],
}
