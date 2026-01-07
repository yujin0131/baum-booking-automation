import asyncio
from typing import Optional, List, Dict
from pathlib import Path
from bs4 import BeautifulSoup
from loguru import logger

from src.services.naver_auth import NaverAuth
from src.services.html_file_scraper import HtmlFileScraper
from config.settings import settings


class SmartplaceCrawler:
    """네이버 스마트플레이스 이용 내역 크롤러"""

    SESSION_FILE = "naver_session.json"

    def __init__(self, username: str = None, password: str = None, headless: bool = True):
        self.username = username or settings.naver_id
        self.password = password or settings.naver_password
        self.booking_url = settings.naver_place_url
        self.headless = headless
        self.auth: Optional[NaverAuth] = None
        self._browser_initialized = False

    async def _init_browser_if_needed(self):
        """브라우저 lazy 초기화"""
        if self._browser_initialized and self.auth and self.auth.page:
            return True

        if self.auth:
            try:
                await self.auth.close()
            except Exception:
                pass

        self.auth = NaverAuth(headless=self.headless)
        await self.auth.init_browser()
        self._browser_initialized = True
        return True

    async def _ensure_login(self) -> bool:
        """로그인 상태 확인 및 필요시 로그인"""
        session_path = Path(self.SESSION_FILE)

        # 세션 파일이 있으면 로드 시도
        if session_path.exists():
            logger.info("저장된 세션 로드 시도...")
            try:
                # 브라우저가 없으면 세션 로드 시 자동 초기화됨
                if not self.auth:
                    self.auth = NaverAuth(headless=self.headless)

                loaded = await self.auth.load_session(self.SESSION_FILE)
                if loaded and await self.auth.is_logged_in():
                    logger.info("세션 유효함, 로그인 건너뜀")
                    self._browser_initialized = True
                    return True
                else:
                    logger.info("세션 만료됨, 재로그인 필요")
            except Exception as e:
                logger.warning(f"세션 로드 실패: {e}")

        # 브라우저 초기화 후 새로 로그인
        await self._init_browser_if_needed()
        success = await self.auth.login(self.username, self.password)

        if success:
            await self.auth.save_session(self.SESSION_FILE)
            return True

        return False

    async def crawl_booking_list(self, target_url: Optional[str] = None) -> Optional[str]:
        """
        예약 내역 페이지 크롤링

        Args:
            target_url: 크롤링할 URL (없으면 기본 스마트플레이스 URL)

        Returns:
            페이지 outerHTML
        """
        try:
            if not await self._ensure_login():
                logger.error("로그인 실패")
                return None

            url = target_url or self.SMARTPLACE_URL
            logger.info(f"페이지 이동: {url}")

            await self.auth.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await self.auth._random_delay(3000, 5000)  # 페이지 로딩 대기

            # outerHTML 가져오기
            outer_html = await self.auth.page.evaluate("document.documentElement.outerHTML")
            logger.info(f"크롤링 완료: {len(outer_html)} bytes")

            return outer_html

        except Exception as e:
            logger.error(f"크롤링 중 오류: {e}")
            return None

    async def crawl_element(self, target_url: str, selector: str) -> Optional[str]:
        """
        특정 요소만 크롤링

        Args:
            target_url: 크롤링할 URL
            selector: CSS 선택자

        Returns:
            요소의 outerHTML
        """
        try:
            if not await self._ensure_login():
                logger.error("로그인 실패")
                return None

            logger.info(f"페이지 이동: {target_url}")
            await self.auth.page.goto(target_url, wait_until="networkidle")
            await self.auth._random_delay(2000, 3000)

            # 특정 요소 대기 및 크롤링
            element = await self.auth.page.wait_for_selector(selector, timeout=10000)
            if element:
                outer_html = await element.evaluate("el => el.outerHTML")
                logger.info(f"요소 크롤링 완료: {len(outer_html)} bytes")
                return outer_html
            else:
                logger.warning(f"요소를 찾을 수 없음: {selector}")
                return None

        except Exception as e:
            logger.error(f"요소 크롤링 중 오류: {e}")
            return None

    def parse_bookings_from_html(self, html: str) -> List[Dict]:
        """
        HTML에서 예약 데이터 파싱 (HtmlFileScraper 로직 활용)
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("[class*='BookingListView__contents-user']")

            if not rows:
                logger.warning("예약 데이터 없음")
                return []

            logger.info(f"{len(rows)}개 예약 발견")

            # HtmlFileScraper 인스턴스 생성해서 파싱 로직 활용
            scraper = HtmlFileScraper.__new__(HtmlFileScraper)
            scraper.soup = soup

            bookings = []
            for row in rows:
                booking_data = scraper._extract_booking_from_row(row)
                if booking_data and booking_data.get("guest_name"):
                    bookings.append(booking_data)

            logger.success(f"{len(bookings)}개 예약 파싱 완료")
            return bookings

        except Exception as e:
            logger.error(f"파싱 오류: {e}")
            return []

    async def get_bookings(self, target_url: Optional[str] = None) -> List[Dict]:
        """
        크롤링 + 파싱 한번에 수행

        Returns:
            예약 데이터 리스트
        """
        url = target_url or self.booking_url
        html = await self.crawl_booking_list(url)
        if not html:
            return []

        return self.parse_bookings_from_html(html)

    # 기존 스케줄러 호환용 별칭
    async def get_new_bookings(self) -> List[Dict]:
        return await self.get_bookings()

    async def cleanup(self):
        """스케줄러 호환용"""
        await self.close()

    async def close(self):
        """브라우저 종료"""
        await self.auth.close()


async def main():
    # .env에서 설정 읽어옴 (직접 전달도 가능)
    crawler = SmartplaceCrawler(
        username="staytuned0901",  # 또는 None이면 .env에서 읽음
        password="staytuned0916",
        headless=False
    )

    try:
        # 크롤링 + 파싱 (URL도 .env에서 읽음)
        bookings = await crawler.get_bookings()

        if bookings:
            logger.info(f"\n{'='*50}")
            logger.info(f"총 {len(bookings)}개 예약")
            logger.info(f"{'='*50}")

            for i, b in enumerate(bookings[:5], 1):  # 처음 5개만 출력
                logger.info(f"\n[{i}] {b.get('guest_name')}")
                logger.info(f"    전화: {b.get('guest_phone')}")
                logger.info(f"    체크인: {b.get('check_in_date')}")
                logger.info(f"    객실: {b.get('room_type')}")
                logger.info(f"    상태: {b.get('booking_status')}")

    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())