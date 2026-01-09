from typing import Dict

_config = None

def _get_config():
    global _config
    if _config is None:
        from src.utils.config_loader import config
        _config = config
    return _config

SMS_TYPE_CHECK_IN_GUIDE = "check_in_guide"
SMS_TYPE_FACILITY_INFO = "facility_info"
SMS_TYPES = [SMS_TYPE_CHECK_IN_GUIDE, SMS_TYPE_FACILITY_INFO]

SMS_STATUS_PENDING = "pending"
SMS_STATUS_SCHEDULED = "scheduled"
SMS_STATUS_SENT = "sent"
SMS_STATUS_FAILED = "failed"

BOOKING_STATUS_NEW = "new"
BOOKING_STATUS_CONFIRMED = "confirmed"
BOOKING_STATUS_SMS_SENT = "sms_sent"
BOOKING_STATUS_CHECKED_IN = "checked_in"
BOOKING_STATUS_CHECKED_OUT = "checked_out"
BOOKING_STATUS_CANCELLED = "cancelled"

APP_MAIN_LOOP_SLEEP_SECONDS = 60
CHECK_IN_DEFAULT_TIME = "15:00"
CHECK_OUT_DEFAULT_TIME = "11:00"

MAX_SMS_RETRIES = 3
SMS_RETRY_DELAY_SECONDS = 60

SMS_BATCH_SIZE = 10
SMS_BATCH_DELAY_SECONDS = 0.1

SCRAPER_DEFAULT_TIMEOUT = 30000
SCRAPER_MAX_RETRIES = 3


def get_check_in_time() -> str:
    return _get_config().accommodation.check_in_time


def get_check_out_time() -> str:
    return _get_config().accommodation.check_out_time


def get_wifi_ssid() -> str:
    return _get_config().accommodation.wifi_ssid


def get_wifi_password() -> str:
    return _get_config().accommodation.wifi_password


def get_address() -> str:
    return _get_config().accommodation.address


def get_emergency_contact() -> str:
    return _get_config().accommodation.emergency_contact


def get_room_passwords() -> Dict[str, str]:
    return _get_config().accommodation.room_passwords


def get_room_password(room_number: str) -> str:
    return _get_config().accommodation.get_room_password(room_number)


def get_default_password() -> str:
    return _get_config().accommodation.default_password

try:
    DEFAULT_WIFI_SSID = get_wifi_ssid()
    DEFAULT_WIFI_PASSWORD = get_wifi_password()
    DEFAULT_ADDRESS = get_address()
    DEFAULT_EMERGENCY_CONTACT = get_emergency_contact()
    ROOM_NUMBER_PASSWORDS = get_room_passwords()
    DEFAULT_ROOM_PASSWORD = get_default_password()
except Exception:
    DEFAULT_WIFI_SSID = "StayTuned_WiFi"
    DEFAULT_WIFI_PASSWORD = "staytuned0131"
    DEFAULT_ADDRESS = "제주특별자치도 서귀포시 성산읍 성산리 181-1"
    DEFAULT_EMERGENCY_CONTACT = "010-9436-3951"
    ROOM_NUMBER_PASSWORDS = {
        "101": "1010", "102": "1020", "103": "1030", "104": "1040", "105": "1050",
        "201": "2010", "202": "2020", "203": "2030", "204": "2040", "205": "2050",
    }
    DEFAULT_ROOM_PASSWORD = "0000"
