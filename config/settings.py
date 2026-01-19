from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    database_url: str = Field(default="sqlite:///./booking_automation.db")

    naver_id: str = Field(..., description="Naver account ID")
    naver_password: str = Field(..., description="Naver account password")
    naver_place_url: str = Field(..., description="Naver Place management URL")

    sms_api_key: str = Field(default="", description="Solapi API key")
    sms_api_secret: str = Field(default="", description="Solapi API secret")
    sms_sender: str = Field(default="", description="SMS sender phone number")

    # Solapi 카카오 알림톡 설정
    kakao_pf_id: str = Field(default="", description="Solapi Kakao Profile ID (pfId)")
    kakao_api_key: str = Field(default="", description="(미사용) Kakao API key")
    kakao_sender_key: str = Field(default="", description="(미사용) Kakao sender key")
    kakao_channel_id: str = Field(default="", description="(미사용) Kakao channel ID")

    admin_phone: str = Field(..., description="Admin phone for alerts")
    statistics_phone: str = Field(default="", description="Phone number for daily statistics (defaults to admin_phone)")

    check_in_time: str = Field(default="15:00", pattern=r"^\d{2}:\d{2}$")

    log_level: str = Field(default="INFO")
    timezone: str = Field(default="Asia/Seoul")

    max_retries: int = Field(default=3, ge=1)
    retry_delay_seconds: int = Field(default=60, ge=1)

    # Test Mode
    use_test_mode: bool = Field(default=False, description="HTML 파일로 오프라인 테스트")
    test_html_file: str = Field(default="sample_booking_page.html", description="테스트용 HTML 파일")

    @field_validator("check_in_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        try:
            hour, minute = map(int, v.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("[Error] Invalid time range")
            return v
        except Exception as e:
            raise ValueError(f"[Error] Invalid time format. Expected HH:MM, got {v}") from e


settings = Settings()
