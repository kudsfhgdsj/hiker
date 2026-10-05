"""German formatting for the templates."""

from datetime import datetime


def _number(value: float, digits: int = 0) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", " ").replace(".", ",").replace(" ", ".")


def number(value, digits: int = 0) -> str:
    return "–" if value is None else _number(float(value), digits)


def weight(grams) -> str:
    if grams is None:
        return "–"
    if abs(grams) < 1000:
        return f"{_number(grams)} g"
    return f"{_number(grams / 1000, 2).rstrip('0').rstrip(',')} kg"


def money(amount, currency: str) -> str:
    return f"{_number(amount, 2)} {currency}"


def distance(meters) -> str:
    if meters is None:
        return "–"
    if meters < 1000:
        return f"{_number(meters)} m"
    return f"{_number(meters / 1000, 1)} km"


def meters(value) -> str:
    return "–" if value is None else f"{_number(value)} m"


def duration(minutes) -> str:
    if minutes is None:
        return "–"
    hours, rest = divmod(int(minutes), 60)
    if hours == 0:
        return f"{rest} min"
    return f"{hours} h" if rest == 0 else f"{hours} h {rest} min"


def _parse(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def date(value) -> str:
    parsed = _parse(value)
    return "" if parsed is None else parsed.strftime("%d.%m.%Y")


def datetime_text(value) -> str:
    """Date and time in UTC; the page converts it to local time in the browser."""
    parsed = _parse(value)
    return "" if parsed is None else parsed.strftime("%d.%m.%Y %H:%M UTC")


def time_text(value) -> str:
    parsed = _parse(value)
    return "" if parsed is None else parsed.strftime("%H:%M")


FILTERS = {
    "number": number,
    "weight": weight,
    "money": money,
    "distance": distance,
    "meters": meters,
    "duration": duration,
    "date": date,
    "datetime": datetime_text,
    "time": time_text,
}
