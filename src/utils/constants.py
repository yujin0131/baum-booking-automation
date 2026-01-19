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
SMS_TYPE_FACILITY_INFO = "facility_info"  # 포틀럭파티 안내
SMS_TYPE_POTLUCK_DAILY = "potluck_daily"  # 연박자 매일 포틀럭 안내
SMS_TYPE_PET_INFO = "pet_info"  # 애견동반 안내
SMS_TYPES = [SMS_TYPE_CHECK_IN_GUIDE, SMS_TYPE_FACILITY_INFO, SMS_TYPE_POTLUCK_DAILY, SMS_TYPE_PET_INFO]

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

# 크롤링 스케줄 설정
SCRAPE_MIN_INTERVAL_MINUTES = 8
SCRAPE_MAX_INTERVAL_MINUTES = 13

# 페이지 로딩 딜레이 (밀리초)
PAGE_LOAD_MIN_DELAY_MS = 3000
PAGE_LOAD_MAX_DELAY_MS = 5000

# 크롤러 메모리 관리
BROWSER_RESTART_INTERVAL = 1  # 매 크롤링마다 브라우저 재시작


def get_room_password(room_number: str) -> str:
    """객실 비밀번호 조회"""
    return _get_config().accommodation.get_room_password(room_number)
