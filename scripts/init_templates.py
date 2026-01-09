"""
카카오 알림톡 템플릿 초기 데이터 삽입 스크립트
"""
import json
from src.models import get_session
from src.models.booking import KakaoTemplate

def init_templates():
    """초기 템플릿 데이터 삽입"""

    templates = [
        {
            "template_key": "check_in_guide_normal",
            "template_code": "staytuned_checkin_normal_001",  # TODO: 실제 승인받은 코드로 변경
            "name": "입실 안내 (일반 객실)",
            "description": "일반 객실 입실 시 발송하는 안내 메시지",
            "variables": json.dumps([
                "guest_name",
                "check_in_date",
                "check_in_time",
                "check_out_time",
                "room_number",
                "room_password"
            ], ensure_ascii=False),
            "buttons": json.dumps([
                {
                    "type": "WL",
                    "name": "숙소 안내 보기",
                    "url_mobile": "https://naver.me/I55Re2hF",
                    "url_pc": "https://naver.me/I55Re2hF"
                }
            ], ensure_ascii=False),
            "is_active": True
        },
        {
            "template_key": "check_in_guide_female_dorm",
            "template_code": "staytuned_checkin_female_002",  # TODO: 실제 승인받은 코드로 변경
            "name": "입실 안내 (여성 도미토리)",
            "description": "여성 도미토리 입실 시 발송하는 안내 메시지",
            "variables": json.dumps([
                "guest_name",
                "check_in_date",
                "check_in_time",
                "check_out_time",
                "room_password"
            ], ensure_ascii=False),
            "buttons": json.dumps([
                {
                    "type": "WL",
                    "name": "숙소 안내 보기",
                    "url_mobile": "https://naver.me/I55Re2hF",
                    "url_pc": "https://naver.me/I55Re2hF"
                }
            ], ensure_ascii=False),
            "is_active": True
        },
        {
            "template_key": "check_in_guide_male_dorm",
            "template_code": "staytuned_checkin_male_003",  # TODO: 실제 승인받은 코드로 변경
            "name": "입실 안내 (남성 도미토리)",
            "description": "남성 도미토리 입실 시 발송하는 안내 메시지",
            "variables": json.dumps([
                "guest_name",
                "check_in_date",
                "check_in_time",
                "check_out_time",
                "room_password"
            ], ensure_ascii=False),
            "buttons": json.dumps([
                {
                    "type": "WL",
                    "name": "숙소 안내 보기",
                    "url_mobile": "https://naver.me/I55Re2hF",
                    "url_pc": "https://naver.me/I55Re2hF"
                }
            ], ensure_ascii=False),
            "is_active": True
        },
        {
            "template_key": "facility_info",
            "template_code": "staytuned_potluck_004",  # TODO: 실제 승인받은 코드로 변경
            "name": "포틀럭파티 안내",
            "description": "포틀럭파티 개최 시 발송하는 안내 메시지",
            "variables": json.dumps([
                "event_date",
                "event_time",
                "location",
                "fee"
            ], ensure_ascii=False),
            "buttons": json.dumps([
                {
                    "type": "WL",
                    "name": "참가 안내 보기",
                    "url_mobile": "https://naver.me/5tJIZ0BF",
                    "url_pc": "https://naver.me/5tJIZ0BF"
                }
            ], ensure_ascii=False),
            "is_active": True
        },
        {
            "template_key": "pet_info",
            "template_code": "staytuned_pet_005",  # TODO: 실제 승인받은 코드로 변경
            "name": "애견동반 안내",
            "description": "애견동반 옵션 선택 고객 대상 안내 메시지",
            "variables": json.dumps([
                "guest_name",
                "room_number"
            ], ensure_ascii=False),
            "buttons": json.dumps([], ensure_ascii=False),
            "is_active": True
        }
    ]

    with get_session() as db:
        for tmpl_data in templates:
            # 이미 존재하는지 확인
            existing = db.query(KakaoTemplate).filter_by(
                template_key=tmpl_data["template_key"]
            ).first()

            if existing:
                print(f"⚠️  Template '{tmpl_data['template_key']}' already exists, skipping")
                continue

            # 새 템플릿 생성
            template = KakaoTemplate(**tmpl_data)
            db.add(template)
            print(f"✅ Created template: {tmpl_data['template_key']}")

        db.commit()
        print(f"\n🎉 Successfully initialized {len(templates)} templates!")


if __name__ == "__main__":
    init_templates()
