from typing import Dict, Optional, List
import httpx
import hmac
import hashlib
import secrets
import json
from datetime import datetime
from loguru import logger

from config.settings import settings
from src.models import get_session
from src.models.booking import KakaoTemplate


class KakaoSender:
    """Solapi를 통한 카카오 알림톡 발송 서비스"""

    def __init__(self):
        self.api_key = settings.sms_api_key
        self.api_secret = settings.sms_api_secret
        self.sender = settings.sms_sender
        self.pf_id = getattr(settings, 'kakao_pf_id', '') or settings.kakao_sender_key
        self.api_url = "https://api.solapi.com/messages/v4/send-many/detail"

        # API 키가 없으면 자동으로 test_mode
        if not self.api_key or not self.api_secret:
            self.test_mode = True
            logger.warning("Solapi API keys not configured, forcing TEST MODE")
        else:
            self.test_mode = settings.use_test_mode

        self.templates = self._load_templates()
        pf_display = self.pf_id[:10] + "..." if self.pf_id else "(empty)"
        logger.info(f"KakaoSender init (test_mode: {self.test_mode}, templates: {len(self.templates)}, pfId: {pf_display})")

    def _create_signature(self, date: str, salt: str) -> str:
        """HMAC SHA256 서명 생성"""
        message = date + salt
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _load_templates(self) -> Dict:
        """DB에서 카카오 템플릿 로드"""
        try:
            with get_session() as db:
                templates = db.query(KakaoTemplate).filter_by(is_active=True).all()

                result = {}
                for tmpl in templates:
                    result[tmpl.template_key] = {
                        "template_code": tmpl.template_code,
                        "name": tmpl.name,
                        "description": tmpl.description,
                        "variables": json.loads(tmpl.variables) if tmpl.variables else [],
                        "buttons": json.loads(tmpl.buttons) if tmpl.buttons else []
                    }

                logger.info(f"Loaded {len(result)} templates from DB")
                return result
        except Exception as e:
            logger.error(f"Failed to load templates from DB: {e}")
            return {}

    def _validate_template_params(self, template_key: str, params: Dict) -> tuple[bool, Optional[str]]:
        """템플릿 파라미터 유효성 검증"""
        if template_key not in self.templates:
            # 템플릿이 없으면 DB에서 다시 로드 시도
            self.templates = self._load_templates()
            if template_key not in self.templates:
                return False, f"Template '{template_key}' not found"

        template_info = self.templates[template_key]
        required_vars = template_info.get("variables", [])
        missing_vars = [var for var in required_vars if var not in params]

        if missing_vars:
            return False, f"Missing required variables: {', '.join(missing_vars)}"

        return True, None

    async def send_alimtalk(
        self,
        recipient: str,
        template_id: str,
        variables: Dict,
    ) -> Dict:
        """Solapi를 통한 카카오 알림톡 발송"""
        try:
            # 전화번호 포맷 정리
            recipient = recipient.replace("-", "").replace(" ", "")

            # 변수 포맷 변환 (guest_name -> #{guest_name})
            kakao_variables = {}
            for key, value in variables.items():
                kakao_key = f"#{{{key}}}" if not key.startswith("#{") else key
                kakao_variables[kakao_key] = str(value)

            # HMAC 인증 헤더 생성
            date = datetime.utcnow().isoformat() + "Z"
            salt = secrets.token_hex(16)
            signature = self._create_signature(date, salt)

            headers = {
                "Authorization": f"HMAC-SHA256 apiKey={self.api_key}, date={date}, salt={salt}, signature={signature}",
                "Content-Type": "application/json"
            }

            # 요청 페이로드
            payload = {
                "messages": [{
                    "to": recipient,
                    "from": self.sender,
                    "kakaoOptions": {
                        "pfId": self.pf_id,
                        "templateId": template_id,
                        "variables": kakao_variables,
                        "disableSms": False  # 실패 시 SMS 대체발송
                    }
                }]
            }

            # 테스트 모드: 로그만 출력
            if self.test_mode:
                logger.info(
                    f"[TEST MODE] Alimtalk to {recipient} "
                    f"(template: {template_id}, vars: {kakao_variables})"
                )
                return {
                    "success": True,
                    "provider": "solapi_kakao",
                    "test_mode": True,
                    "response": {"groupId": "TEST_GROUP_ID"},
                    "message_id": "TEST_ALIMTALK_ID",
                }

            # 실제 알림톡 발송
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                response_data = response.json()

            if response.status_code == 200:
                group_id = response_data.get("groupId")

                # 개별 메시지 실패 여부 확인
                failed_list = response_data.get("failedMessageList", [])
                if failed_list:
                    # 실패한 메시지가 있으면 실패로 처리
                    failed_msg = failed_list[0] if failed_list else {}
                    error_code = failed_msg.get("statusCode", "unknown")
                    error_msg = failed_msg.get("statusMessage", "Unknown error")
                    logger.error(f"Alimtalk failed: [{error_code}] {error_msg}")
                    return {
                        "success": False,
                        "provider": "solapi_kakao",
                        "error": f"[{error_code}] {error_msg}",
                        "response": response_data,
                    }

                logger.info(f"Alimtalk sent to {recipient} (groupId: {group_id}, template: {template_id})")
                return {
                    "success": True,
                    "provider": "solapi_kakao",
                    "response": response_data,
                    "message_id": group_id,
                }
            else:
                error_msg = response_data.get("errorMessage", str(response_data))
                logger.error(f"Alimtalk failed: {error_msg}")
                return {
                    "success": False,
                    "provider": "solapi_kakao",
                    "error": error_msg,
                    "response": response_data,
                }

        except httpx.TimeoutException:
            logger.error("[Error] Solapi Kakao timeout")
            return {"success": False, "error": "Request timeout"}

        except Exception as e:
            logger.error(f"[Error] Solapi Kakao exception: {e}")
            return {"success": False, "error": str(e)}

    async def send_template(
        self,
        recipient: str,
        template_key: str,
        variables: Dict
    ) -> Dict:
        """템플릿 키 기반 알림톡 발송"""
        # 템플릿 정보 검증
        is_valid, error_msg = self._validate_template_params(template_key, variables)
        if not is_valid:
            logger.error(f"[Kakao] Template validation failed: {error_msg}")
            return {
                "success": False,
                "provider": "solapi_kakao",
                "error": error_msg
            }

        # 템플릿 정보 로드
        template_info = self.templates[template_key]
        template_code = template_info["template_code"]

        # 알림톡 발송
        return await self.send_alimtalk(
            recipient=recipient,
            template_id=template_code,
            variables=variables,
        )

    async def send_admin_alert(self, message: str) -> Dict:
        """관리자 알림 발송 (로그만 출력)"""
        logger.info(f"[ADMIN ALERT] {message}")
        return {
            "success": True,
            "provider": "log_only",
            "message": message
        }

    def get_template_info(self, template_key: str) -> Optional[Dict]:
        """템플릿 상세 정보 조회"""
        return self.templates.get(template_key)

    def list_templates(self) -> Dict[str, str]:
        """등록된 모든 템플릿 목록 반환"""
        return {
            key: info.get("name", "")
            for key, info in self.templates.items()
        }
