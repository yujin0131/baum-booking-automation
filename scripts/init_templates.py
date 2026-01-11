"""
카카오 알림톡 템플릿 초기 데이터 삽입 스크립트
config/kakao_templates.yaml 파일에서 템플릿 정보를 읽어 DB에 삽입
"""
import json
import yaml
from pathlib import Path

from src.models import get_session, init_db
from src.models.booking import KakaoTemplate


def init_templates():
    """초기 템플릿 데이터 삽입"""
    # DB 테이블 생성
    init_db()

    # yaml 파일 읽기
    yaml_path = Path(__file__).parent.parent / "config" / "kakao_templates.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    templates_data = data.get("templates", {})

    with get_session() as db:
        for template_key, tmpl in templates_data.items():
            # 이미 존재하는지 확인
            existing = db.query(KakaoTemplate).filter_by(
                template_key=template_key
            ).first()

            if existing:
                print(f"⚠️  Template '{template_key}' already exists, skipping")
                continue

            # 새 템플릿 생성
            template = KakaoTemplate(
                template_key=template_key,
                template_code=tmpl.get("template_code", ""),
                name=tmpl.get("name", ""),
                description=tmpl.get("description", ""),
                variables=json.dumps(tmpl.get("variables", []), ensure_ascii=False),
                buttons=json.dumps(tmpl.get("buttons", []), ensure_ascii=False),
                is_active=True
            )
            db.add(template)
            print(f"✅ Created template: {template_key}")

        db.commit()
        print(f"\n🎉 Successfully initialized {len(templates_data)} templates!")


if __name__ == "__main__":
    init_templates()
