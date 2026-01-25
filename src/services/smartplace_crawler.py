import asyncio
import gc
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from bs4 import BeautifulSoup
from loguru import logger

from src.services.naver_auth import NaverAuth
from src.services.html_file_scraper import HtmlFileScraper
from config.settings import settings
from src.utils.constants import BROWSER_RESTART_INTERVAL, PAGE_LOAD_MIN_DELAY_MS, PAGE_LOAD_MAX_DELAY_MS


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
        self._crawl_count = 0  # 크롤링 횟수 카운터

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

    async def crawl_booking_list(self, target_url: Optional[str] = None) -> Tuple[Optional[str], bool]:
        """
        예약 내역 페이지 크롤링

        Args:
            target_url: 크롤링할 URL (없으면 기본 스마트플레이스 URL)

        Returns:
            (페이지 outerHTML, 오늘이용 필터 성공 여부)
        """
        try:
            # 주기적 브라우저 재시작 (메모리 누수 방지)
            self._crawl_count += 1
            if self._crawl_count >= BROWSER_RESTART_INTERVAL:
                logger.info(f"브라우저 재시작 (크롤링 {self._crawl_count}회)")
                if self.auth:
                    await self.auth.close()
                    self.auth = None
                    self._browser_initialized = False
                self._crawl_count = 0

            if not await self._ensure_login():
                logger.error("로그인 실패")
                return None, False

            url = target_url or self.booking_url
            logger.info(f"페이지 이동: {url}")

            await self.auth.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await self.auth._random_delay(PAGE_LOAD_MIN_DELAY_MS, PAGE_LOAD_MAX_DELAY_MS)  # 페이지 로딩 대기

            # 로그인 페이지로 리다이렉트 확인 (세션 만료 감지)
            current_url = self.auth.page.url
            page_title = await self.auth.page.title()

            if "로그인" in page_title or "nid.naver.com" in current_url:
                logger.warning(f"세션 만료 감지 (title: {page_title}, url: {current_url})")
                logger.info("세션 파일 삭제 및 재로그인 시도")

                # 세션 파일 삭제
                from pathlib import Path
                session_file = Path(self.SESSION_FILE)
                try:
                    if session_file.exists():
                        session_file.unlink(missing_ok=True)
                        logger.info(f"세션 파일 삭제: {self.SESSION_FILE}")
                except OSError as e:
                    logger.warning(f"세션 파일 삭제 실패 : {e}")

                # 재로그인
                success = await self.auth.login(self.username, self.password)
                if not success:
                    logger.error("재로그인 실패")
                    return None, False

                logger.success("재로그인 성공")

                # 세션 저장
                await self.auth.save_session(self.SESSION_FILE)

                # 예약 페이지 다시 이동
                await self.auth.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await self.auth._random_delay(PAGE_LOAD_MIN_DELAY_MS, PAGE_LOAD_MAX_DELAY_MS)

                # 재확인
                current_url = self.auth.page.url
                if "nid.naver.com" in current_url:
                    logger.error("재로그인 후에도 로그인 페이지, 중단")
                    return None, False

            # "오늘이용" 필터 클릭 (재시도 로직 포함)
            filter_applied = False
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # 버튼이 DOM에 나타날 때까지 대기
                    today_button = await self.auth.page.wait_for_selector(
                        "input[value*='오늘이용']",
                        timeout=5000,
                        state="attached"
                    )
                    if today_button:

                        await self.auth._random_delay(500, 1000)
                        await today_button.click()

                        await self.auth._random_delay(2000, 3000)
                        logger.info("'오늘이용' 필터 적용 성공")
                        filter_applied = True
                        break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(f"'오늘이용' 필터 클릭 재시도 {attempt + 1}/{max_retries}: {e}")
                        await self.auth._random_delay(1000, 2000)
                    else:
                        logger.warning(f"'오늘이용' 필터 클릭 실패, 파싱 단계에서 필터링: {e}")

            outer_html = await self.auth.page.evaluate("document.documentElement.outerHTML")
            logger.info(f"크롤링 완료: {len(outer_html)} bytes")
           # 디버그: HTML 파일로 저장
            # with open("debug_crawl.html", "w", encoding="utf-8") as f:
            #     f.write(outer_html)
            # logger.info("HTML saved to debug_crawl.html")
            await self.auth.page.evaluate("() => { document.body.innerHTML = ''; }")

            return outer_html, filter_applied

        except Exception as e:
            logger.error(f"크롤링 중 오류: {e}")
            return None, False

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
            await self.auth.page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
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

    def parse_bookings_from_html(self, html: str, filter_today: bool = False) -> List[Dict]:
        """
        HTML에서 예약 데이터 파싱 (HtmlFileScraper 로직 활용)

        Args:
            html: 파싱할 HTML
            filter_today: True이면 오늘 체크인 예약만 필터링
        """
        try:
            # 크롤링 설정 리로드 (CSS 셀렉터 변경 감지)
            from src.utils.config_loader import config
            config.check_and_reload_if_changed()
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

            # 오늘 날짜 필터링
            if filter_today:
                from src.utils.datetime_utils import now_kst
                today = now_kst().date()
                original_count = len(bookings)
                bookings = [b for b in bookings if b.get("check_in_date") == today]
                logger.info(f"오늘 체크인 필터링: {original_count}개 → {len(bookings)}개")

            logger.success(f"{len(bookings)}개 예약 파싱 완료")
            return bookings

        except Exception as e:
            logger.error(f"파싱 오류: {e}")
            return []

    async def get_bookings(self, target_url: Optional[str] = None) -> Optional[List[Dict]]:
        """
        크롤링 + 파싱 한번에 수행

        Returns:
            예약 데이터 리스트
        """
        url = target_url or self.booking_url
        html, filter_applied = await self.crawl_booking_list(url)
        if not html:
            return None

        # 필터 클릭 실패 시 파싱 단계에서 오늘 날짜로 필터링
        return self.parse_bookings_from_html(html, filter_today=not filter_applied)

    # 기존 스케줄러 호환용 별칭
    async def get_new_bookings(self) -> Optional[List[Dict]]:
        return await self.get_bookings()

    async def cleanup(self):
        """스케줄러 호환용"""
        await self.close()

    async def close(self):
        """브라우저 종료 및 메모리 정리"""
        if self.auth:
            await self.auth.close()
        # 명시적 가비지 컬렉션으로 메모리 해제
        gc.collect()
        logger.debug("Browser closed and garbage collected")
