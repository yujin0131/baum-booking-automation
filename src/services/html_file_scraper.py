import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from loguru import logger

from src.utils.config_loader import config
from src.utils.constants import get_room_password
from src.utils.datetime_utils import now_kst


class HtmlFileScraper:
    def __init__(self, html_file_path: str = "sample_booking_page.html"):
        self.html_file_path = Path(html_file_path)
        self.soup: Optional[BeautifulSoup] = None
        self.is_logged_in = True
        self._crawling_config = config.crawling
        logger.info(f"HtmlFileScraper init - {html_file_path}")

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def initialize(self):
        if not self.html_file_path.exists():
            raise FileNotFoundError(f"[Error] file is not found {self.html_file_path}")

        logger.info(f"File loading - {self.html_file_path}")

        with open(self.html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        self.soup = BeautifulSoup(html_content, "html.parser")

        file_size = self.html_file_path.stat().st_size / 1024
        logger.success(f"File loaded successfully ({file_size:.1f})")

    async def cleanup(self):
        self.soup = None

    async def get_new_bookings(self) -> List[Dict]:
        if not self.soup:
            logger.error("File not loaded")
            return []

        try:
            # 크롤링 설정 리로드 (CSS 셀렉터 변경 감지)
            config.check_and_reload_if_changed()
            self._crawling_config = config.crawling

            logger.info("Extracting bookings...")

            rows = self.soup.select("[class*='BookingListView__contents-user']")

            if not rows:
                logger.warning("[Warn] No booking rows found")
                return []

            logger.info(f"Found {len(rows)} rows")

            bookings = []
            for row in rows:
                booking_data = self._extract_booking_from_row(row)
                if booking_data and booking_data.get("guest_name"):
                    bookings.append(booking_data)

            logger.success(f"Extracted {len(bookings)} bookings")
            return bookings

        except Exception as e:
            logger.error(f"[Error] Extraction failed {e}")
            return []

    def _extract_booking_from_row(self, row) -> Optional[Dict]:
        try:
            guest_name = self._get_text(row, "[class*='BookingListView__name-ellipsis']")
            guest_phone = self._extract_phone(row)
            booking_number = self._get_text(row, "[class*='BookingListView__book-number']")
            book_date = self._get_text(row, "[class*='BookingListView__book-date']")
            guest_count_text = self._get_text(row, "[class*='BookingListView__qty']")
            room_type = self._get_text(row, "[class*='BookingListView__host']")
            booking_status = self._get_text(row, "[class*='BookingListView__state']")
            special_request_raw = self._get_text(row, "[class*='BookingListView__comment']")
            option_text = self._get_text(row, "[class*='BookingListView__option']")
            payment_status = self._get_text(row, "[class*='BookingListView__payment-state']")
            total_price = self._get_text(row, "[class*='BookingListView__total-price']")
            order_date_text = self._get_text(row, "[class*='BookingListView__order-date']")

            guest_count = self._parse_guest_count(guest_count_text)
            room_number = self._extract_room_number(room_type)
            check_in_date, check_out_date = self._parse_book_date(book_date)
            booking_date = self._parse_order_date(order_date_text)
            room_password = get_room_password(room_number) if room_number else "0000"
            naver_booking_id = booking_number or f"NAVER_{int(datetime.now().timestamp())}"

            special_request = None
            if special_request_raw and special_request_raw.strip() not in ("-", "없음", ""):
                special_request = special_request_raw.strip()

            # 애견 옵션 감지
            pet_option = False
            if option_text and option_text.strip():
                option_lower = option_text.lower()
                pet_keywords = ["애견", "반려", "강아지", "pet", "dog"]
                pet_option = any(keyword in option_lower for keyword in pet_keywords)

            return {
                "naver_booking_id": naver_booking_id,
                "guest_name": guest_name or "미확인",
                "guest_phone": guest_phone or "",
                "guest_count": guest_count,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "booking_date": booking_date,
                "room_type": room_type or "미확인",
                "room_number": room_number,
                "special_request": special_request,
                "pet_option": pet_option,
                "room_password": room_password,
                "booking_status": booking_status,
                "payment_status": payment_status,
                "total_price": total_price,
            }

        except Exception as e:
            logger.error(f"[Error] Row extraction failed {e}")
            return None

    def _get_text(self, parent, selector: str) -> Optional[str]:
        try:
            el = parent.select_one(selector)
            if el:
                return el.get_text(strip=True)
        except Exception:
            pass
        return None

    def _extract_phone(self, row) -> Optional[str]:
        phone_el = row.select_one("[class*='BookingListView__phone']")
        if phone_el:
            phone_text = phone_el.get_text(strip=True)
            phone_match = re.search(r'01[0-9]-\d{4}-\d{4}', phone_text)
            if phone_match:
                return phone_match.group()
            return phone_text
        return None

    def _parse_guest_count(self, text: Optional[str]) -> int:
        if text:
            numbers = re.findall(r"\d+", text)
            if numbers:
                return int(numbers[0])
        return 1

    def _extract_room_number(self, room_type: Optional[str]) -> Optional[str]:
        if not room_type:
            return None

        match = re.search(r'ROOM\s*(\d+)', room_type)
        if match:
            return match.group(1)

        numbers = re.findall(r'\d+', room_type)
        if numbers:
            for num in numbers:
                if len(num) == 3:
                    return num
            return numbers[0]

        return None

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

                check_in = datetime(in_year, in_month, in_day).date()
                check_out = datetime(out_year, out_month, out_day).date()

                return check_in, check_out

        except Exception as e:
            logger.warning(f"[Warn] Date parse failed {book_date} - {e}")

        check_in = now_kst().date()
        return check_in, check_in + timedelta(days=1)

    def _parse_order_date(self, order_date_text: Optional[str]) -> datetime:
        """신청일시 파싱: '25. 12. 21.(일) 오전 9:59' 형식"""
        if not order_date_text:
            return now_kst()

        try:
            # 정규식: '25. 12. 21.(일) 오전 9:59' or '25. 12. 21.(일) 오후 2:30'
            match = re.search(
                r'(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\([^\)]+\)\s*(오전|오후)\s*(\d{1,2}):(\d{2})',
                order_date_text
            )
            if match:
                year = 2000 + int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                am_pm = match.group(4)
                hour = int(match.group(5))
                minute = int(match.group(6))

                # 오후 처리
                if am_pm == "오후" and hour != 12:
                    hour += 12
                elif am_pm == "오전" and hour == 12:
                    hour = 0

                # KST timezone 적용
                from src.utils.datetime_utils import get_kst_timezone
                return datetime(year, month, day, hour, minute, tzinfo=get_kst_timezone())

        except Exception as e:
            logger.warning(f"[Warn] Order date parse failed {order_date_text} - {e}")

        return now_kst()
