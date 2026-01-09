import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from loguru import logger
import pyotp


class NaverAuth:
    NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"

    def __init__(self, headless: bool = False, otp_secret: Optional[str] = None):
        self.headless = headless
        self.otp_secret = otp_secret
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def _random_delay(self, min_ms: int = 50, max_ms: int = 150):
        delay = random.uniform(min_ms / 1000, max_ms / 1000)
        await asyncio.sleep(delay)

    async def _random_type(self, page: Page, selector: str, text: str):
        element = await page.wait_for_selector(selector, state="visible")
        await element.click()
        await self._random_delay(100, 300)

        for char in text:
            await page.keyboard.type(char)
            await self._random_delay(50, 200)

    async def _move_mouse(self, page: Page, x: int, y: int):
        current_pos = await page.evaluate("() => ({x: 0, y: 0})")

        steps = random.randint(5, 15)
        for i in range(steps):
            progress = (i + 1) / steps

            noise_x = random.uniform(-5, 5)
            noise_y = random.uniform(-5, 5)

            next_x = current_pos['x'] + (x - current_pos['x']) * progress + noise_x
            next_y = current_pos['y'] + (y - current_pos['y']) * progress + noise_y

            await page.mouse.move(next_x, next_y)
            await self._random_delay(10, 30)

    async def _random_mouse_movement(self, page: Page):
        viewport = page.viewport_size
        if viewport:
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, viewport['width'] - 100)
                y = random.randint(100, viewport['height'] - 100)
                await self._move_mouse(page, x, y)
                await self._random_delay(100, 300)

    async def _scroll_randomly(self, page: Page):
        scroll_amount = random.randint(50, 200)
        await page.mouse.wheel(0, scroll_amount)
        await self._random_delay(200, 500)
        await page.mouse.wheel(0, -scroll_amount)
        await self._random_delay(100, 200)

    async def _handle_2step_auth(self):
        """2단계 인증 처리 (OTP 자동 입력)"""
        if not self.otp_secret:
            logger.warning("OTP 비밀키 없음. 수동 처리 필요")
            await self.page.wait_for_url("**/naver.com/**", timeout=120000)
            return

        try:
            # "OTP로 로그인" 버튼 찾기 및 클릭
            otp_btn = await self.page.query_selector("text=OTP")
            if not otp_btn:
                otp_btn = await self.page.query_selector("text=일회용")
            if otp_btn:
                await otp_btn.click()
                await self._random_delay(1000, 2000)

            # OTP 코드 생성
            totp = pyotp.TOTP(self.otp_secret)
            otp_code = totp.now()
            logger.info(f"OTP 코드 생성: {otp_code}")

            # OTP 입력창 찾기
            otp_input = await self.page.wait_for_selector(
                "input[type='text'], input[type='number'], input[placeholder*='인증'], input[name*='otp']",
                timeout=10000
            )

            if otp_input:
                # OTP 코드 입력
                await otp_input.click()
                await self._random_delay(200, 400)
                await self.page.evaluate(f'''
                    document.querySelector("input[type='text'], input[type='number']").value = "{otp_code}";
                ''')
                await self._random_delay(300, 500)

                # 확인 버튼 클릭
                confirm_btn = await self.page.query_selector("button[type='submit'], .btn_confirm, text=확인")
                if confirm_btn:
                    await confirm_btn.click()
                    await self._random_delay(2000, 3000)

                logger.info("OTP 인증 완료")
            else:
                logger.warning("OTP 입력창을 찾을 수 없음")

        except Exception as e:
            logger.error(f"2단계 인증 처리 중 오류: {e}")
            logger.warning("수동 처리 대기...")
            await self.page.wait_for_url("**/naver.com/**", timeout=120000)

    async def init_browser(self) -> Page:
        self._playwright = await async_playwright().start()

        # Firefox 사용 (Chromium이 macOS에서 크래시)
        self.browser = await self._playwright.firefox.launch(
            headless=self.headless,
        )

        # 컨텍스트 생성 - 실제 사용자처럼 보이는 설정
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            # 실제 브라우저 권한 설정
            permissions=['geolocation'],
            geolocation={'latitude': 37.5665, 'longitude': 126.9780},
        )

        # WebDriver 탐지 우회 스크립트
        await self.context.add_init_script("""
            // WebDriver 속성 숨기기
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Chrome 속성 추가 (일반 크롬처럼 보이게)
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Permissions 우회
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // 플러그인 배열 수정 (빈 배열이면 의심됨)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {type: "application/pdf"},
                        description: "",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    }
                ]
            });

            // Languages 설정
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en']
            });

            // 하드웨어 동시성 (코어 수)
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });

            // DeviceMemory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
        """)

        self.page = await self.context.new_page()

        logger.info("브라우저 초기화 완료")
        return self.page

    async def login(self, username: str, password: str) -> bool:

        if not self.page:
            await self.init_browser()

        try:
            logger.info(f"로그인 페이지 이동 중: {self.NAVER_LOGIN_URL}")
            await self.page.goto(self.NAVER_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            await self._random_delay(1000, 2000)
            logger.info("로그인 페이지 로드 완료")
            await self._random_mouse_movement(self.page)

            # JavaScript로 직접 값 설정 (봇 탐지 우회)
            await self.page.evaluate(f'''
                document.querySelector("#id").value = "{username}";
                document.querySelector("#id").dispatchEvent(new Event("input", {{ bubbles: true }}));
            ''')
            await self._random_delay(300, 600)

            await self.page.evaluate(f'''
                document.querySelector("#pw").value = "{password}";
                document.querySelector("#pw").dispatchEvent(new Event("input", {{ bubbles: true }}));
            ''')
            await self._random_delay(500, 1000)

            login_btn = await self.page.wait_for_selector(".btn_login", state="visible")

            box = await login_btn.bounding_box()
            if box:
                center_x = box['x'] + box['width'] / 2
                center_y = box['y'] + box['height'] / 2
                await self._move_mouse(self.page, int(center_x), int(center_y))
                await self._random_delay(100, 200)

            await login_btn.click()
            await self._random_delay(2000, 3000)
            current_url = self.page.url

            # CAPTCHA 뜨는경우
            if "captcha" in current_url.lower():
                logger.warning("CAPTCHA. 관리자 확인 필요")
                await self.page.wait_for_url("**/naver.com/**", timeout=120000)

            # 2단계 인증 처리
            if "2step" in current_url or "otp" in current_url.lower():
                logger.info("2단계 인증 감지")
                await self._handle_2step_auth()

            if "nid.naver.com" not in self.page.url or "login" not in self.page.url.lower():
                logger.success("로그인 성공")
                return True
            else:
                error_msg = await self.page.query_selector(".error_message, .err_common")
                if error_msg:
                    error_text = await error_msg.text_content()
                    logger.error(f"{error_text}")
                else:
                    logger.error("로그인 실패: 알 수 없는 오류")
                return False

        except Exception as e:
            logger.error(f"로그인 중 오류 발생: {e}")
            return False

    async def get_cookies(self) -> list:
        if self.context:
            return await self.context.cookies()
        return []

    async def save_session(self, filepath: str):
        if self.context:
            await self.context.storage_state(path=filepath)
            logger.info(f"세션이 {filepath}에 저장되었습니다.")

    async def load_session(self, filepath: str) -> bool:
        try:
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.firefox.launch(headless=self.headless)
            self.context = await self.browser.new_context(storage_state=filepath)
            self.page = await self.context.new_page()
            logger.info(f"세션이 {filepath}에서 로드되었습니다.")
            return True
        except Exception as e:
            logger.error(f"세션 로드 실패: {e}")
            return False

    async def is_logged_in(self) -> bool:
        if not self.page:
            return False

        try:
            await self.page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=60000)
            await self._random_delay(1000, 2000)
            login_area = await self.page.query_selector(".MyView-module__link_login___HpHMW")
            return login_area is None
        except Exception:
            return False

    async def close(self):
        if self.browser:
            await self.browser.close()
        if hasattr(self, '_playwright') and self._playwright:
            await self._playwright.stop()
        logger.info("브라우저가 종료되었습니다.")
