import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import yaml
from loguru import logger


CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
ACCOMMODATION_FILE = CONFIG_DIR / "accommodation.yaml"
SMS_TEMPLATES_FILE = CONFIG_DIR / "sms_templates.yaml"
CRAWLING_FILE = CONFIG_DIR / "crawling.yaml"


@dataclass
class AccommodationConfig:
    name: str
    address: str
    emergency_contact: str
    wifi_ssid: str
    wifi_password: str
    check_in_time: str
    check_out_time: str
    room_passwords: Dict[str, str]
    default_password: str

    def get_room_password(self, room_number: str) -> str:
        return self.room_passwords.get(str(room_number), self.default_password)


@dataclass
class SMSTemplatesConfig:
    check_in_guide_normal: str
    check_in_guide_female_dorm: str
    check_in_guide_male_dorm: str
    facility_info: str
    pet_info: str

    def get_template(self, template_type: str) -> str:
        templates = {
            "check_in_guide_normal": self.check_in_guide_normal,
            "check_in_guide_female_dorm": self.check_in_guide_female_dorm,
            "check_in_guide_male_dorm": self.check_in_guide_male_dorm,
            "facility_info": self.facility_info,
            "pet_info": self.pet_info,
        }
        return templates.get(template_type, "")


@dataclass
class CrawlingConfig:
    settings: Dict[str, Any]
    login: Dict[str, Any]
    booking_list: Dict[str, Any]
    booking_info: Dict[str, Any]
    pagination: Dict[str, Any]

    def get_selector(self, field_name: str, category: str = "booking_info") -> str:
        categories = {
            "booking_info": self.booking_info,
            "booking_list": self.booking_list,
            "login": self.login,
            "pagination": self.pagination,
        }

        category_data = categories.get(category, {})
        field_data = category_data.get(field_name, {})

        return field_data.get("selector", "")

    def get_fallback_selectors(self, field_name: str, category: str = "booking_info") -> List[str]:
        categories = {
            "booking_info": self.booking_info,
            "booking_list": self.booking_list,
            "login": self.login,
            "pagination": self.pagination,
        }

        category_data = categories.get(category, {})
        field_data = category_data.get(field_name, {})

        return field_data.get("fallbacks", [])

    def get_all_selectors(self, field_name: str, category: str = "booking_info") -> List[str]:
        main = self.get_selector(field_name, category)
        fallbacks = self.get_fallback_selectors(field_name, category)

        result = []
        if main:
            result.append(main)
        result.extend(fallbacks)

        return result


class ConfigManager:
    def __init__(self):
        self._file_mtimes: Dict[str, float] = {}
        self._accommodation: Optional[AccommodationConfig] = None
        self._sms_templates: Optional[SMSTemplatesConfig] = None
        self._crawling: Optional[CrawlingConfig] = None
        self._load_all()
        logger.info("Config loaded")

    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        try:
            if not file_path.exists():
                logger.warning(f"[Warn] Config file not found: {file_path}")
                return {}

            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            self._file_mtimes[str(file_path)] = file_path.stat().st_mtime
            return data

        except yaml.YAMLError as e:
            logger.error(f"[Error] YAML parse error ({file_path}) {e}")
            return {}
        except Exception as e:
            logger.error(f"[Error] Config load error ({file_path}) {e}")
            return {}

    def _load_accommodation(self) -> AccommodationConfig:
        data = self._load_yaml(ACCOMMODATION_FILE)

        accommodation = data.get("accommodation", {})
        wifi = data.get("wifi", {})
        schedule = data.get("schedule", {})

        return AccommodationConfig(
            name=accommodation.get("name", ""),
            address=accommodation.get("address", ""),
            emergency_contact=accommodation.get("emergency_contact", ""),
            wifi_ssid=wifi.get("ssid", ""),
            wifi_password=wifi.get("password", ""),
            check_in_time=schedule.get("check_in_time", "15:00"),
            check_out_time=schedule.get("check_out_time", "11:00"),
            room_passwords=data.get("room_passwords", {}),
            default_password=data.get("default_password", "0000"),
        )

    def _load_sms_templates(self) -> SMSTemplatesConfig:
        data = self._load_yaml(SMS_TEMPLATES_FILE)

        return SMSTemplatesConfig(
            check_in_guide_normal=data.get("check_in_guide_normal", "").strip(),
            check_in_guide_female_dorm=data.get("check_in_guide_female_dorm", "").strip(),
            check_in_guide_male_dorm=data.get("check_in_guide_male_dorm", "").strip(),
            facility_info=data.get("facility_info", "").strip(),
            pet_info=data.get("pet_info", "").strip(),
        )

    def _load_crawling(self) -> CrawlingConfig:
        data = self._load_yaml(CRAWLING_FILE)

        return CrawlingConfig(
            settings=data.get("settings", {}),
            login=data.get("login", {}),
            booking_list=data.get("booking_list", {}),
            booking_info=data.get("booking_info", {}),
            pagination=data.get("pagination", {}),
        )

    def _load_all(self):
        self._accommodation = self._load_accommodation()
        self._sms_templates = self._load_sms_templates()
        self._crawling = self._load_crawling()

    def reload(self):
        logger.info("Reloading config...")
        self._load_all()
        logger.success("Config reloaded")

    def check_and_reload_if_changed(self):
        files_to_check = [
            (ACCOMMODATION_FILE, "_accommodation", self._load_accommodation),
            (SMS_TEMPLATES_FILE, "_sms_templates", self._load_sms_templates),
            (CRAWLING_FILE, "_crawling", self._load_crawling),
        ]

        for file_path, attr_name, loader_func in files_to_check:
            if file_path.exists():
                current_mtime = file_path.stat().st_mtime
                cached_mtime = self._file_mtimes.get(str(file_path), 0)

                if current_mtime > cached_mtime:
                    logger.info(f"Config changed: {file_path.name}")
                    setattr(self, attr_name, loader_func())

    @property
    def accommodation(self) -> AccommodationConfig:
        return self._accommodation

    @property
    def sms_templates(self) -> SMSTemplatesConfig:
        return self._sms_templates

    @property
    def crawling(self) -> CrawlingConfig:
        return self._crawling


config = ConfigManager()
