import asyncio
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Browser, Page, Playwright
from loguru import logger

from config.settings import settings
from src.utils.config_loader import config
from src.utils.constants import get_room_password
from src.utils.datetime_utils import now_kst


class NaverPlaceScraper:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.is_logged_in = False
        self._crawling_config = config.crawling

        logger.info("NaverPlaceScraper init")

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def initialize(self):
        try:
            logger.info("Initializing browser...")

            self.playwright = await async_playwright().start()

            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()

            timeout = self._crawling_config.settings.get("timeout_seconds", 30) * 1000
            self.page.set_default_timeout(timeout)

            logger.success("Browser initialized")

        except Exception as e:
            logger.error(f"[Error] Init failed {e}")
            raise

    async def cleanup(self):
        try:
            logger.info("Closing browser...")

            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

            logger.success("Browser closed")

        except Exception as e:
            logger.error(f"[Error] Browser close failed {e}")

    async def login(self) -> bool:
        try:
            logger.info("Naver login starting...")

            login_url = self._crawling_config.login.get(
                "login_url",
                "https://nid.naver.com/nidlogin.login"
            )

            await self.page.goto(login_url)
            await asyncio.sleep(1)

            email_selector = await self._find_element("email_input", "login")
            if email_selector:
                await self.page.fill(email_selector, settings.naver_id)
                logger.debug("Email input done")
            else:
                logger.error("[Error] Email input not found")
                return False

            await asyncio.sleep(0.5)
            password_selector = await self._find_element("password_input", "login")
            if password_selector:
                await self.page.fill(password_selector, settings.naver_password)
                logger.debug("Password input done")
            else:
                logger.error("[Error] Password input not found")
                return False

            await asyncio.sleep(0.5)
            login_button_selector = await self._find_element("login_button", "login")
            if login_button_selector:
                await self.page.click(login_button_selector)
                logger.debug("Login button clicked")
            else:
                logger.error("[Error] Login button not found")
                return False

            await asyncio.sleep(3)

            current_url = self.page.url
            if "nidlogin" not in current_url:
                self.is_logged_in = True
                logger.success("Naver login success")
                return True
            else:
                logger.error("[Error] Naver login failed - still on login page")
                return False

        except Exception as e:
            logger.error(f"[Error] Login failed {e}")
            return False

    async def get_new_bookings(self) -> List[Dict]:
        try:
            if not self.is_logged_in:
                logger.warning("[Warn] Not logged in, trying login...")
                if not await self.login():
                    logger.error("[Error] Login failed, cannot get bookings")
                    return []

            logger.info("Navigating to booking list...")
            await self.page.goto(settings.naver_place_url)
            await asyncio.sleep(2)

            logger.info("Extracting bookings...")

            booking_row_selectors = [
                "[class*='BookingListView__contents-user']",
                "[class*='BookingListView__content']",
            ]

            booking_rows = []
            for selector in booking_row_selectors:
                items = await self.page.query_selector_all(selector)
                if items:
                    booking_rows = items
                    logger.debug(f"Found {len(items)} rows (selector: {selector})")
                    break

            if not booking_rows:
                logger.info("No bookings found")
                return []

            bookings = []
            for row in booking_rows:
                booking_data = await self._extract_booking_info(row)
                if booking_data and booking_data.get("guest_name"):
                    bookings.append(booking_data)

            logger.success(f"Extracted {len(bookings)} bookings")
            return bookings

        except Exception as e:
            logger.error(f"[Error] Get bookings failed {e}")
            return []

    async def _extract_booking_info(self, row) -> Optional[Dict]:
        try:
            guest_name = await self._get_text_by_selector(row, "[class*='BookingListView__name-ellipsis']")
            if not guest_name:
                guest_name = await self._get_text_from_element(row, "guest_name")

            guest_phone = await self._get_phone_from_element(row)
            booking_number = await self._get_text_by_selector(row, "[class*='BookingListView__book-number']")
            book_date = await self._get_text_by_selector(row, "[class*='BookingListView__book-date']")
            guest_count_text = await self._get_text_by_selector(row, "[class*='BookingListView__qty']")
            room_type = await self._get_text_by_selector(row, "[class*='BookingListView__host']")
            if not room_type:
                room_type = await self._get_text_from_element(row, "room_type")
            booking_status = await self._get_text_by_selector(row, "[class*='BookingListView__state']")
            special_request_raw = await self._get_text_by_selector(row, "[class*='BookingListView__comment']")
            total_price = await self._get_text_by_selector(row, "[class*='BookingListView__total-price']")

            # "-" 또는 빈 문자열은 None으로 처리
            special_request = None
            if special_request_raw and special_request_raw.strip() not in ("-", "없음", ""):
                special_request = special_request_raw.strip()

            # 데이터 정제
            if guest_phone:
                phone_match = re.search(r'01[0-9]-\d{4}-\d{4}', guest_phone)
                if phone_match:
                    guest_phone = phone_match.group()

            guest_count_int = 1
            if guest_count_text:
                numbers = re.findall(r"\d+", guest_count_text)
                if numbers:
                    guest_count_int = int(numbers[0])

            room_number = self._extract_room_number(room_type)
            check_in_date, check_out_date = self._parse_book_date(book_date)
            room_password = get_room_password(room_number) if room_number else "0000"
            naver_booking_id = booking_number or f"NAVER_{int(datetime.now().timestamp())}"

            return {
                "naver_booking_id": naver_booking_id,
                "guest_name": guest_name or "미확인",
                "guest_phone": guest_phone or "",
                "guest_count": guest_count_int,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "booking_date": now_kst(),
                "room_type": room_type or "미확인",
                "room_number": room_number,
                "special_request": special_request,
                "room_password": room_password,
                "booking_status": booking_status,
                "total_price": total_price,
            }

        except Exception as e:
            logger.error(f"[Error] Row extraction failed {e}")
            return None

    def _extract_room_number(self, room_type: Optional[str]) -> Optional[str]:
        if not room_type:
            return None

        match = re.search(r'ROOM\s*(\d+)', room_type)
        if match:
            return match.group(1)

        numbers = re.findall(r'\d+', room_type)
        for num in numbers:
            if len(num) == 3:
                return num

        return numbers[0] if numbers else None

    def _parse_book_date(self, book_date: Optional[str]) -> tuple:
        if not book_date:
            check_in = now_kst()
            return check_in, check_in + timedelta(days=1)

        try:
            match = re.search(
                r'(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\([^\)]+\)~(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})',
                book_date
            )
            if match:
                in_year = 2000 + int(match.group(1))
                in_month = int(match.group(2))
                in_day = int(match.group(3))
                out_year = 2000 + int(match.group(4))
                out_month = int(match.group(5))
                out_day = int(match.group(6))

                check_in = datetime(in_year, in_month, in_day, 15, 0)
                check_out = datetime(out_year, out_month, out_day, 11, 0)

                return check_in, check_out

        except Exception as e:
            logger.warning(f"[Warn] Date parse failed: {book_date} - {e}")

        check_in = now_kst()
        return check_in, check_in + timedelta(days=1)

    async def _get_text_by_selector(self, parent, selector: str) -> Optional[str]:
        try:
            element = await parent.query_selector(selector)
            if element:
                text = await element.inner_text()
                return text.strip() if text else None
        except Exception:
            pass
        return None

    async def _get_phone_from_element(self, parent) -> Optional[str]:
        try:
            element = await parent.query_selector("[class*='BookingListView__phone']")
            if element:
                text = await element.inner_text()
                return text.strip() if text else None
        except Exception:
            pass
        return await self._get_text_from_element(parent, "guest_phone")

    async def _find_element(self, field_name: str, category: str = "booking_info") -> Optional[str]:
        all_selectors = self._crawling_config.get_all_selectors(field_name, category)

        for selector in all_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    logger.debug(f"Element found: {field_name} (selector: {selector})")
                    return selector
            except Exception:
                continue

        logger.warning(f"[Warn] Element not found: {field_name}")
        return None

    async def _get_text_from_element(self, parent, field_name: str) -> Optional[str]:
        all_selectors = self._crawling_config.get_all_selectors(field_name, "booking_info")

        for selector in all_selectors:
            try:
                element = await parent.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    return text.strip() if text else None
            except Exception:
                continue

        return None

    async def _get_attribute_from_element(self, parent, field_name: str) -> Optional[str]:
        field_config = self._crawling_config.booking_info.get(field_name, {})
        selector = field_config.get("selector", "")
        attribute = field_config.get("attribute", "")

        if not selector or not attribute:
            return None

        try:
            element = await parent.query_selector(selector)
            if element:
                value = await element.get_attribute(attribute)
                return value
        except Exception:
            pass

        fallback_attributes = field_config.get("fallback_attributes", [])
        for attr in fallback_attributes:
            try:
                value = await parent.get_attribute(attr)
                if value:
                    return value
            except Exception:
                continue

        return None
