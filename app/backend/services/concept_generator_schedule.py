from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def detect_local_timezone() -> str:
    configured = os.getenv("DINKLY_TIMEZONE")
    if configured and valid_timezone(configured):
        return configured
    localtime = Path("/etc/localtime")
    if localtime.is_symlink():
        target = str(localtime.resolve())
        for marker in ("/zoneinfo/", "/zones/"):
            if marker in target:
                candidate = target.split(marker, 1)[1]
                if valid_timezone(candidate):
                    return candidate
    key = getattr(datetime.now().astimezone().tzinfo, "key", None)
    return key if isinstance(key, str) and valid_timezone(key) else "America/New_York"


def valid_timezone(value: str) -> bool:
    try:
        ZoneInfo(value)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def scheduled_datetime(day: date, daily_time: str, timezone: str) -> datetime:
    hour, minute = (int(part) for part in daily_time.split(":"))
    return datetime.combine(day, time(hour, minute), tzinfo=ZoneInfo(timezone))


def is_scheduled_day(day: date, schedule_days: str) -> bool:
    return schedule_days == "every_day" or day.weekday() < 5


def next_scheduled_run(now: datetime, daily_time: str, timezone: str, schedule_days: str) -> datetime:
    local = now.astimezone(ZoneInfo(timezone))
    candidate_day = local.date()
    candidate = scheduled_datetime(candidate_day, daily_time, timezone)
    if candidate <= local or not is_scheduled_day(candidate_day, schedule_days):
        candidate_day += timedelta(days=1)
        while not is_scheduled_day(candidate_day, schedule_days):
            candidate_day += timedelta(days=1)
        candidate = scheduled_datetime(candidate_day, daily_time, timezone)
    return candidate
