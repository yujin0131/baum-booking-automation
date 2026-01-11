import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from loguru import logger

from src.models.booking import Booking, SMSLog, BookingStatus, SMSStatus, SMSType, KakaoTemplate
from src.utils.datetime_utils import (
    now_kst,
    to_kst,
    combine_date_and_time,
    get_time_from_string,
    format_date_korean,
)
from src.utils.constants import (
    SMS_TYPE_CHECK_IN_GUIDE,
    SMS_TYPE_FACILITY_INFO,
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
                "check_in_guide_normal": config.sms_templates.check_in_guide_normal,
                "check_in_guide_female_dorm": config.sms_templates.check_in_guide_female_dorm,
                "check_in_guide_male_dorm": config.sms_templates.check_in_guide_male_dorm,
                "facility_info": config.sms_templates.facility_info,
                "pet_info": config.sms_templates.pet_info,
            }
        return self._templates

    def _get_kakao_template_code(self, template_key: str) -> Optional[str]:
        """템플릿 키로 Solapi 템플릿 코드 조회"""
        try:
            template = self.db.query(KakaoTemplate).filter(
                KakaoTemplate.template_key == template_key,
                KakaoTemplate.is_active == True
            ).first()
            return template.template_code if template else None
        except Exception as e:
            logger.warning(f"Failed to get template_code for {template_key}: {e}")
            return None

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

            # 당일 예약
            check_in_time = get_time_from_string(settings.check_in_time)
            check_in_datetime = combine_date_and_time(check_in_date, check_in_time)
            is_immediate = booking_date >= check_in_datetime

            # 초기 상태 결정
            today = now_kst().date()
            crawled_status = booking_data.get("booking_status", "").strip()

            # 1. 크롤링한 상태가 체크인 완료면 CHECKED_IN으로 저장
            if crawled_status in ["체크인 완료", "checked_in", "입실완료", "입실"]:
                initial_status = BookingStatus.CHECKED_IN
            # 2. 체크인 날짜가 오늘보다 이전이면 이미 입실한 것으로 간주
            elif check_in_date < today:
                initial_status = BookingStatus.CHECKED_IN
            # 3. 그 외에는 신규 예약
            else:
                initial_status = BookingStatus.NEW

            booking = Booking(
                naver_booking_id=naver_booking_id,
                guest_name=booking_data.get("guest_name"),
                guest_phone=booking_data.get("guest_phone"),
                guest_count=booking_data.get("guest_count", 1),
                check_in_date=check_in_date,
                check_out_date=booking_data.get("check_out_date"),
                booking_date=booking_date,
                room_type=booking_data.get("room_type"),
                room_number=booking_data.get("room_number"),
                special_request=booking_data.get("special_request"),
                pet_option=booking_data.get("pet_option", False),
                room_password=booking_data.get("room_password", "1234"),
                status=initial_status,
                is_immediate_booking=is_immediate,
            )

            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)

            logger.success(
                f"[Success] {booking.guest_name}"
                f" - check-in: {booking.check_in_date.strftime('%Y년 %m월 %d일')}"
                f" - immediate: {is_immediate}"
            )

            return booking

        except Exception as e:
            logger.error(f"[Error] {e}")
            self.db.rollback()
            return None

    def create_sms_logs_for_booking(self, booking: Booking) -> List[SMSLog]:
        try:
            # 이미 체크인한 예약은 SMS를 보내지 않음
            if booking.status == BookingStatus.CHECKED_IN:
                logger.info(f"[skip] {booking.guest_name} - 이미 체크인 완료된 예약이므로 SMS 생성하지 않음")
                return []

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

            # 3시 30분 기준으로 즉시 발송 여부 판단
            guide_time_scheduled = check_in_datetime - timedelta(minutes=30)  # 3:30 PM

            is_immediate_send = now >= guide_time_scheduled

            if is_immediate_send:
                # 3시 30분 이후 예약 → 즉시 발송
                guide_time = now
                facility_time = now + timedelta(minutes=1)
            else:
                # 3시 30분 이전 예약 → 3시 30분에 발송
                guide_time = guide_time_scheduled
                facility_time = guide_time + timedelta(minutes=1)

            # 테스트용: guest_name에 원래 수신자 번호 추가
            test_guest_name = f"{booking.guest_name} ({booking.guest_phone})"

            # 객실별 체크인 안내 템플릿 선택
            templates = self._get_sms_templates()

            if booking.room_number == "103":
                checkin_template_key = "check_in_guide_female_dorm"
            elif booking.room_number == "205":
                checkin_template_key = "check_in_guide_male_dorm"
            else:
                checkin_template_key = "check_in_guide_normal"

            # 템플릿별 실제 필요한 변수만 정의
            TEMPLATE_VARS = {
                "check_in_guide_normal": {
                    "guest_name": test_guest_name,
                    "room_number": booking.room_number or "확인 후 안내",
                    "room_password": booking.room_password,
                },
                "check_in_guide_female_dorm": {
                    "guest_name": test_guest_name,
                    "room_password": booking.room_password,
                },
                "check_in_guide_male_dorm": {
                    "guest_name": test_guest_name,
                    "room_password": booking.room_password,
                },
                "facility_info": None,
                "pet_info": None,
            }

            # SMS 스케줄: CHECK_IN_GUIDE + FACILITY_INFO
            sms_schedule = {
                SMS_TYPE_CHECK_IN_GUIDE: (guide_time, checkin_template_key),
                SMS_TYPE_FACILITY_INFO: (facility_time, "facility_info"),
            }

            # CHECK_IN_GUIDE + FACILITY_INFO SMS 생성
            for sms_type, (sms_scheduled_time, template_key) in sms_schedule.items():
                template = templates.get(template_key, "")
                template_vars = TEMPLATE_VARS.get(template_key)

                try:
                    if template_vars:
                        message = template.format(**template_vars)
                    else:
                        message = template
                except KeyError as e:
                    logger.warning(f"[Warn] {e}, default template")
                    message = template

                # 템플릿별 변수 저장 (없으면 null)
                template_vars_json = json.dumps(template_vars, ensure_ascii=False) if template_vars else None

                # Solapi 템플릿 코드 조회
                template_code = self._get_kakao_template_code(template_key)

                sms_log = SMSLog(
                    booking_id=booking.id,
                    sms_type=SMSType(sms_type),
                    recipient_phone=booking.guest_phone,
                    message_content=message,
                    template_key=template_key,  # 템플릿 키 저장
                    template_code=template_code,  # Solapi 템플릿 코드 저장
                    template_vars=template_vars_json,  # 템플릿 변수 저장 (JSON)
                    status=SMSStatus.SCHEDULED,  # 스케줄링된 상태로 생성
                    scheduled_time=sms_scheduled_time,
                    sent_time=None,
                    retry_count=0,
                    max_retries=settings.max_retries,
                )

                self.db.add(sms_log)
                sms_logs.append(sms_log)

            # 104호 애견옵션 감지 및 추가 SMS 생성
            if booking.room_number == "104" and booking.pet_option:
                pet_template = templates.get("pet_info", "")
                try:
                    pet_message = pet_template.format(**kakao_vars)
                except KeyError as e:
                    logger.warning(f"[Warn] {e}, default pet template")
                    pet_message = pet_template

                pet_time = guide_time + timedelta(minutes=2) if not is_immediate_send else now + timedelta(minutes=2)
                pet_template_code = self._get_kakao_template_code("pet_info")

                pet_sms_log = SMSLog(
                    booking_id=booking.id,
                    sms_type=SMSType.FACILITY_INFO,
                    recipient_phone=booking.guest_phone,
                    message_content=pet_message,
                    template_key="pet_info",
                    template_code=pet_template_code,
                    template_vars=None,  # pet_info는 변수 없음
                    status=SMSStatus.SCHEDULED,
                    scheduled_time=pet_time,
                    retry_count=0,
                    max_retries=settings.max_retries,
                )

                self.db.add(pet_sms_log)
                sms_logs.append(pet_sms_log)
                logger.info(f"[Pet Option] 104호 애견옵션 감지 - SMS 로그 생성")

            self.db.commit()

            if is_immediate_send:
                logger.success(
                    f"SMS log - ({booking.id}) "
                    f"immediate: send all now"
                )
            else:
                logger.success(
                    f"SMS log - ({booking.id}) "
                    f"GUIDE/FACILITY: {format_date_korean(guide_time)}"
                )

            return sms_logs

        except Exception as e:
            import traceback
            logger.error(f"[Error] create_sms_logs_for_booking {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            booking = sms_log.booking

            if success:
                sms_log.status = SMSStatus.SENT
                sms_log.sent_time = now_kst()
                if data:
                    sms_log.provider_response = json.dumps(data, ensure_ascii=False)
                logger.info(f"SMS {sms_log.id} send fin")

                # 해당 예약의 모든 SMS가 발송 완료되었는지 확인
                if booking and booking.all_sms_sent and booking.status == BookingStatus.NEW:
                    booking.status = BookingStatus.SMS_SENT
                    logger.info(f"[Status Update] {booking.guest_name} 예약 상태: NEW → SMS_SENT")
            else:
                sms_log.status = SMSStatus.FAILED
                sms_log.error_message = str(data) if data else "Unknown error"
                sms_log.retry_count += 1
                logger.warning(
                    f"[Warn] {sms_log.id} "
                    f"(retry {sms_log.retry_count}/{sms_log.max_retries})"
                )

                # 재시도 불가능하면 예약 상태를 SMS_FAILED로 변경
                if booking and not sms_log.can_retry and booking.status == BookingStatus.NEW:
                    booking.status = BookingStatus.SMS_FAILED
                    logger.info(f"[Status Update] {booking.guest_name} 예약 상태: NEW → SMS_FAILED")

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
