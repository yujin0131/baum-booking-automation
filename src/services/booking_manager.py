import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from loguru import logger

from src.models.booking import Booking, SMSLog, BookingStatus, SMSStatus, SMSType
from src.utils.datetime_utils import (
    now_kst,
    to_kst,
    combine_date_and_time,
    get_time_from_string,
    format_date_korean,
)
from src.utils.constants import (
    SMS_TYPE_WELCOME,
    SMS_TYPE_CHECK_IN_GUIDE,
    SMS_TYPE_FACILITY_INFO,
    CHECK_OUT_DEFAULT_TIME,
    get_wifi_ssid,
    get_wifi_password,
    get_address,
    get_emergency_contact,
)
from config.settings import settings


class BookingManager:

    def __init__(self, db: Session):
        self.db = db
        self._templates = None

    def _get_sms_templates(self) -> Dict[str, str]:
        if self._templates is None:
            from src.utils.config_loader import config
            config.check_and_reload_if_changed()

            self._templates = {
                "welcome": config.sms_templates.welcome,
                "check_in_guide": config.sms_templates.check_in_guide,
                "facility_info": config.sms_templates.facility_info,
            }
        return self._templates

    def _get_special_request_suffix(self) -> str:
        from src.utils.config_loader import config
        return config.sms_templates.special_request_suffix

    def create_or_update_booking(self, booking_data: Dict) -> Optional[Booking]:
        try:
            naver_booking_id = booking_data.get("naver_booking_id")

            existing_booking = (
                self.db.query(Booking)
                .filter(Booking.naver_booking_id == naver_booking_id)
                .first()
            )

            if existing_booking:
                # 크롤링한 상태가 "취소"면 DB 상태 업데이트
                crawled_status = booking_data.get("booking_status", "")
                if crawled_status == "취소" and existing_booking.status != BookingStatus.CANCELLED:
                    existing_booking.status = BookingStatus.CANCELLED
                    self.db.commit()
                    logger.info(f"[cancelled] {existing_booking.guest_name} 예약 취소 처리")
                else:
                    logger.debug(f"[skip] {naver_booking_id} is already.")
                return existing_booking

            booking_date = booking_data.get("booking_date", now_kst())
            check_in_date = booking_data.get("check_in_date")

            if isinstance(check_in_date, str):
                from src.utils.datetime_utils import parse_date
                check_in_date = parse_date(check_in_date)

            booking_date = to_kst(booking_date)
            check_in_date = to_kst(check_in_date)

            # 당일 예약
            check_in_time = get_time_from_string(settings.check_in_time)
            check_in_datetime = combine_date_and_time(check_in_date, check_in_time)
            is_immediate = booking_date >= check_in_datetime

            booking = Booking(
                naver_booking_id=naver_booking_id,
                guest_name=booking_data.get("guest_name"),
                guest_phone=booking_data.get("guest_phone"),
                guest_count=booking_data.get("guest_count", 1),
                check_in_date=check_in_date,
                check_out_date=to_kst(booking_data.get("check_out_date")),
                booking_date=booking_date,
                room_type=booking_data.get("room_type"),
                room_number=booking_data.get("room_number"),
                special_request=booking_data.get("special_request"),
                room_password=booking_data.get("room_password", "1234"),
                status=BookingStatus.NEW,
                is_immediate_booking=is_immediate,
                sms_sent=False,
            )

            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)

            logger.success(
                f"[Success] {booking.guest_name}"
                f" - check-in: {format_date_korean(booking.check_in_date)}"
                f" - immediate: {is_immediate}"
            )

            return booking

        except Exception as e:
            logger.error(f"[Error] {e}")
            self.db.rollback()
            return None

    def create_sms_logs_for_booking(self, booking: Booking) -> List[SMSLog]:
        try:
            existing_logs = (
                self.db.query(SMSLog)
                .filter(SMSLog.booking_id == booking.id)
                .first()
            )
            if existing_logs:
                logger.debug(f"[skip] {booking.id} sms log is already.")
                return []

            sms_logs = []
            now = now_kst()

            check_in_time_str = settings.check_in_time
            check_in_time = get_time_from_string(check_in_time_str)
            check_in_datetime = combine_date_and_time(booking.check_in_date, check_in_time)

            is_immediate_send = now >= check_in_datetime

            if is_immediate_send:
                welcome_time = now
                guide_time = now
                facility_time = now + timedelta(minutes=1)
            else:
                welcome_time = now
                guide_time = check_in_datetime - timedelta(minutes=10)
                facility_time = check_in_datetime - timedelta(minutes=9)

                if guide_time < now:
                    guide_time = now
                    facility_time = now + timedelta(minutes=1)

            template_vars = {
                "guest_name": booking.guest_name,
                "check_in_date": format_date_korean(booking.check_in_date),
                "check_in_time": check_in_time_str,
                "check_out_time": CHECK_OUT_DEFAULT_TIME,
                "room_type": booking.room_type,
                "room_number": booking.room_number or "확인 후 안내",
                "room_info": f"{booking.room_type} ({booking.room_number or '객실번호 별도 안내'})",
                "room_password": booking.room_password,
                "address": get_address(),
                "wifi_ssid": get_wifi_ssid(),
                "wifi_password": get_wifi_password(),
                "emergency_contact": get_emergency_contact(),
                "special_request": booking.special_request or "",
            }

            sms_schedule = {
                SMS_TYPE_WELCOME: welcome_time,
                SMS_TYPE_CHECK_IN_GUIDE: guide_time,
                SMS_TYPE_FACILITY_INFO: facility_time,
            }

            templates = self._get_sms_templates()

            for sms_type, sms_scheduled_time in sms_schedule.items():
                template = templates.get(sms_type, "")

                try:
                    message = template.format(**template_vars)

                    has_special_request = (
                        booking.special_request
                        and booking.special_request.strip() not in ("-", "없음", "")
                    )
                    if has_special_request and sms_type == SMS_TYPE_WELCOME:
                        suffix = self._get_special_request_suffix()
                        message += suffix.format(special_request=booking.special_request)

                except KeyError as e:
                    logger.warning(f"[Warn] {e}, default template")
                    message = template

                sms_log = SMSLog(
                    booking_id=booking.id,
                    sms_type=SMSType(sms_type),
                    recipient_phone=booking.guest_phone,
                    message_content=message,
                    status=SMSStatus.SCHEDULED,
                    scheduled_time=sms_scheduled_time,
                    retry_count=0,
                    max_retries=settings.max_retries,
                )

                self.db.add(sms_log)
                sms_logs.append(sms_log)

            self.db.commit()

            if is_immediate_send:
                logger.success(
                    f"SMS log - ({booking.id})"
                    f"immediate: send all now"
                )
            else:
                logger.success(
                    f"SMS log - ({booking.id})"
                    f"WELCOME: now, GUIDE/FACILITY: {format_date_korean(guide_time)}"
                )

            return sms_logs

        except Exception as e:
            logger.error(f"[Error] create_sms_logs_for_booking {e}")
            self.db.rollback()
            return []

    def get_pending_sms_logs(self) -> List[SMSLog]:
        try:
            now = now_kst()

            pending_logs = (
                self.db.query(SMSLog)
                .filter(
                    SMSLog.status == SMSStatus.SCHEDULED,
                    SMSLog.scheduled_time <= now,
                )
                .order_by(SMSLog.scheduled_time)
                .all()
            )

            return pending_logs

        except Exception as e:
            logger.error(f"[Error] get_pending_sms_logs {e}")
            return []

    def update_sms_status(self, sms_log: SMSLog, success: bool, data: Union[Dict, str] = None):
        try:
            if success:
                sms_log.status = SMSStatus.SENT
                sms_log.sent_time = now_kst()
                if data:
                    sms_log.provider_response = json.dumps(data, ensure_ascii=False)
                logger.info(f"SMS {sms_log.id} send fin")
            else:
                sms_log.status = SMSStatus.FAILED
                sms_log.error_message = str(data) if data else "Unknown error"
                sms_log.retry_count += 1
                logger.warning(
                    f"[Warn] {sms_log.id} "
                    f"(retry {sms_log.retry_count}/{sms_log.max_retries})"
                )

            self.db.commit()

        except Exception as e:
            logger.error(f"[Error] update_sms_status {e}")
            self.db.rollback()

    def mark_sms_as_sent(self, sms_log: SMSLog, provider_response: Dict):
        self.update_sms_status(sms_log, True, provider_response)

    def mark_sms_as_failed(self, sms_log: SMSLog, error_message: str):
        self.update_sms_status(sms_log, False, error_message)

    def get_booking_by_id(self, booking_id: int, with_sms_logs: bool = False) -> Optional[Booking]:
        query = self.db.query(Booking)
        if with_sms_logs:
            query = query.options(joinedload(Booking.sms_logs))
        return query.filter(Booking.id == booking_id).first()

    def get_all_bookings(self, with_sms_logs: bool = False) -> List[Booking]:
        query = self.db.query(Booking)
        if with_sms_logs:
            query = query.options(joinedload(Booking.sms_logs))
        return query.all()

    def get_bookings_by_status(self, status: BookingStatus, with_sms_logs: bool = False) -> List[Booking]:
        query = self.db.query(Booking)
        if with_sms_logs:
            query = query.options(joinedload(Booking.sms_logs))
        return query.filter(Booking.status == status).all()
