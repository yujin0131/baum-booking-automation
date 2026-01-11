from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from .database import Base
from src.utils.datetime_utils import now_kst
from src.utils.constants import (
    BOOKING_STATUS_NEW,
    SMS_STATUS_PENDING,
)


class BookingStatus(str, enum.Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    SMS_SENT = "sms_sent"
    SMS_FAILED = "sms_failed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


class SMSStatus(str, enum.Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"


class SMSType(str, enum.Enum):
    CHECK_IN_GUIDE = "check_in_guide"
    FACILITY_INFO = "facility_info"


class KakaoTemplate(Base):
    """카카오 알림톡 템플릿 관리"""
    __tablename__ = "kakao_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="ID")
    template_key = Column(String(100), unique=True, nullable=False, index=True, comment="템플릿 키")
    template_code = Column(String(100), nullable=False, comment="카카오 승인 템플릿 코드")
    name = Column(String(200), nullable=False, comment="템플릿 이름")
    description = Column(Text, nullable=True, comment="템플릿 설명")
    variables = Column(Text, nullable=True, comment="필수 변수 목록 (JSON)")
    buttons = Column(Text, nullable=True, comment="버튼 정보 (JSON)")
    is_active = Column(Boolean, default=True, nullable=False, comment="활성화 여부")
    created_at = Column(DateTime(timezone=True), default=now_kst, nullable=False, comment="생성 시간")
    updated_at = Column(DateTime(timezone=True), default=now_kst, onupdate=now_kst, nullable=False, comment="수정 시간")

    def __repr__(self):
        return f"<KakaoTemplate(id={self.id}, key={self.template_key}, name={self.name})>"

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "template_key": self.template_key,
            "template_code": self.template_code,
            "name": self.name,
            "description": self.description,
            "variables": json.loads(self.variables) if self.variables else [],
            "buttons": json.loads(self.buttons) if self.buttons else [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="ID")

    naver_booking_id = Column(String(255), unique=True, index=True, nullable=False, comment="네이버 예약 ID")

    guest_name = Column(String(100), nullable=False, comment="예약자 이름")
    guest_phone = Column(String(20), nullable=False, index=True, comment="예약자 전화번호")
    guest_count = Column(Integer, default=1, comment="예약 인원")

    check_in_date = Column(Date, nullable=False, index=True, comment="체크인 날짜")
    check_out_date = Column(Date, nullable=False, comment="체크아웃 날짜")
    booking_date = Column(DateTime(timezone=True), nullable=False, comment="예약 등록 날짜")

    room_type = Column(String(100), nullable=False, comment="객실 타입")
    room_number = Column(String(50), nullable=True, comment="객실 번호")
    room_password = Column(String(50), nullable=True, comment="객실 비밀번호")

    special_request = Column(Text, nullable=True, comment="요청사항")
    pet_option = Column(Boolean, default=False, comment="애견동반 옵션 여부")

    status = Column(SQLEnum(BookingStatus), default=BookingStatus.NEW, nullable=False, index=True, comment="예약 상태")
    is_immediate_booking = Column(Boolean, default=False, comment="당일 예약 여부")

    created_at = Column(DateTime(timezone=True), default=now_kst, nullable=False, comment="레코드 생성 시간")
    updated_at = Column(DateTime(timezone=True), default=now_kst, onupdate=now_kst, nullable=False, comment="레코드 수정 시간")

    sms_logs = relationship("SMSLog", back_populates="booking", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Booking(id={self.id}, guest={self.guest_name}, check_in={self.check_in_date}, status={self.status})>"

    def get_sms_status(self, sms_type: SMSType) -> dict:
        """특정 SMS 타입의 발송 상태 조회"""
        for log in self.sms_logs:
            if log.sms_type == sms_type:
                return {
                    "status": log.status.value if isinstance(log.status, enum.Enum) else log.status,
                    "sent_time": log.sent_time,
                    "scheduled_time": log.scheduled_time,
                }
        return {"status": None, "sent_time": None, "scheduled_time": None}

    @property
    def all_sms_sent(self) -> bool:
        """모든 SMS가 발송 완료되었는지 확인"""
        if not self.sms_logs:
            return False
        return all(log.status == SMSStatus.SENT for log in self.sms_logs)

    @property
    def sms_status_summary(self) -> dict:
        """SMS 타입별 발송 상태 요약"""
        summary = {}
        for log in self.sms_logs:
            type_key = log.sms_type.value if isinstance(log.sms_type, enum.Enum) else log.sms_type
            summary[type_key] = log.status.value if isinstance(log.status, enum.Enum) else log.status
        return summary

    @property
    def display_status(self) -> tuple[str, str]:
        """목록 페이지용 표시 상태 (label, color)"""
        from src.utils.datetime_utils import now_kst

        # 취소된 예약
        if self.status == BookingStatus.CANCELLED:
            return ("취소", "danger")

        today = now_kst().date()

        # 예약: 미래 체크인 (오늘이 아닌 경우) - 완료보다 먼저 체크
        if self.check_in_date and self.check_in_date > today:
            return ("예약", "primary")

        # 실패: SMS 발송 실패
        if self.status == BookingStatus.SMS_FAILED:
            return ("실패", "danger")

        # 완료: 오늘/과거 체크인이고 SMS 발송됨 또는 체크인 완료
        if self.status in [BookingStatus.SMS_SENT, BookingStatus.CHECKED_IN, BookingStatus.CHECKED_OUT]:
            return ("완료", "success")

        # 신규: 오늘 체크인인데 아직 SMS 안보냄
        return ("신규", "info")

    def to_dict(self):
        return {
            "id": self.id,
            "naver_booking_id": self.naver_booking_id,
            "guest_name": self.guest_name,
            "guest_phone": self.guest_phone,
            "guest_count": self.guest_count,
            "check_in_date": self.check_in_date.isoformat() if self.check_in_date else None,
            "check_out_date": self.check_out_date.isoformat() if self.check_out_date else None,
            "booking_date": self.booking_date.isoformat() if self.booking_date else None,
            "room_type": self.room_type,
            "room_number": self.room_number,
            "special_request": self.special_request,
            "pet_option": self.pet_option,
            "room_password": self.room_password,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "is_immediate_booking": self.is_immediate_booking,
            "sms_status": self.sms_status_summary,
            "all_sms_sent": self.all_sms_sent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SMSLog(Base):
    __tablename__ = "sms_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="ID")

    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True, comment="예약 ID")

    sms_type = Column(SQLEnum(SMSType), nullable=False, index=True, comment="SMS 타입 (CHECK_IN_GUIDE / FACILITY_INFO)")
    recipient_phone = Column(String(20), nullable=False, comment="수신자 전화번호")
    message_content = Column(Text, nullable=False, comment="메시지 내용")

    # 카카오 알림톡 템플릿 정보
    template_key = Column(String(100), nullable=True, comment="카카오 알림톡 템플릿 키")
    template_code = Column(String(100), nullable=True, comment="Solapi 템플릿 코드 (발송 시점 기록)")
    template_vars = Column(Text, nullable=True, comment="템플릿 변수 (JSON)")

    status = Column(SQLEnum(SMSStatus), default=SMSStatus.PENDING, nullable=False, index=True, comment="상태")
    scheduled_time = Column(DateTime(timezone=True), nullable=True, comment="발송 예정 시간")
    sent_time = Column(DateTime(timezone=True), nullable=True, comment="발송 완료 시간")

    retry_count = Column(Integer, default=0, comment="재시도 횟수")
    max_retries = Column(Integer, default=3, comment="최대 재시도 횟수")

    provider_response = Column(Text, nullable=True, comment="알리고 API 응답")
    error_message = Column(Text, nullable=True, comment="발송 실패 시 에러 메시지")

    created_at = Column(DateTime(timezone=True), default=now_kst, nullable=False, comment="레코드 생성 시간")
    updated_at = Column(DateTime(timezone=True), default=now_kst, onupdate=now_kst, nullable=False, comment="레코드 수정 시간")

    booking = relationship("Booking", back_populates="sms_logs")

    def __repr__(self):
        return f"<SMSLog(id={self.id}, booking_id={self.booking_id}, type={self.sms_type}, status={self.status})>"

    def to_dict(self):
        return {
            "id": self.id,
            "booking_id": self.booking_id,
            "sms_type": self.sms_type.value if isinstance(self.sms_type, enum.Enum) else self.sms_type,
            "recipient_phone": self.recipient_phone,
            "message_content": self.message_content,
            "template_key": self.template_key,
            "template_code": self.template_code,
            "template_vars": self.template_vars,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "sent_time": self.sent_time.isoformat() if self.sent_time else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "provider_response": self.provider_response,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def can_retry(self) -> bool:
        return self.status == SMSStatus.FAILED and self.retry_count < self.max_retries

    @property
    def is_pending_or_scheduled(self) -> bool:
        return self.status in [SMSStatus.PENDING, SMSStatus.SCHEDULED]
