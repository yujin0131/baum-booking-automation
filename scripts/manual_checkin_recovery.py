#!/usr/bin/env python3
"""
장애 복구용 스크립트: 크롤링 후 바로 입실 처리 (문자 발송 없이)

사용법:
    python scripts/manual_checkin_recovery.py

Docker 컨테이너 내에서 실행:
    docker exec -it staytuned-booking-automation python scripts/manual_checkin_recovery.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.booking import Booking, SMSLog, BookingStatus, SMSStatus, SMSType
from src.utils.datetime_utils import now_kst


async def crawl_and_mark_checked_in(db):
    """크롤링 후 바로 입실 처리 (문자 발송 없이)"""
    try:
        from src.services.smartplace_crawler import SmartplaceCrawler

        crawler = SmartplaceCrawler(headless=True)
        print("[*] 크롤링 시작...")

        bookings_data = await crawler.get_new_bookings()

        if bookings_data is None:
            print("[!] 크롤링 실패: 브라우저 오류")
            await crawler.close()
            return 0

        if not bookings_data:
            print("[!] 크롤링 결과: 오늘 체크인 예약 없음")
            await crawler.close()
            return 0

        print(f"[OK] 크롤링 완료: {len(bookings_data)}건 발견\n")

        count = 0
        for data in bookings_data:
            naver_booking_id = data.get("naver_booking_id")

            # 이미 존재하는지 확인
            existing = db.query(Booking).filter(Booking.naver_booking_id == naver_booking_id).first()
            if existing:
                print(f"  [스킵] {data.get('guest_name')} - 이미 존재 (ID: {existing.id})")
                continue

            # 새 예약 생성 (바로 CHECKED_IN 상태로)
            booking = Booking(
                naver_booking_id=naver_booking_id,
                guest_name=data.get("guest_name"),
                guest_phone=data.get("guest_phone"),
                guest_count=data.get("guest_count", 1),
                check_in_date=data.get("check_in_date"),
                check_out_date=data.get("check_out_date"),
                booking_date=data.get("booking_date") or now_kst(),
                room_type=data.get("room_type", ""),
                room_number=data.get("room_number"),
                special_request=data.get("special_request"),
                pet_option=data.get("pet_option", False),
                status=BookingStatus.CHECKED_IN,
                is_immediate_booking=False,
            )

            db.add(booking)
            db.flush()

            # SMS 로그도 SENT로 생성 (중복 발송 방지)
            sms_log = SMSLog(
                booking_id=booking.id,
                sms_type=SMSType.CHECK_IN_GUIDE,
                recipient_phone=booking.guest_phone,
                message_content="[장애복구] 수동 입실 처리",
                status=SMSStatus.SENT,
                sent_time=now_kst(),
            )
            db.add(sms_log)

            sms_log2 = SMSLog(
                booking_id=booking.id,
                sms_type=SMSType.FACILITY_INFO,
                recipient_phone=booking.guest_phone,
                message_content="[장애복구] 수동 입실 처리",
                status=SMSStatus.SENT,
                sent_time=now_kst(),
            )
            db.add(sms_log2)

            count += 1
            print(f"  [추가] {booking.guest_name} ({booking.room_number}) → CHECKED_IN")

        db.commit()
        await crawler.close()

        print(f"\n[완료] {count}건 입실 처리됨")
        return count

    except Exception as e:
        print(f"[!] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    print("=" * 60)
    print("   장애 복구: 크롤링 → 입실 처리 (문자 발송 안 함)")
    print("=" * 60)

    confirm = input("\n진행할까요? (y/n): ")
    if confirm.lower() != "y":
        print("취소됨")
        return

    db = SessionLocal()
    try:
        asyncio.run(crawl_and_mark_checked_in(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
