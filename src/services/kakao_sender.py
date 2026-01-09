from typing import Dict, Optional, List
import httpx
import json
from loguru import logger

from config.settings import settings
from src.models import get_session
from src.models.booking import KakaoTemplate


class KakaoSender:
    """카카오 알림톡/친구톡 발송 서비스"""

    def __init__(self):
        self.api_key = settings.kakao_api_key
        self.sender_key = settings.kakao_sender_key
        self.channel_id = settings.kakao_channel_id
        self.api_url = "https://api.kakaowork.com/v1/messages.send"
        self.alimtalk_api_url = "https://kapi.kakao.com/v1/api/kakao/message/send"

        # API 키가 없으면 자동으로 test_mode
        if not self.api_key or not self.sender_key:
            self.test_mode = True
            logger.warning("⚠️  Kakao API keys not configured, forcing TEST MODE")
        else:
            self.test_mode = settings.use_test_mode

        self.templates = self._load_templates()
        logger.info(f"KakaoSender init (test_mode: {self.test_mode}, templates: {len(self.templates)})")

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
            return False, f"Template '{template_key}' not found in kakao_templates.yaml"

        template_info = self.templates[template_key]
        required_vars = template_info.get("variables", [])
        missing_vars = [var for var in required_vars if var not in params]

        if missing_vars:
            return False, f"Missing required variables: {', '.join(missing_vars)}"

        return True, None

    async def send_alimtalk(
        self,
        recipient: str,
        template_code: str,
        template_params: Dict,
        buttons: Optional[List[Dict]] = None
    ) -> Dict:
        """카카오 알림톡 발송"""
        try:
            # 전화번호 포맷 정리
            recipient = recipient.replace("-", "").replace(" ", "")

            # 헤더 설정
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # 요청 페이로드
            payload = {
                "senderKey": self.sender_key,
                "templateCode": template_code,
                "to": recipient,
                "content": template_params,
                "buttons": buttons or []
            }

            # 테스트 모드: 로그만 출력, 실제 발송 안 함
            if self.test_mode:
                logger.info(
                    f"[TEST MODE] Alimtalk to {recipient} "
                    f"(template: {template_code}, params: {template_params})"
                )
                return {
                    "success": True,
                    "provider": "kakao_alimtalk",
                    "test_mode": True,
                    "response": {"code": "0000", "messageId": "TEST_ALIMTALK_ID"},
                    "message_id": "TEST_ALIMTALK_ID",
                }

            # 실제 알림톡 발송
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.alimtalk_api_url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                response_data = response.json()

            if response.status_code == 200 and response_data.get("code") == "0000":
                message_id = response_data.get("messageId")
                logger.info(f" Alimtalk sent to {recipient} (ID: {message_id}, template: {template_code})")
                return {
                    "success": True,
                    "provider": "kakao_alimtalk",
                    "response": response_data,
                    "message_id": message_id,
                }
            else:
                error_msg = response_data.get("message", "Unknown error")
                logger.error(f" Alimtalk failed: {error_msg} (code: {response_data.get('code')})")
                return {
                    "success": False,
                    "provider": "kakao_alimtalk",
                    "error": error_msg,
                    "response": response_data,
                }

        except httpx.TimeoutException:
            logger.error("[Error] KakaoTalk timeout")
            return {"success": False, "error": "Request timeout"}

        except Exception as e:
            logger.error(f"[Error] KakaoTalk exception: {e}")
            return {"success": False, "error": str(e)}

    async def send_friendtalk(
        self,
        recipient: str,
        message: str,
        buttons: Optional[List[Dict]] = None,
        image_url: Optional[str] = None
    ) -> Dict:
        """카카오 친구톡 발송"""
        try:
            # 전화번호 포맷 정리
            recipient = recipient.replace("-", "").replace(" ", "")

            # 메시지 길이 체크
            if len(message) > 1000:
                logger.warning(f"Message too long ({len(message)} chars), truncating to 1000")
                message = message[:1000]

            # 헤더 설정
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # 요청 페이로드
            payload = {
                "senderKey": self.sender_key,
                "to": recipient,
                "message": message,
                "buttons": buttons or []
            }

            if image_url:
                payload["imageUrl"] = image_url

            # 테스트 모드: 로그만 출력, 실제 발송 안 함
            if self.test_mode:
                logger.info(
                    f"[TEST MODE] Friendtalk to {recipient}: {message[:50]}..."
                )
                return {
                    "success": True,
                    "provider": "kakao_friendtalk",
                    "test_mode": True,
                    "response": {"code": "0000", "messageId": "TEST_FRIENDTALK_ID"},
                    "message_id": "TEST_FRIENDTALK_ID",
                }

            # 실제 친구톡 발송
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.alimtalk_api_url.replace("/kakao/", "/friendtalk/"),
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                response_data = response.json()

            if response.status_code == 200 and response_data.get("code") == "0000":
                message_id = response_data.get("messageId")
                logger.info(f" Friendtalk sent to {recipient} (ID: {message_id})")
                return {
                    "success": True,
                    "provider": "kakao_friendtalk",
                    "response": response_data,
                    "message_id": message_id,
                }
            else:
                error_msg = response_data.get("message", "Unknown error")
                logger.error(f" Friendtalk failed: {error_msg}")
                return {
                    "success": False,
                    "provider": "kakao_friendtalk",
                    "error": error_msg,
                    "response": response_data,
                }

        except httpx.TimeoutException:
            logger.error("[Error] FriendTalk timeout")
            return {"success": False, "error": "Request timeout"}

        except Exception as e:
            logger.error(f"[Error] FriendTalk exception: {e}")
            return {"success": False, "error": str(e)}

    async def send_template(
        self,
        recipient: str,
        template_key: str,
        variables: Dict
    ) -> Dict:
        """템플릿 기반 알림톡 발송"""
        # 템플릿 정보 검증
        is_valid, error_msg = self._validate_template_params(template_key, variables)
        if not is_valid:
            logger.error(f"[Kakao] Template validation failed: {error_msg}")
            return {
                "success": False,
                "provider": "kakao_alimtalk",
                "error": error_msg
            }

        # 템플릿 정보 로드
        template_info = self.templates[template_key]
        template_code = template_info["template_code"]
        buttons = template_info.get("buttons", [])

        # 알림톡 발송
        return await self.send_alimtalk(
            recipient=recipient,
            template_code=template_code,
            template_params=variables,
            buttons=buttons
        )

    async def send_admin_alert(self, message: str) -> Dict:
        """관리자 알림 발송 (친구톡)"""
        from config.settings import settings
        return await self.send_friendtalk(
            recipient=settings.admin_phone,
            message=f"[Alert] {message}"
        )

    def get_template_info(self, template_key: str) -> Optional[Dict]:
        """템플릿 상세 정보 조회"""
        return self.templates.get(template_key)

    def list_templates(self) -> Dict[str, str]:
        """등록된 모든 템플릿 목록 반환"""
        return {
            key: info.get("name", "")
            for key, info in self.templates.items()
        }
