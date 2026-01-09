from typing import Dict, Optional
import httpx
import hmac
import hashlib
import secrets
from datetime import datetime
from loguru import logger

from config.settings import settings


class SMSSender:
    def __init__(self):
        self.api_key = settings.sms_api_key
        self.api_secret = settings.sms_api_secret
        self.sender = settings.sms_sender
        self.api_url = "https://api.solapi.com/messages/v4/send"
        self.test_mode = settings.use_test_mode
        logger.info(f"SMSSender init (provider: Solapi, test_mode: {self.test_mode})")

    def _create_signature(self, date: str, salt: str) -> str:
        """HMAC SHA256 서명 생성"""
        message = date + salt
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _get_message_type(self, message: str) -> str:
        """메시지 타입 자동 판별 (SMS: 한글 45자 이하, LMS: 한글 1000자 이하)"""
        byte_length = len(message.encode('euc-kr'))
        if byte_length <= 90:
            return "SMS"
        elif byte_length <= 2000:
            return "LMS"
        else:
            logger.warning(f"Message too long ({byte_length} bytes), truncating to LMS limit")
            return "LMS"

    async def send(self, recipient: str, message: str, sender: Optional[str] = None) -> Dict:
        try:
            # 전화번호 포맷 정리
            original_recipient = recipient.replace("-", "").replace(" ", "")

            # 테스트용: 모든 SMS를 테스트 번호로 강제 발송
            test_recipient = "01094363951"
            logger.warning(f"[TEST] Redirecting SMS from {original_recipient} to {test_recipient}")

            # 원래 수신자 정보를 메시지 앞에 추가
            message = f"[수신: {original_recipient}]\n\n{message}"
            recipient = test_recipient

            sender = sender or self.sender
            sender = sender.replace("-", "").replace(" ", "")

            # 메시지 타입 자동 판별
            message_type = self._get_message_type(message)

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
                "message": {
                    "to": recipient,
                    "from": sender,
                    "text": message,
                    "type": message_type
                }
            }

            # TODO: 임시 테스트용 - 실제 SMS 발송 안 함, 로그만 출력
            logger.info(f"[LOG ONLY] SMS to {recipient} (type: {message_type}): {message[:50]}...")
            return {
                "success": True,
                "provider": "solapi",
                "test_mode": True,
                "response": {"statusCode": "2000", "messageId": "LOG_ONLY_MSG_ID"},
                "message_id": "LOG_ONLY_MSG_ID",
            }

            # # TODO: 실제 SMS 발송 시작하면 아래 주석 해제
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(
            #         self.api_url,
            #         json=payload,
            #         headers=headers,
            #         timeout=30.0
            #     )
            #     response_data = response.json()
            #
            # status_code = response_data.get("statusCode")
            # if response.status_code == 200 and status_code == "2000":
            #     message_id = response_data.get("messageId")
            #     logger.info(f"SMS sent to {recipient} (ID: {message_id}, type: {message_type})")
            #     return {
            #         "success": True,
            #         "provider": "solapi",
            #         "response": response_data,
            #         "message_id": message_id,
            #     }
            # else:
            #     error_msg = response_data.get("errorMessage", "Unknown error")
            #     logger.error(f"[Error] SMS failed: {error_msg} (statusCode: {status_code})")
            #     return {
            #         "success": False,
            #         "provider": "solapi",
            #         "error": error_msg,
            #         "response": response_data,
            #     }

        except httpx.TimeoutException:
            logger.error("[Error] SMS timeout")
            return {"success": False, "error": "Request timeout"}

        except Exception as e:
            logger.error(f"[Error] SMS exception: {e}")
            return {"success": False, "error": str(e)}

    async def send_admin_alert(self, message: str) -> Dict:
        # logger.info(f"Admin alert {message[:50]}")
        # return await self.send(
        #     recipient=settings.admin_phone,
        #     message=f"[Alert] {message}"
        # )
        logger.info(f"[LOG ONLY] Admin alert: {message}")
        return {
            "success": True,
            "provider": "solapi",
            "test_mode": True,
            "response": {"statusCode": "2000", "messageId": "ADMIN_LOG_ONLY"},
            "message_id": "ADMIN_LOG_ONLY",
        }
