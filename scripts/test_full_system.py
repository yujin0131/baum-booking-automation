"""
크롤링 → 예약 생성 → SMS 로그 생성 → 알림톡 발송 전체 테스트
"""
import asyncio
from src.services.scheduler import BookingScheduler
from src.models import get_session
from src.models.booking import Booking, SMSLog
from loguru import logger


async def test_full_system():
    print("=" * 60)
    print("🧪 크롤링부터 알림톡 발송까지 전체 시스템 테스트")
    print("=" * 60)

    # 1. Scheduler 초기화
    print("\n[1] Scheduler 초기화")
    scheduler = BookingScheduler()
    await scheduler.initialize()
    print(f"✅ Scheduler 초기화 완료")
    print(f"   - Scraper: {type(scheduler.scraper).__name__}")
    print(f"   - Kakao Sender: {type(scheduler.kakao_sender).__name__}")
    print(f"   - Test Mode: {scheduler.test_mode}")

    # 2. 크롤링 실행
    print("\n[2] 예약 크롤링 실행")
    try:
        await scheduler.scrape_and_process_bookings()
        print("✅ 크롤링 완료")
    except Exception as e:
        print(f"❌ 크롤링 실패: {e}")
        import traceback
        traceback.print_exc()

    # 3. DB 확인
    print("\n[3] DB 상태 확인")
    with get_session() as db:
        total_bookings = db.query(Booking).count()
        recent_bookings = db.query(Booking).order_by(Booking.id.desc()).limit(3).all()
        total_sms_logs = db.query(SMSLog).count()

        print(f"✅ 총 예약: {total_bookings}건")
        print(f"✅ 총 SMS 로그: {total_sms_logs}건")

        if recent_bookings:
            print(f"\n   최근 예약 {len(recent_bookings)}건:")
            for booking in recent_bookings:
                print(f"   - [{booking.id}] {booking.guest_name} | {booking.room_number}호")
                print(f"     체크인: {booking.check_in_date} | 상태: {booking.status.value}")

                # SMS 로그 확인
                sms_logs = db.query(SMSLog).filter_by(booking_id=booking.id).all()
                print(f"     SMS 로그: {len(sms_logs)}건")
                for log in sms_logs:
                    print(f"       - {log.sms_type.value} | template: {log.template_key} | status: {log.status.value}")

    # 4. 발송 대기 중인 SMS 확인
    print("\n[4] 발송 대기 중인 SMS 확인")
    with get_session() as db:
        from src.services.booking_manager import BookingManager
        booking_manager = BookingManager(db)

        pending_logs = booking_manager.get_pending_sms_logs()
        print(f"✅ 발송 대기 중: {len(pending_logs)}건")

        if pending_logs:
            print(f"\n   발송 예정:")
            for log in pending_logs[:3]:  # 최대 3건만 표시
                print(f"   - [{log.id}] {log.recipient_phone}")
                print(f"     Template: {log.template_key}")
                print(f"     Scheduled: {log.scheduled_time}")

    # 5. SMS 발송 시뮬레이션
    print("\n[5] 알림톡 발송 시뮬레이션")
    try:
        await scheduler.send_pending_sms()
        print("✅ 발송 작업 완료")
    except Exception as e:
        print(f"❌ 발송 실패: {e}")
        import traceback
        traceback.print_exc()

    # 6. 발송 결과 확인
    print("\n[6] 발송 결과 확인")
    with get_session() as db:
        from src.models.booking import SMSStatus

        sent_count = db.query(SMSLog).filter_by(status=SMSStatus.SENT).count()
        failed_count = db.query(SMSLog).filter_by(status=SMSStatus.FAILED).count()
        scheduled_count = db.query(SMSLog).filter_by(status=SMSStatus.SCHEDULED).count()

        print(f"✅ 발송 완료: {sent_count}건")
        print(f"⚠️  발송 실패: {failed_count}건")
        print(f"⏰ 발송 대기: {scheduled_count}건")

    # 7. Cleanup
    print("\n[7] Cleanup")
    await scheduler.shutdown()
    print("✅ Scheduler 종료")

    print("\n" + "=" * 60)
    print("✨ 전체 시스템 테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_full_system())
