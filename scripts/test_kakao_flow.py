"""
카카오 알림톡 전체 플로우 테스트
"""
import asyncio
from datetime import datetime, timedelta
from src.models import get_session
from src.models.booking import Booking, SMSLog, KakaoTemplate
from src.services.booking_manager import BookingManager
from src.services.kakao_sender import KakaoSender
from src.utils.datetime_utils import now_kst
import json


async def test_full_flow():
    print("=" * 60)
    print("🧪 카카오 알림톡 전체 플로우 테스트")
    print("=" * 60)

    # 1. 템플릿 로드 확인
    print("\n[1] 템플릿 로드 확인")
    with get_session() as db:
        templates = db.query(KakaoTemplate).filter_by(is_active=True).all()
        print(f"✅ DB에 {len(templates)}개 템플릿 존재")
        for tmpl in templates:
            print(f"   - {tmpl.template_key}: {tmpl.name}")

    # 2. KakaoSender 초기화
    print("\n[2] KakaoSender 초기화")
    kakao = KakaoSender()
    print(f"✅ KakaoSender 로드: {len(kakao.templates)}개 템플릿")

    # 3. 테스트 예약 생성
    print("\n[3] 테스트 예약 생성")
    with get_session() as db:
        booking_manager = BookingManager(db)

        # 기존 테스트 데이터 정리
        test_booking = db.query(Booking).filter_by(
            naver_booking_id="TEST_KAKAO_001"
        ).first()
        if test_booking:
            db.delete(test_booking)
            db.commit()
            print("   기존 테스트 데이터 삭제")

        # 새 예약 생성
        booking_data = {
            "naver_booking_id": "TEST_KAKAO_001",
            "guest_name": "테스트유저",
            "guest_phone": "01012345678",
            "guest_count": 2,
            "check_in_date": (now_kst() + timedelta(days=1)).date(),
            "check_out_date": (now_kst() + timedelta(days=2)).date(),
            "booking_date": now_kst(),
            "room_type": "일반실",
            "room_number": "102",
            "room_password": "1234",
            "special_request": None,
            "pet_option": False
        }

        booking = booking_manager.create_or_update_booking(booking_data)
        print(f"✅ 예약 생성: {booking.guest_name} (ID: {booking.id})")

    # 4. SMS 로그 생성 (template_key 포함)
    print("\n[4] SMS 로그 생성")
    with get_session() as db:
        booking_manager = BookingManager(db)
        booking = db.query(Booking).filter_by(
            naver_booking_id="TEST_KAKAO_001"
        ).first()

        sms_logs = booking_manager.create_sms_logs_for_booking(booking)
        print(f"✅ SMS 로그 {len(sms_logs)}개 생성")

        for log in sms_logs:
            print(f"\n   SMS Log ID: {log.id}")
            print(f"   - Type: {log.sms_type.value}")
            print(f"   - Template Key: {log.template_key}")
            print(f"   - Template Vars: {log.template_vars[:100] if log.template_vars else None}...")
            print(f"   - Scheduled Time: {log.scheduled_time}")

    # 5. 알림톡 발송 시뮬레이션
    print("\n[5] 알림톡 발송 시뮬레이션")
    with get_session() as db:
        sms_log = db.query(SMSLog).filter_by(
            booking_id=booking.id
        ).first()

        if sms_log and sms_log.template_key:
            template_vars = json.loads(sms_log.template_vars) if sms_log.template_vars else {}
            print(f"\n   발송할 템플릿: {sms_log.template_key}")
            print(f"   변수: {list(template_vars.keys())}")

            result = await kakao.send_template(
                recipient=sms_log.recipient_phone,
                template_key=sms_log.template_key,
                variables=template_vars
            )

            print(f"\n   결과:")
            print(f"   - Success: {result.get('success')}")
            print(f"   - Provider: {result.get('provider')}")
            print(f"   - Test Mode: {result.get('test_mode')}")
            print(f"   - Message ID: {result.get('message_id')}")

            if result.get('success'):
                print("\n✅ 알림톡 발송 성공 (TEST MODE)")
            else:
                print(f"\n❌ 알림톡 발송 실패: {result.get('error')}")
        else:
            print("❌ SMS 로그에 template_key가 없습니다")

    # 6. 템플릿 검증
    print("\n[6] 템플릿 변수 검증")
    with get_session() as db:
        sms_log = db.query(SMSLog).filter_by(
            booking_id=booking.id
        ).first()

        if sms_log.template_key:
            template_vars = json.loads(sms_log.template_vars)
            is_valid, error_msg = kakao._validate_template_params(
                sms_log.template_key,
                template_vars
            )

            if is_valid:
                print(f"✅ 템플릿 변수 검증 성공")
            else:
                print(f"❌ 템플릿 변수 검증 실패: {error_msg}")

    # 7. 정리
    print("\n[7] 테스트 데이터 정리")
    with get_session() as db:
        test_booking = db.query(Booking).filter_by(
            naver_booking_id="TEST_KAKAO_001"
        ).first()
        if test_booking:
            db.delete(test_booking)
            db.commit()
            print("✅ 테스트 데이터 삭제 완료")

    print("\n" + "=" * 60)
    print("✨ 전체 플로우 테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_full_flow())
