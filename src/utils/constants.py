from typing import Dict

_config = None


def _get_config():
    global _config
    if _config is None:
        from src.utils.config_loader import config
        _config = config
    return _config


# SMS 타입
SMS_TYPE_CHECK_IN_GUIDE = "check_in_guide"
SMS_TYPE_FACILITY_INFO = "facility_info"
SMS_TYPES = [SMS_TYPE_CHECK_IN_GUIDE, SMS_TYPE_FACILITY_INFO]

# SMS 상태
SMS_STATUS_PENDING = "pending"
SMS_STATUS_SCHEDULED = "scheduled"
SMS_STATUS_SENT = "sent"
SMS_STATUS_FAILED = "failed"

# 예약 상태
BOOKING_STATUS_NEW = "new"
BOOKING_STATUS_CONFIRMED = "confirmed"
BOOKING_STATUS_SMS_SENT = "sms_sent"
BOOKING_STATUS_CHECKED_IN = "checked_in"
BOOKING_STATUS_CHECKED_OUT = "checked_out"
BOOKING_STATUS_CANCELLED = "cancelled"

# 기본값
CHECK_IN_DEFAULT_TIME = "16:00"
CHECK_OUT_DEFAULT_TIME = "11:00"
APP_MAIN_LOOP_SLEEP_SECONDS = 60

MAX_SMS_RETRIES = 3
SMS_RETRY_DELAY_SECONDS = 60
SMS_BATCH_SIZE = 10
SMS_BATCH_DELAY_SECONDS = 0.1

SCRAPER_DEFAULT_TIMEOUT = 30000
SCRAPER_MAX_RETRIES = 3


def get_room_password(room_number: str) -> str:
    """객실 비밀번호 조회"""
    return _get_config().accommodation.get_room_password(room_number)
