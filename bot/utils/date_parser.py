import re
from datetime import datetime, timedelta, timezone

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DATE_PRESETS = [
    ("Today", "today"),
    ("Yesterday", "yesterday"),
    ("Last 7 days", "7d"),
    ("Last 14 days", "14d"),
    ("Last 30 days", "30d"),
    ("Last 3 months", "90d"),
    ("Last 6 months", "180d"),
]


def _fmt(dt: datetime, end_of_day: bool) -> str:
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=0)
    else:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_date_input(s: str, end_of_day: bool = False) -> str | None:
    s = s.strip().lower()
    now = datetime.now(timezone.utc)

    match = re.match(r"^(\d+)\s*(d|day|days|h|hour|hours|w|week|weeks|mo|mos|month|months)$", s)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        if unit in ("d", "day", "days"):
            dt = now - timedelta(days=value)
        elif unit in ("h", "hour", "hours"):
            dt = now - timedelta(hours=value)
        elif unit in ("w", "week", "weeks"):
            dt = now - timedelta(weeks=value)
        else:
            dt = now - timedelta(days=value * 30)
        return _fmt(dt, end_of_day)

    if s == "today":
        return _fmt(now, end_of_day)
    if s == "yesterday":
        return _fmt(now - timedelta(days=1), end_of_day)

    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if match:
        dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return _fmt(dt.replace(tzinfo=timezone.utc), end_of_day)

    match = re.match(r"^(\d{4})/(\d{2})/(\d{2})$", s)
    if match:
        dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return _fmt(dt.replace(tzinfo=timezone.utc), end_of_day)

    match = re.match(r"^([a-z]+)\s+(\d{1,2})(?:,?\s*(\d{4}))?$", s)
    if match and match.group(1) in _MONTHS:
        m = _MONTHS[match.group(1)]
        d = int(match.group(2))
        y = int(match.group(3)) if match.group(3) else now.year
        dt = datetime(y, m, d)
        return _fmt(dt.replace(tzinfo=timezone.utc), end_of_day)

    match = re.match(r"^(\d{1,2})\s+([a-z]+)(?:,?\s*(\d{4}))?$", s)
    if match and match.group(2) in _MONTHS:
        d = int(match.group(1))
        m = _MONTHS[match.group(2)]
        y = int(match.group(3)) if match.group(3) else now.year
        dt = datetime(y, m, d)
        return _fmt(dt.replace(tzinfo=timezone.utc), end_of_day)

    if "T" in s:
        try:
            datetime.fromisoformat(s)
            return s
        except Exception:
            pass

    return None


def get_date_choices(current: str) -> list:
    from discord import app_commands
    current = current.strip().lower()
    choices: list[app_commands.Choice[str]] = []
    for label, value in _DATE_PRESETS:
        if not current or current in label.lower() or current in value.lower():
            choices.append(app_commands.Choice(name=label, value=value))
    return choices[:25]
