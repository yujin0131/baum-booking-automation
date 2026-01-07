from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from .database import Base
from src.utils.datetime_utils import now_kst
from src.utils.constants import (
    BOOKING_STATUS_NEW,
    SMS_STATUS_PENDING,
    SMS_TYPE_WELCOME,
)


class BookingStatus(str, enum.Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    SMS_SENT = "sms_sent"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


class SMSStatus(str, enum.Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"


class SMSType(str, enum.Enum):
    WELCOME = "welcome"
    CHECK_IN_GUIDE = "check_in_guide"
    FACILITY_INFO = "facility_info"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="ID")

    naver_booking_id = Column(String(255), unique=True, index=True, nullable=False, comment="네이버 예약 ID")

    guest_name = Column(String(100), nullable=False, comment="예약자 이름")
    guest_phone = Column(String(20), nullable=False, index=True, comment="예약자 전화번호")
    guest_count = Column(Integer, default=1, comment="예약 인원")

    check_in_date = Column(DateTime(timezone=True), nullable=False, index=True, comment="체크인 날짜")
    check_out_date = Column(DateTime(timezone=True), nullable=False, comment="체크아웃 날짜")
    booking_date = Column(DateTime(timezone=True), nullable=False, comment="예약 등록 날짜")

    room_type = Column(String(100), nullable=False, comment="객실 타입")
    room_number = Column(String(50), nullable=True, comment="객실 번호")
    room_password = Column(String(50), nullable=True, comment="객실 비밀번호")

    special_request = Column(Text, nullable=True, comment="요청사항")

    status = Column(SQLEnum(BookingStatus), default=BookingStatus.NEW, nullable=False, index=True, comment="예약 상태")
    is_immediate_booking = Column(Boolean, default=False, comment="당일 예약 여부")
    sms_sent = Column(Boolean, default=False, comment="모든 SMS 발송 완료 여부")

    created_at = Column(DateTime(timezone=True), default=now_kst, nullable=False, comment="레코드 생성 시간")
    updated_at = Column(DateTime(timezone=True), default=now_kst, onupdate=now_kst, nullable=False, comment="레코드 수정 시간")

    sms_logs = relationship("SMSLog", back_populates="booking", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Booking(id={self.id}, guest={self.guest_name}, check_in={self.check_in_date}, status={self.status})>"

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
            "room_password": self.room_password,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "is_immediate_booking": self.is_immediate_booking,
            "sms_sent": self.sms_sent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SMSLog(Base):
    __tablename__ = "sms_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="ID")

    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True, comment="예약 ID")

    sms_type = Column(SQLEnum(SMSType), nullable=False, index=True, comment="SMS 타입 (WELCOME / CHECK_IN_GUIDE / FACILITY_INFO)")
    recipient_phone = Column(String(20), nullable=False, comment="수신자 전화번호")
    message_content = Column(Text, nullable=False, comment="메시지 내용")

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
