from typing import Dict, Optional
import httpx
from loguru import logger

from config.settings import settings


class SMSSender:
    def __init__(self):
        self.api_key = settings.sms_api_key
        self.user_id = settings.sms_user_id
        self.sender = settings.sms_sender
        self.api_url = "https://apis.aligo.in/send/"
        self.test_mode = settings.use_test_mode
        logger.info(f"SMSSender init (test_mode: {self.test_mode})")

    async def send(self, recipient: str, message: str, sender: Optional[str] = None) -> Dict:
        try:
            recipient = recipient.replace("-", "").replace(" ", "")
            sender = sender or self.sender

            data = {
                "key": self.api_key,
                "user_id": self.user_id,
                "sender": sender,
                "receiver": recipient,
                "msg": message,
            }

            if self.test_mode:
                data["testmode_yn"] = "Y"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    data=data,
                    timeout=30.0
                )
                response_data = response.json()

            result_code = response_data.get("result_code")
            if response.status_code == 200 and str(result_code) == "1":
                logger.info(f"SMS sent {recipient}")
                return {
                    "success": True,
                    "provider": "aligo",
                    "response": response_data,
                    "message_id": response_data.get("msg_id"),
                }
            else:
                error_msg = response_data.get("message", "Unknown error")
                logger.error(f"[Error] SMS failed {error_msg}")
                return {
                    "success": False,
                    "provider": "aligo",
                    "error": error_msg,
                    "response": response_data,
                }

        except httpx.TimeoutException:
            logger.error("[Error] SMS timeout")
            return {"success": False, "error": "Request timeout"}

        except Exception as e:
            logger.error(f"[Error] SMS exception {e}")
            return {"success": False, "error": str(e)}

    async def send_admin_alert(self, message: str) -> Dict:
        logger.info(f"Admin alert {message[:50]}")
        return await self.send(
            recipient=settings.admin_phone,
            message=f"[Alert] {message}"
        )
