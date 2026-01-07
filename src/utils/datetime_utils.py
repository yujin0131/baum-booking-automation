from datetime import datetime, time
from typing import Optional, Union
import pytz
from zoneinfo import ZoneInfo

from config.settings import settings

def get_kst_timezone():
    return ZoneInfo("Asia/Seoul")

def now_kst() -> datetime:
    return datetime.now(get_kst_timezone())

def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=get_kst_timezone())
    return dt.astimezone(get_kst_timezone())


def format_date(dt: datetime, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    kst_dt = to_kst(dt)
    return kst_dt.strftime(format_string)

def format_date_korean(dt: datetime) -> str:
    kst_dt = to_kst(dt)
    return kst_dt.strftime("%Y년 %m월 %d일 %H시 %M분")

def parse_date(date_string: str, format_string: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    try:
        dt = datetime.strptime(date_string, format_string)
        return dt.replace(tzinfo=get_kst_timezone())
    except (ValueError, TypeError):
        return None

def get_time_from_string(time_string: str) -> Optional[time]:
    try:
        hour, minute = map(int, time_string.split(":"))
        return time(hour=hour, minute=minute)
    except (ValueError, AttributeError):
        return None

def combine_date_and_time(date: datetime, time_obj: time) -> datetime:
    combined = datetime.combine(date.date(), time_obj)
    return combined.replace(tzinfo=get_kst_timezone())

def is_same_day(dt1: datetime, dt2: datetime) -> bool:
    kst_dt1 = to_kst(dt1)
    kst_dt2 = to_kst(dt2)
    return kst_dt1.date() == kst_dt2.date()

def hours_until(target_dt: datetime, from_dt: Optional[datetime] = None) -> float:
    if from_dt is None:
        from_dt = now_kst()

    delta = target_dt - from_dt
    return delta.total_seconds() / 3600

def is_past(dt: datetime) -> bool:
    return dt < now_kst()

def is_today(dt: datetime) -> bool:
    return is_same_day(dt, now_kst())
